"""Tool hooks (src/freya_builder/hooks.py), executed as the exact generated source.

Post hooks get `result` shaped like the platform envelope (kit/docs/tools-and-code.md, "Where a
result lands"); pre hooks get `vars` and `config`. Every behavioural test runs twice: in one
namespace, and with separate globals/locals (the sandbox's exec style is not documented).
Brief A values appear here only as test data (tests/fixtures/spec_a.json).
"""

import ast
import copy
import json
from pathlib import Path

import pytest

from freya_builder import hooks
from freya_builder.sandbox import CLOSE, OPEN

SPEC = json.loads((Path(__file__).parent / "fixtures" / "spec_a.json").read_text())
FAILED_ROW = "not_verified_failed"
CALLBACK_ROW = "not_reached_callback"
HEADER = {"Content-Type": "application/json", "X-Request-Id": "abc"}
SERVER_ERROR = {
    "status": "error",
    "message": "Request failed with status code 500",
    "status_code": 500,
    "header": dict(HEADER),
}
PROMISE_RULE = SPEC["failure_rules"]["promise"]
PROMISE_LINE = SPEC["success_lines"]["promise"]
FAILED_LINE = SPEC["identity"]["failed_line"]
Q1, Q2 = (q["ask"] for q in SPEC["identity"]["questions"])


def envelope(data, status="success", code=200):
    return {
        "status": status,
        "data": data,
        "message": "Successfully executed POST request",
        "status_code": code,
        "header": dict(HEADER),
    }


def all_sources(spec=SPEC):
    return {
        "verify_post": hooks.verify_post(spec, FAILED_ROW),
        "verify_pre": hooks.verify_pre(spec),
        "promise_post": hooks.promise_post(spec, 1),
        "promise_pre": hooks.promise_pre(spec),
        "note_post": hooks.note_post(spec),
        "callback_post": hooks.callback_post(spec, CALLBACK_ROW),
        "callback_pre": hooks.callback_pre(spec),
    }


SOURCES = all_sources()
POST = {k: v for k, v in SOURCES.items() if k.endswith("_post")}
PRE = {k: v for k, v in SOURCES.items() if k.endswith("_pre")}


@pytest.fixture(params=[False, True], ids=["shared", "split"])
def split(request):
    return request.param


def run(src, names, split):
    if split:
        exec(src, {}, names)
    else:
        exec(src, names)
    return names


def post(src, result, split, vs=None):
    names = {"result": result}
    if vs is not None:
        names["vars"] = vs
    run(src, names, split)
    return result


def what(result):
    return result["data"]["what_to_do_next"]


def pre(src, body, split, vs=None):
    config = {
        "url": "https://bank.example/tool",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }
    names = {"vars": {} if vs is None else vs, "config": config}
    run(src, names, split)
    return config["body"], names["vars"]


