"""Fix 1 audit (2026-10-11): an ending's "First say" list must not repeat what was said earlier.

Fixture: a fresh cand-eng.6 (a170935) --dry extraction of Brief A + B (fresh6/spec-ab4). Fix 1's
say_before_end sentence pulled mid-call lines into closing rows: transferred_support and
no_promise_hardship carry the sympathy line and "Would you like me to connect you with the customer
support team?", transferred_human carries "Can I help you first?". The ENDINGS header has the agent
say the listed sentences and call the transition in the SAME message, so they were said again
(brief A rules 32, 42: one sympathy sentence, offer once, ask once) and a question could never be
answered. Seen in 9 of 16 fresh Fix-1 extractions, 0 of 13 before Fix 1. render() now moves them to
the step's rules, said once (spec.early_lines, render._split_early_lines).
"""

import copy
import json
import re
from pathlib import Path

from freya_builder.render import _split_early_lines, render
from freya_builder.spec import early_lines
from freya_builder.toolapi import load_tool_api
from freya_builder.validate import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "tests" / "fixtures" / "fix1_audit_spec_ab4.json").read_text())
TOOLS = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")
SYMPATHY = "I am sorry to hear that."
OFFER = "Would you like me to connect you with the customer support team?"
HELP_FIRST = "Can I help you first?"
TASKS = ("opening", "third_party", "identity", "negotiate")


def _ending_lines(wf: dict, node: str) -> list[str]:
    return [x for x in wf["nodes"][node]["task_message"].splitlines() if x.startswith("- transi")]


def _first_say(line: str) -> list[str]:
    said = line.split(" First say ", 1)[1] if " First say " in line else ""
    return re.findall(r'"([^"]*)"', said)


def _row(spec: dict, row_id: str) -> dict:
    return next(r for r in spec["rows"] if r["id"] == row_id)


def test_fixture_holds_the_audit_finding():
    early = early_lines(SPEC)
    assert early == {
        "transferred_human": [HELP_FIRST],
        "transferred_support": [SYMPATHY, OFFER],
        "no_promise_hardship": [SYMPATHY, OFFER],
    }


def test_no_ending_repeats_a_question_an_offer_or_the_sympathy_line():
    wf = render(SPEC, TOOLS)
    assert validate(wf) == []
    for node in TASKS:
        for line in _ending_lines(wf, node):
            said = _first_say(line)
            assert not any(s.endswith("?") for s in said), line
            assert SYMPATHY not in said and OFFER not in said, line


def test_moved_lines_are_said_once_in_the_step_where_the_situation_comes_up():
    wf = render(SPEC, TOOLS)
    negotiate = wf["nodes"]["negotiate"]["task_message"]
    assert negotiate.count("SAID BEFORE THE CUSTOMER ANSWERS") == 1
    assert (
        f'- "{SYMPATHY}" "{OFFER}" (before transition_to_ev_transferred_support or '
        "transition_to_ev_no_promise_hardship)" in negotiate
    )
    assert f'- "{HELP_FIRST}" (before transition_to_ev_transferred_human)' in negotiate
    for node in ("opening", "identity"):
        task = wf["nodes"][node]["task_message"]
        assert f'- "{HELP_FIRST}" (before transition_to_ev_transferred_human)' in task
        assert OFFER not in task
    assert "SAID BEFORE" not in wf["nodes"]["third_party"]["task_message"]


def test_true_closing_sentences_stay_in_their_endings():
    # Fix 1's purpose: the paid sentence stays in its row; the deceased line, the failed-check line
    # and the goodbye are said at the end and are untouched.
    wf = render(SPEC, TOOLS)
    lines = {n: _ending_lines(wf, n) for n in TASKS}
    paid = next(x for x in lines["negotiate"] if "transition_to_ev_paid:" in x)
    assert _first_say(paid)[:1] == ["Payments can take one business day to appear."]
    dead = next(x for x in lines["third_party"] if "transition_to_ev_not_reached_deceased:" in x)
    assert _first_say(dead) == ["I am sorry for your loss.", "Thank you. Goodbye."]
    failed = next(x for x in lines["identity"] if "transition_to_ev_not_verified_failed:" in x)
    assert "Please use the mobile app or a branch." in _first_say(failed)
    for node in TASKS:
        assert all(_first_say(x)[-1:] == ["Thank you. Goodbye."] for x in lines[node])


def test_an_offer_said_as_a_statement_and_a_lone_sympathy_pair_are_moved_too():
    s = copy.deepcopy(SPEC)
    for rid in ("transferred_support", "no_promise_hardship"):
        _row(s, rid)["say_before_end"] = [
            SYMPATHY,
            "I can connect you with the customer support team.",
            "Thank you. Goodbye.",
        ]
    early = early_lines(s)
    assert early["no_promise_hardship"] == [
        SYMPATHY,
        "I can connect you with the customer support team.",
    ]
    for rid in ("transferred_support", "no_promise_hardship"):  # fresh6 raw1/vr1/p3b1 shape
        _row(s, rid)["say_before_end"] = [SYMPATHY, "Thank you. Goodbye."]
    assert early_lines(s)["transferred_support"] == [SYMPATHY]


def test_shared_closing_lines_are_not_moved():
    s = copy.deepcopy(SPEC)
    for r in s["rows"]:
        if r["id"] in ("transferred_support", "no_promise_hardship", "transferred_human"):
            r["say_before_end"] = ["Thank you. Goodbye."]
        if "negotiate" in r["phases"]:  # a line the brief requires at every ending of a step
            r["say_before_end"] = ["This call was recorded.", *r["say_before_end"]]
        if r["queue"]:  # a line said before every transfer
            r["say_before_end"] = ["Please hold while I transfer you.", *r["say_before_end"]]
    assert early_lines(s) == {}
    assert _split_early_lines(s) is s


def test_specs_without_early_lines_render_unchanged():
    for name in ("spec_a.json", "spec_variant_c.json", "spec_variant_r.json"):
        spec = json.loads((ROOT / "tests" / "fixtures" / name).read_text())
        assert early_lines(spec) == {}, name
        assert _split_early_lines(spec) is spec, name


def test_split_is_idempotent():
    once = _split_early_lines(SPEC)
    assert early_lines(once) == {}
    assert _split_early_lines(once) is once
    assert (
        SPEC["rows"]
        == json.loads((ROOT / "tests" / "fixtures" / "fix1_audit_spec_ab4.json").read_text())[
            "rows"
        ]
    )