# --- source rules -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_source_is_sandbox_safe(name):
    src = SOURCES[name]
    assert OPEN not in src and CLOSE not in src
    compile(src, name, "exec")
    assert src.startswith("try:\n") and src.endswith("except Exception:\n    pass\n")
    assert src.isascii()
    # Straight-line code only: these behave differently (or fail) when the sandbox runs the hook
    # with separate globals and locals on a Python older than 3.12 (no inlined comprehensions).
    banned = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Lambda, ast.ClassDef)
    banned += (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    assert not [type(n).__name__ for n in ast.walk(ast.parse(src)) if isinstance(n, banned)]
    if name.endswith("_post"):
        assert "result.pop('header', None)" in src


def test_spec_text_with_quotes_braces_and_newlines_is_embedded_exactly(split):
    nasty = "He said \"no\" and 'maybe' {{x}} } { $HOME $$ \\ end\nnext line, naïve €"
    spec = copy.deepcopy(SPEC)
    spec["identity"]["failed_line"] = nasty
    spec["identity"]["hints"][0]["instruction"] = nasty
    spec["success_lines"]["promise"] = nasty
    spec["failure_rules"]["promise"] = nasty
    for name, src in all_sources(spec).items():
        assert OPEN not in src and CLOSE not in src and "$" not in src, name
    failed = post(
        hooks.verify_post(spec, FAILED_ROW),
        envelope({"ok": True, "verified": False, "wrong_answers_left": 0}),
        split,
    )
    assert nasty in what(failed)
    hinted = post(
        hooks.verify_post(spec, FAILED_ROW),
        envelope({"ok": True, "verified": False, "hint": "day_month_swapped"}),
        split,
    )
    assert what(hinted).startswith(nasty)
    ok = post(hooks.promise_post(spec, 1), envelope({"ok": True}), split)
    assert what(ok).endswith(nasty)
    bad = post(hooks.promise_post(spec, 1), envelope({"ok": False}), split)
    assert what(bad).endswith(nasty)


def test_unknown_exit_rows_and_bad_slots_are_rejected_at_build_time():
    with pytest.raises(ValueError):
        hooks.verify_post(SPEC, "no_such_row")
    with pytest.raises(ValueError):
        hooks.callback_post(SPEC, "no_such_row")
    with pytest.raises(ValueError):
        hooks.promise_post(SPEC, 0)


# --- every post hook: the T6 contract (docs/design.md §2) ---------------------------------------

T6_RESULTS = {
    "ok true": envelope({"ok": True}),
    "ok false": envelope({"ok": False, "error": "nope"}),
    "500 without data": SERVER_ERROR,
    "hint": envelope({"ok": True, "verified": False, "hint": "day_month_swapped"}),
}


@pytest.mark.parametrize("case", sorted(T6_RESULTS))
@pytest.mark.parametrize("name", sorted(POST))
def test_every_post_hook_sets_what_to_do_next_and_drops_header(name, case, split):
    result = post(POST[name], copy.deepcopy(T6_RESULTS[case]), split)
    assert "header" not in result
    assert isinstance(what(result), str) and what(result)


@pytest.mark.parametrize("garbage", [None, "text", 5, [], ["a"]])
@pytest.mark.parametrize("name", sorted(POST))
def test_post_hooks_never_raise_on_garbage(name, garbage, split):
    assert post(POST[name], garbage, split) == garbage


@pytest.mark.parametrize("name", sorted(POST))
def test_post_hooks_never_raise_on_an_empty_envelope(name, split):
    result = post(POST[name], {}, split)
    assert what(result)


@pytest.mark.parametrize("name", sorted(PRE))
def test_pre_hooks_never_raise_on_garbage(name, split):
    for config in (None, "x", {}, {"body": None}, {"body": "raw"}, {"body": []}):
        names = {"vars": {}, "config": copy.deepcopy(config)}
        run(PRE[name], names, split)
        assert names["config"] == config
    run(PRE[name], {"config": {"body": {}}}, split)  # no `vars`: the name is the builtin


# --- verify_identity post -----------------------------------------------------------------------

VERIFY_POST = POST["verify_post"]


@pytest.mark.parametrize("gate", [True, "true", "True"])
def test_verify_gate_true_means_all_verified(gate, split):
    result = post(
        VERIFY_POST, envelope({"ok": True, "verified": True, "all_verified": gate}), split
    )
    assert what(result) == (
        "Both answers are verified. Do not ask more security questions; "
        "the account is being loaded."
    )
    assert "header" not in result


@pytest.mark.parametrize("verified", [True, "true", "True"])
def test_verify_correct_names_the_next_question_when_the_asked_key_is_known(verified, split):
    vs = {"hook_verify_question": "date_of_birth"}
    data = {"ok": True, "verified": verified, "all_verified": False, "wrong_answers_left": 3}
    result = post(VERIFY_POST, envelope(data), split, vs)
    assert what(result) == "Correct. Now ask: " + Q2
    assert vs["hook_verify_passed"] == "date_of_birth"


def test_verify_correct_after_an_earlier_pass_skips_passed_questions(split):
    vs = {"hook_verify_question": "phone_last4", "hook_verify_passed": "date_of_birth"}
    data = {"ok": True, "verified": True, "all_verified": False}
    result = post(VERIFY_POST, envelope(data), split, vs)
    assert what(result).startswith("Correct. Now ask the next security question")
    assert vs["hook_verify_passed"] == "date_of_birth,phone_last4"


def test_verify_correct_out_of_order_points_back_to_the_first_question(split):
    vs = {"hook_verify_question": "phone_last4"}
    data = {"ok": True, "verified": True, "all_verified": False}
    assert what(post(VERIFY_POST, envelope(data), split, vs)) == "Correct. Now ask: " + Q1


def test_verify_correct_without_vars_is_generic_and_lists_the_questions(split):
    result = post(
        VERIFY_POST, envelope({"ok": True, "verified": True, "all_verified": False}), split
    )
    text = what(result)
    assert text.startswith("Correct. Now ask the next security question that has not been")
    assert "1. " + Q1 in text and "2. " + Q2 in text


def test_verify_pre_then_post_share_the_asked_key(split):
    vs = {}
    body = {"customer_id": "c1", "field": "date_of_birth", "answer": "1988-3-14"}
    pre(PRE["verify_pre"], body, split, vs)
    assert vs["hook_verify_question"] == "date_of_birth"
    result = post(VERIFY_POST, envelope({"ok": True, "verified": True}), split, vs)
    assert what(result) == "Correct. Now ask: " + Q2


def test_verify_hint_gives_the_brief_instruction(split):
    data = {"ok": True, "verified": False, "all_verified": False, "wrong_answers_left": 3}
    data["hint"] = "day_month_swapped"
    result = post(VERIFY_POST, envelope(data), split)
    instruction = SPEC["identity"]["hints"][0]["instruction"]
    assert what(result) == instruction + " (This does not count as a wrong answer.)"


def test_verify_hint_that_counts_as_wrong_says_so(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["hints"][0]["counts_as_wrong"] = True
    data = {"ok": True, "verified": False, "hint": "day_month_swapped", "wrong_answers_left": 1}
    result = post(hooks.verify_post(spec, FAILED_ROW), envelope(data), split)
    assert what(result).endswith("(This counts as a wrong answer.)")


def test_verify_unknown_hint_is_passed_on(split):
    data = {"ok": True, "verified": False, "hint": "year_off_by_one", "wrong_answers_left": 2}
    text = what(post(VERIFY_POST, envelope(data), split))
    assert text.startswith("The bank returned hint year_off_by_one; follow the brief for it.")
    assert text.endswith(
        "Wrong answer; do not say it was correct. Wrong answers left: 2. "
        "You may ask that same question again."
    )


@pytest.mark.parametrize("ok", [False, "false", "False"])
def test_verify_unreadable_answer_is_not_wrong(ok, split):
    data = {"ok": ok, "error": "answer is not a date"}
    result = post(VERIFY_POST, envelope(data), split)
    assert what(result) == (
        "The answer could not be read (bank error: answer is not a date); ask the customer to "
        "say it again (this does not count as wrong)."
    )


@pytest.mark.parametrize("left", [2, "2", 1])
def test_verify_wrong_with_answers_left_may_ask_again(left, split):
    data = {"ok": True, "verified": False, "all_verified": False, "wrong_answers_left": left}
    result = post(VERIFY_POST, envelope(data), split)
    # the count tells the model where it stands (PUB-03 talkative: an 18-turn loop on one question)
    assert what(result) == (
        f"Wrong answer; do not say it was correct. Wrong answers left: {int(left)}. "
        "You may ask that same question again."
    )


@pytest.mark.parametrize("left", [0, "0"])
def test_verify_no_answers_left_fails_and_names_the_exit(left, split):
    data = {"ok": True, "verified": False, "all_verified": False, "wrong_answers_left": left}
    result = post(VERIFY_POST, envelope(data), split)
    assert what(result) == (
        "The check has FAILED. Do not state any debt or account detail. Say: "
        + FAILED_LINE
        + " Then thank the customer, say goodbye and call transition_to_ev_not_verified_failed"
        " in the same message, with no other tool."
    )


def test_verify_failed_wins_over_a_hint(split):
    data = {"ok": True, "verified": False, "hint": "day_month_swapped", "wrong_answers_left": 0}
    assert what(post(VERIFY_POST, envelope(data), split)).startswith("The check has FAILED.")


def test_verify_500_without_data_is_a_service_error_not_a_wrong_answer(split):
    result = post(VERIFY_POST, copy.deepcopy(SERVER_ERROR), split)
    assert "header" not in result
    assert what(result) == (
        "The answer was not checked because of a service error. This is not a wrong answer. "
        "Call verify_identity once more with the same answer."
    )


@pytest.mark.parametrize(
    "result",
    [
        envelope({"ok": True, "verified": True, "all_verified": True}, status="error", code=500),
        envelope({"ok": True, "verified": True, "all_verified": True}, code="503"),
        envelope("upstream timeout", status="error", code=504),
    ],
)
def test_verify_failure_envelopes_win_over_the_body(result, split):
    text = what(post(VERIFY_POST, result, split))
    assert text.startswith("The answer was not checked because of a service error")


def test_verify_string_data_is_kept_as_the_error_text(split):
    result = envelope("upstream timeout", status="error", code=504)
    assert "(bank error: upstream timeout)" in what(post(VERIFY_POST, result, split))


def test_verify_bare_body_without_envelope_is_read_as_data(split):
    result = {"ok": True, "verified": False, "wrong_answers_left": 0}
    post(VERIFY_POST, result, split)
    assert result["what_to_do_next"].startswith("The check has FAILED.")


def test_verify_question_count_other_than_two_says_all(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["questions"].append({"key": "postcode", "ask": "Postcode?", "format": "alnum"})
    src = hooks.verify_post(spec, FAILED_ROW)
    result = post(src, envelope({"ok": True, "all_verified": True}), split)
    assert what(result).startswith("All answers are verified.")


def _all_at_once_post(answer_ok="ok"):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["answer_ok_field"] = answer_ok
    return hooks.verify_post(spec, FAILED_ROW, all_at_once=True)


@pytest.mark.parametrize("answer_ok", ["ok", "verified", ""])
def test_verify_all_at_once_wrong_answer_is_never_correct(answer_ok, split):
    # Engine-fixes item 1 (rehearsal P3b): ok=true only means the check ran.
    data = {"ok": True, "verified": True, "all_verified": False, "wrong_answers_left": 2}
    msg = what(post(_all_at_once_post(answer_ok), envelope(data), split))
    assert not msg.startswith("Correct")
    assert msg.startswith("The check did not pass: at least one answer is wrong.")
    assert "Failed checks left: 2." in msg and ASK_ALL in msg
    assert msg.endswith("each new answer in place of the old one.")


def test_verify_all_at_once_names_the_answers_the_bank_marked_wrong(split):
    data = {"ok": True, "all_verified": False, "wrong_fields": ["phone_last4"]}
    msg = what(post(_all_at_once_post(), envelope(data), split))
    assert "The bank marked as wrong: " + Q2 + "." in msg
    assert "You may ask again for those answers only," in msg and Q1 not in msg


ASK_ALL = "Ask again for the answers the BANK BRIEF says to ask for after a failed check (if it "


@pytest.mark.parametrize(
    "data",
    [
        {"wrong_fields": ["phone_last4", "pin"]},  # not only question keys
        {"matched_fields": ["date_of_birth"]},  # review of cand-eng.1: a right answer named wrong
        {"correct_fields": ["date_of_birth"], "failed": ["phone_last4"], "wrong": ["phone_last4"]},
        {"wrong_fields": "phone_last4"},  # not a list
        {"wrong_fields": []},
    ],
)
def test_verify_all_at_once_names_answers_only_from_one_list_that_says_wrong(data, split):
    data = {"ok": True, "all_verified": False, **data}
    msg = what(post(_all_at_once_post(), envelope(data), split))
    assert "marked as wrong" not in msg and ASK_ALL in msg


def test_verify_all_at_once_gate_failed_and_unreadable_paths_are_unchanged(split):
    src = _all_at_once_post()
    assert what(post(src, envelope({"ok": True, "all_verified": True}), split)).startswith(
        "Both answers are verified."
    )
    gone = {"ok": True, "all_verified": False, "wrong_answers_left": 0}
    assert what(post(src, envelope(gone), split)).startswith("The check has FAILED.")
    unreadable = what(post(src, envelope({"ok": False, "error": "bad date"}), split))
    assert unreadable.startswith("The answer could not be read")


def test_verify_per_answer_source_is_unchanged_by_the_all_at_once_branch():
    assert hooks.verify_post(SPEC, FAILED_ROW) == hooks.verify_post(
        SPEC, FAILED_ROW, all_at_once=False
    )
    assert "marked as wrong" not in hooks.verify_post(SPEC, FAILED_ROW)


# --- verify_identity pre ------------------------------------------------------------------------

VERIFY_PRE = PRE["verify_pre"]


def verify_answer(field, answer, split, src=VERIFY_PRE):
    body = {"customer_id": "c_1", "field": field, "answer": answer}
    out, _ = pre(src, body, split)
    assert out["customer_id"] == "c_1" and out["field"] == field
    return out["answer"]


@pytest.mark.parametrize(
    "said, sent",
    [
        ("1988-03-14", "1988-03-14"),
        ("1988-3-4", "1988-03-04"),
        ("1988/03/04", "1988-03-04"),
        ("1988.3.14", "1988-03-14"),
        ("  1988-03-14 ", "1988-03-14"),
        ("1988-03-14T00:00:00", "1988-03-14"),
        ("1988-14-03", "1988-03-14"),
        ("14/03/1988", "1988-03-14"),
        ("03/14/1988", "1988-03-14"),
        ("5/5/1990", "1990-05-05"),
        ("14 March 1988", "1988-03-14"),
        ("March 14th, 1988", "1988-03-14"),
        ("the 3rd of sept 1990", "1990-09-03"),
        ("1988 Mar 4", "1988-03-04"),
        ("04/03/1988", "04/03/1988"),
        ("1988-13-14", "1988-13-14"),
        ("14/03/88", "14/03/88"),
        ("not a date", "not a date"),
        ("", ""),
    ],
)
def test_verify_pre_dates_become_iso_only_when_unambiguous(said, sent, split):
    assert verify_answer("date_of_birth", said, split) == sent


@pytest.mark.parametrize(
    "said, sent",
    [
        ("4471", "4471"),
        ("44 71", "4471"),
        ("4-4-7-1", "4471"),
        ("four four seven one", "4471"),
        ("oh three five eight", "0358"),
        ("Zero Three Five Eight", "0358"),
        (358, "0358"),
        (4471, 4471),
        (4471.0, 4471),
        ("0358", "0358"),
        ("no idea", "no idea"),
    ],
)
def test_verify_pre_digits_are_digits_only(said, sent, split):
    out = verify_answer("phone_last4", said, split)
    assert out == sent and type(out) is type(sent)


def test_verify_pre_unknown_question_is_only_stripped(split):
    assert verify_answer("mothers_maiden_name", "  van Dijk ", split) == "van Dijk"


def test_verify_pre_missing_answer_is_left_missing(split):
    body, vs = pre(VERIFY_PRE, {"customer_id": "c_1", "field": "phone_last4"}, split)
    assert body == {"customer_id": "c_1", "field": "phone_last4"}
    assert vs["hook_verify_question"] == "phone_last4"


def test_verify_pre_other_formats(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["questions"] = [
        {"key": "birth_year", "ask": "Year of birth?", "format": "year"},
        {"key": "postcode", "ask": "Postcode?", "format": "alnum"},
        {"key": "pet", "ask": "First pet?", "format": "text"},
        {"key": "pin", "ask": "PIN?", "format": "digits:6"},
    ]
    src = hooks.verify_pre(spec)
    assert verify_answer("birth_year", "born in 1988", split, src) == "1988"
    assert verify_answer("birth_year", " 1988 ", split, src) == "1988"
    assert verify_answer("postcode", " sw1a 1aa ", split, src) == "SW1A1AA"
    assert verify_answer("pet", "  Rex ", split, src) == "Rex"
    assert verify_answer("pin", 1234, split, src) == "001234"


def test_verify_pre_all_at_once_shape_normalises_each_answer_field(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["question_field"] = ""
    spec["identity"]["answer_field"] = ""
    body = {"customer_id": "c_1", "date_of_birth": "14 March 1988", "phone_last4": "44 71"}
    out, vs = pre(hooks.verify_pre(spec), body, split)
    assert out == {"customer_id": "c_1", "date_of_birth": "1988-03-14", "phone_last4": "4471"}
    assert vs["hook_verify_question"] == ""


# --- create_promise -----------------------------------------------------------------------------

PROMISE_POST = POST["promise_post"]
NOT_RECORDED = ". Do not say it was recorded. Per the brief: " + PROMISE_RULE


@pytest.mark.parametrize("ok", [True, "true", "True"])
def test_promise_success_says_the_brief_line(ok, split):
    result = post(PROMISE_POST, envelope({"ok": ok, "promise_id": "pr_1"}), split)
    assert what(result) == (
        "Recorded (P1). When every agreed promise is recorded, say exactly once: " + PROMISE_LINE
    )
    assert "header" not in result


@pytest.mark.parametrize("ok", [False, "false", "False"])
def test_promise_ok_false_is_not_recorded_with_the_bank_error(ok, split):
    result = post(PROMISE_POST, envelope({"ok": ok, "error": "date after deadline"}), split)
    assert what(result) == "NOT recorded (P1) (bank error: date after deadline)" + NOT_RECORDED


@pytest.mark.parametrize(
    "result",
    [
        SERVER_ERROR,
        envelope({"ok": True}, status="error", code=500),
        envelope({"ok": True}, code=502),
        envelope({"promise_id": "pr_1", "recorded": False}),
        envelope(None),
    ],
    ids=["500 without data", "status error", "status code", "ok missing, false field", "data null"],
)
def test_promise_failure_signals_are_not_recorded(result, split):
    result = post(PROMISE_POST, copy.deepcopy(result), split)
    assert what(result) == "NOT recorded (P1)" + NOT_RECORDED
    assert "header" not in result


def test_promise_multi_product_says_the_line_once(split):
    spec = copy.deepcopy(SPEC)
    spec["meta"]["max_products"] = 3
    result = post(hooks.promise_post(spec, 2), envelope({"ok": True}), split)
    assert what(result) == (
        "Recorded (P2). When every agreed promise is recorded, say exactly once: " + PROMISE_LINE
    )


def test_promise_without_brief_sentences_stays_honest(split):
    spec = copy.deepcopy(SPEC)
    spec["success_lines"]["promise"] = ""
    spec["failure_rules"]["promise"] = ""
    src = hooks.promise_post(spec, 1)
    ok = what(post(src, envelope({"ok": True}), split))
    assert ok == "Recorded (P1). Tell the customer the promise is recorded."
    bad = what(post(src, envelope({"ok": False}), split))
    assert bad == (
        "NOT recorded (P1). Do not say it was recorded. Tell the customer it could not be recorded."
    )


PROMISE_PRE = PRE["promise_pre"]


@pytest.mark.parametrize(
    "amount, sent",
    [
        (420, 420),
        (420.0, 420.0),
        (420.456, 420.46),
        (637.5, 637.5),
        ("420", 420.0),
        ("420.50", 420.5),
        ("1,250.00", 1250.0),
        ("420,50", 420.5),
        ("1.250,50", 1250.5),
        ("EUR 99.999", 100.0),
        ("abc", "abc"),
    ],
)
def test_promise_pre_rounds_the_amount_and_keeps_a_number(amount, sent, split):
    body = {"customer_id": "c_1", "product_id": "p1", "amount": amount, "date": "2026-10-16"}
    out, _ = pre(PROMISE_PRE, body, split)
    assert out["amount"] == sent and type(out["amount"]) is type(sent)
    assert out["customer_id"] == "c_1" and out["product_id"] == "p1"


@pytest.mark.parametrize(
    "said, sent",
    [
        ("2026-10-16", "2026-10-16"),
        ("2026-10-6", "2026-10-06"),
        ("2026/10/16", "2026-10-16"),
        ("16 October 2026", "2026-10-16"),
        ("Friday", "Friday"),
    ],
)
def test_promise_pre_pads_the_iso_date(said, sent, split):
    body = {"customer_id": "c_1", "product_id": "p1", "amount": 420, "date": said}
    assert pre(PROMISE_PRE, body, split)[0]["date"] == sent


# --- add_note -----------------------------------------------------------------------------------

NOTE_POST = POST["note_post"]


def test_note_success_and_failure(split):
    ok = what(post(NOTE_POST, envelope({"ok": "true"}), split))
    assert ok.startswith("Note saved.")
    assert "transition_to_ev_" not in ok  # render.py builds no ev_done exit; name none
    # The notes-done route (92b83b5) closes the call on the last note's result. Diff review 2:
    # "say goodbye and call the matching ENDING" after an early note ended multi-product calls
    # with products still open. Now: go on with an open product; never be empty (90b737d stall).
    assert "do not say goodbye" in ok and "closes by itself" in ok
    assert "Never reply with an empty message" in ok
    bad = what(post(NOTE_POST, envelope({"ok": False, "error": "unknown product"}), split))
    assert bad == "The note was NOT saved (bank error: unknown product). Do not say it was saved."
    down = what(post(NOTE_POST, copy.deepcopy(SERVER_ERROR), split))
    assert down == "The note was NOT saved. Do not say it was saved."


# --- schedule_callback --------------------------------------------------------------------------

CALLBACK_PRE = PRE["callback_pre"]
CALLBACK_POST = POST["callback_post"]
BOOKED_TAIL = (
    " Thank the person, say goodbye and call transition_to_ev_not_reached_callback in the same "
    "message, with no other tool."
)


@pytest.mark.parametrize(
    "said, sent",
    [
        ("11", "11:00"),
        ("11am", "11:00"),
        ("11 AM", "11:00"),
        ("11.00", "11:00"),
        ("11:00", "11:00"),
        ("11:00:00", "11:00"),
        ("2pm", "14:00"),
        ("2:30 pm", "14:30"),
        ("2 p.m.", "14:00"),
        ("12pm", "12:00"),
        ("12am", "00:00"),
        ("1430", "14:30"),
        ("930", "09:30"),
        ("9", "09:00"),
        ("noon", "12:00"),
        ("7 in the evening", "19:00"),
        ("10 in the morning", "10:00"),
        ("whenever", "whenever"),
        ("25:00", "25:00"),
    ],
)
def test_callback_pre_time_becomes_hh_mm(said, sent, split):
    body = {"customer_id": "c_1", "date": "2026-10-15", "time": said}
    assert pre(CALLBACK_PRE, body, split)[0]["time"] == sent


def test_callback_pre_pads_the_date_and_remembers_the_booking(split):
    vs = {}
    body = {"customer_id": "c_1", "date": "2026-10-5", "time": "11am"}
    out, vs = pre(CALLBACK_PRE, body, split, vs)
    assert out == {"customer_id": "c_1", "date": "2026-10-05", "time": "11:00"}
    assert vs == {"hook_callback_date": "2026-10-05", "hook_callback_time": "11:00"}


def test_callback_pre_then_post_reads_back_the_booking(split):
    vs = {}
    pre(CALLBACK_PRE, {"customer_id": "c_1", "date": "2026-10-15", "time": "11"}, split, vs)
    result = post(CALLBACK_POST, envelope({"ok": True}), split, vs)
    assert what(result) == "Booked for 2026-10-15 11:00." + BOOKED_TAIL


def test_callback_success_without_vars(split):
    assert what(post(CALLBACK_POST, envelope({"ok": True}), split)) == "Booked." + BOOKED_TAIL


@pytest.mark.parametrize(
    "result, text",
    [
        (
            envelope({"ok": False, "error": "outside callback window"}),
            "The callback was NOT booked (bank error: outside callback window). "
            "Do not say it was booked; follow the brief.",
        ),
        (SERVER_ERROR, "The callback was NOT booked. Do not say it was booked; follow the brief."),
    ],
)
def test_callback_failure_is_not_booked(result, text, split):
    vs = {"hook_callback_date": "2026-10-15", "hook_callback_time": "11:00"}
    assert what(post(CALLBACK_POST, copy.deepcopy(result), split, vs)) == text


# --- review regressions (each was a failing case against the first version) --------------------


def test_contract_signatures_take_the_exit_rows_from_the_spec():
    # docs/design.md §9 lists verify_post(spec) and callback_post(spec).
    assert hooks.verify_post(SPEC) == hooks.verify_post(SPEC, FAILED_ROW)
    assert hooks.callback_post(SPEC) == hooks.callback_post(SPEC, CALLBACK_ROW)


@pytest.mark.parametrize(
    "said",
    ["quarter past 11", "half past 2", "2 thirty pm", "quarter to 3", "10 to 3", "11 or 12"],
)
def test_callback_pre_leaves_a_time_alone_when_words_change_its_meaning(said, split):
    body = {"customer_id": "c_1", "date": "2026-10-15", "time": said}
    assert pre(CALLBACK_PRE, body, split)[0]["time"] == said


@pytest.mark.parametrize(
    "said, sent",
    [
        ("2", "14:00"),
        ("2:30", "14:30"),
        ("7", "19:00"),
        ("11", "11:00"),
        ("9", "09:00"),
        ("2 am", "02:00"),
        ("7 in the morning", "07:00"),
        ("2 p.m. tomorrow", "14:00"),
        ("11 o'clock", "11:00"),
        ("around 3 this afternoon", "15:00"),
    ],
)
def test_callback_pre_reads_a_bare_hour_inside_the_callback_window(said, sent, split):
    body = {"customer_id": "c_1", "date": "2026-10-15", "time": said}
    assert pre(CALLBACK_PRE, body, split)[0]["time"] == sent


def test_callback_pre_window_comes_from_the_spec(split):
    spec = copy.deepcopy(SPEC)
    spec["callback"]["start"], spec["callback"]["end"] = "08:00", "12:00"
    src = hooks.callback_pre(spec)
    assert pre(src, {"time": "9"}, split)[0]["time"] == "09:00"
    spec["callback"]["start"], spec["callback"]["end"] = "garbage", ""
    assert pre(hooks.callback_pre(spec), {"time": "2"}, split)[0]["time"] == "02:00"


@pytest.mark.parametrize(
    "said, sent",
    [
        ("4 4 seven one", "4471"),
        ("zero 3 5 8", "0358"),
        ("my number ends four four seven one", "4471"),
        ("my last four digits are 4471", "4471"),
        ("44 seventy one", "44 seventy one"),
        ("double four seven one", "double four seven one"),
    ],
)
def test_verify_pre_digits_never_drop_spoken_digits(said, sent, split):
    assert verify_answer("phone_last4", said, split) == sent


@pytest.mark.parametrize("amount", ["420 and 50 cents", "between 100 and 200", "1 250", "3 x 100"])
def test_promise_pre_leaves_an_amount_with_several_numbers_alone(amount, split):
    body = {"customer_id": "c_1", "product_id": "p1", "amount": amount, "date": "2026-10-16"}
    assert pre(PROMISE_PRE, body, split)[0]["amount"] == amount


@pytest.mark.parametrize(
    "amount, sent", [("EUR 420,50", 420.5), ("-12.5", -12.5), ("420.50 euros.", 420.5)]
)
def test_promise_pre_parses_one_number_with_text_around_it(amount, sent, split):
    body = {"customer_id": "c_1", "product_id": "p1", "amount": amount, "date": "2026-10-16"}
    assert pre(PROMISE_PRE, body, split)[0]["amount"] == sent


def test_verify_pre_keeps_the_json_type_of_numbers(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["question_field"] = ""
    spec["identity"]["answer_field"] = ""
    spec["identity"]["questions"] = [
        {"key": "birth_year", "ask": "Year of birth?", "format": "year"},
        {"key": "pin", "ask": "PIN?", "format": "digits:4"},
        {"key": "code", "ask": "Code?", "format": "alnum"},
    ]
    body = {"customer_id": "c_1", "birth_year": 1988.0, "pin": 4471, "code": 7}
    out, _ = pre(hooks.verify_pre(spec), body, split)
    assert out == {"customer_id": "c_1", "birth_year": 1988, "pin": 4471, "code": 7}
    assert type(out["birth_year"]) is int and type(out["pin"]) is int


def test_verify_pre_per_answer_shape_never_touches_other_body_fields(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["questions"][1]["key"] = "customer_id"
    body = {"customer_id": "c 1 x", "field": "date_of_birth", "answer": "1988-3-14"}
    out, _ = pre(hooks.verify_pre(spec), body, split)
    assert out == {"customer_id": "c 1 x", "field": "date_of_birth", "answer": "1988-03-14"}


def test_pre_hooks_also_normalise_the_model_argument_variable(split):
    # The model fills `{{arg_<field>}}` (toolapi.model_tool); if the engine re-renders the body
    # from `vars` after the pre-hook, the cleaned value must be there too. No new keys are made.
    vs = {"arg_answer": "1988-3-4", "arg_field": "date_of_birth", "customer_id": "c_1"}
    body = {"customer_id": "c_1", "field": "date_of_birth", "answer": "1988-3-4"}
    out, vs = pre(VERIFY_PRE, body, split, vs)
    assert out["answer"] == "1988-03-04" and vs["arg_answer"] == "1988-03-04"
    assert vs["arg_field"] == "date_of_birth" and "arg_customer_id" not in vs
    vs = {"arg_time": "2pm"}
    pre(CALLBACK_PRE, {"customer_id": "c_1", "date": "2026-10-15", "time": "2pm"}, split, vs)
    assert vs["arg_time"] == "14:00" and "arg_date" not in vs


def test_arg_prefix_matches_the_model_tool_placeholders():
    import inspect

    from freya_builder.toolapi import model_tool

    assert inspect.signature(model_tool).parameters["name_prefix"].default == hooks.ARG_PREFIX


@pytest.mark.parametrize(
    "data, done",
    [
        ({"promise_id": "pr_1"}, True),
        ({}, True),
        ({"success": False}, False),
        ({"recorded": "false"}, False),
        ({"error": "date after deadline"}, False),
    ],
)
@pytest.mark.parametrize("name", ["promise_post", "note_post", "callback_post"])
def test_a_200_without_ok_follows_the_contract(name, data, done, split):
    # docs/design.md §9: failure is status_code >= 400, status != success, ok false or no data.
    text = what(post(POST[name], envelope(dict(data)), split))
    assert ("NOT" not in text) is done, text


@pytest.mark.parametrize("code", [400, 404, 422, "409"])
def test_verify_4xx_is_a_rejected_request_not_a_same_answer_retry(code, split):
    result = envelope({"detail": "answer must be text"}, status="error", code=code)
    text = what(post(VERIFY_POST, result, split))
    assert "same answer" not in text and "not checked" in text


def test_verify_4xx_with_no_answers_left_still_fails_the_check(split):
    result = envelope({"ok": False, "wrong_answers_left": 0}, status="error", code=403)
    assert what(post(VERIFY_POST, result, split)).startswith("The check has FAILED.")


@pytest.mark.parametrize("asked", ["Date_Of_Birth", "DATE_OF_BIRTH"])
def test_verify_asked_key_matches_without_case(asked, split):
    vs = {"hook_verify_question": asked}
    result = post(VERIFY_POST, envelope({"ok": True, "verified": True}), split, vs)
    assert what(result) == "Correct. Now ask: " + Q2
    assert vs["hook_verify_passed"] == "date_of_birth"


def test_verify_unknown_asked_key_never_names_a_question_already_answered(split):
    vs = {"hook_verify_question": "dob"}
    text = what(post(VERIFY_POST, envelope({"ok": True, "verified": True}), split, vs))
    assert text.startswith("Correct. Now ask the next security question that has not been")


def test_verify_failed_row_lines_are_said_when_the_failed_line_is_missing(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["failed_line"] = ""
    data = {"ok": True, "verified": False, "wrong_answers_left": 0}
    text = what(post(hooks.verify_post(spec), envelope(data), split))
    for line in next(r for r in SPEC["rows"] if r["id"] == FAILED_ROW)["say_before_end"]:
        assert line in text
    assert "transition_to_ev_not_verified_failed" in text


def test_verify_failed_row_outside_the_identity_step_names_no_missing_tool(split):
    spec = copy.deepcopy(SPEC)
    next(r for r in spec["rows"] if r["id"] == FAILED_ROW)["phases"] = ["opening"]
    data = {"ok": True, "verified": False, "wrong_answers_left": 0}
    text = what(post(hooks.verify_post(spec), envelope(data), split))
    assert text.startswith("The check has FAILED.") and "transition_to_" not in text


GARBAGE = [
    None,
    True,
    False,
    0,
    1,
    -1,
    3.5,
    float("nan"),
    "",
    " ",
    "true",
    "False",
    "0",
    "x",
    [],
    ["a", 1],
    {"k": None},
    b"\x00",
]


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_fuzz_hooks_never_raise_and_always_answer(name, split):
    src = SOURCES[name]
    for g in GARBAGE:
        vs = {k: g for k in hooks.HOOK_VARS}
        vs.update({"arg_answer": g, "arg_time": g, "arg_amount": g})
        if name.endswith("_post"):
            for data in (
                g,
                {
                    "ok": g,
                    "verified": g,
                    "all_verified": g,
                    "wrong_answers_left": g,
                    "hint": g,
                    "error": g,
                },
            ):
                result = {"status": g, "status_code": g, "data": data, "header": g}
                post(src, result, split, dict(vs))
                assert isinstance(what(result), str) and what(result)
        else:
            body = {
                "customer_id": "c_1",
                "field": g,
                "answer": g,
                "date": g,
                "time": g,
                "amount": g,
                "date_of_birth": g,
                "phone_last4": g,
            }
            pre(src, body, split, dict(vs))


@pytest.mark.parametrize("amount, sent", [("420,50", 420.5), (420.456, 420.46), (420, 420)])
def test_promise_pre_cleans_the_amount_argument_variable_too(amount, sent, split):
    vs = {"arg_amount": amount, "arg_date": "2026-10-6"}
    body = {"customer_id": "c_1", "product_id": "p1", "amount": amount, "date": "2026-10-6"}
    out, vs = pre(PROMISE_PRE, body, split, vs)
    assert out["amount"] == vs["arg_amount"] == pytest.approx(sent)
    assert out["date"] == vs["arg_date"] == "2026-10-06"


def test_verify_failed_without_any_brief_line_gives_an_instruction_not_a_quote(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["failed_line"] = ""
    next(r for r in spec["rows"] if r["id"] == FAILED_ROW)["say_before_end"] = []
    data = {"ok": True, "verified": False, "wrong_answers_left": 0}
    assert what(post(hooks.verify_post(spec), envelope(data), split)) == (
        "The check has FAILED. Do not state any debt or account detail. Say that you cannot "
        "verify their identity. Then thank the customer, say goodbye and call "
        "transition_to_ev_not_verified_failed in the same message, with no other tool."
    )


def test_verify_hint_without_an_instruction_still_reads_as_a_sentence(split):
    spec = copy.deepcopy(SPEC)
    spec["identity"]["hints"][0]["instruction"] = " "
    data = {"ok": True, "verified": False, "hint": "day_month_swapped", "wrong_answers_left": 2}
    assert what(post(hooks.verify_post(spec), envelope(data), split)) == (
        "Follow the brief for the bank's hint day_month_swapped. "
        "(This does not count as a wrong answer.)"
    )


def test_callback_row_lines_are_said_before_the_exit(split):
    spec = copy.deepcopy(SPEC)
    next(r for r in spec["rows"] if r["id"] == CALLBACK_ROW)["say_before_end"] = ["We will call."]
    text = what(post(hooks.callback_post(spec), envelope({"ok": True}), split))
    assert text == "Booked. Say: We will call. Then" + BOOKED_TAIL.replace(" Thank", " thank")


@pytest.mark.parametrize(
    "said, sent",
    [
        ("2026-12-31", "2026-12-31"),
        ("2027-1-1", "2027-01-01"),
        ("31/12/2026", "2026-12-31"),
        ("1 January 2027", "2027-01-01"),
        ("2028-2-29", "2028-02-29"),
        ("2026-10-31T00:00:00Z", "2026-10-31"),
        ("Sat 31 Oct 2026", "2026-10-31"),
    ],
)
def test_pre_hooks_pad_month_end_year_end_and_leap_dates(said, sent, split):
    body = {"customer_id": "c_1", "product_id": "p1", "amount": 1, "date": said}
    assert pre(PROMISE_PRE, body, split)[0]["date"] == sent
    assert pre(CALLBACK_PRE, {"date": said, "time": "11:00"}, split)[0]["date"] == sent
