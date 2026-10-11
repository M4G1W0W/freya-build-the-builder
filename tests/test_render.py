import copy
import json
import re
from pathlib import Path

from freya_builder.nodes import always as nodes_always
from freya_builder.render import _complete_when, exit_tool_name, render
from freya_builder.spec import check_spec
from freya_builder.toolapi import load_tool_api
from freya_builder.validate import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())
TOOLS = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")
BRIEF = (ROOT / "kit" / "briefs" / "brief-a.md").read_text()


def tool_names(node: dict) -> list[str]:
    return [t["function"]["name"] for t in node.get("tools") or []]


def engine_names(node: dict) -> list[str]:
    return [a["function"]["name"] for a in node.get("pre_actions") or []]


def spec_ab() -> dict:
    s = copy.deepcopy(SPEC_A)
    s["meta"]["max_products"] = 3
    s["notes"]["used"] = True
    return s


def test_rendered_brief_a_passes_local_validation():
    wf = render(SPEC_A, TOOLS, BRIEF)
    assert validate(wf) == []
    assert wf["initial_node"] == "setup"
    assert "BANK BRIEF" in wf["system_prompt"] and BRIEF[:200] in wf["system_prompt"]


def test_stage_tools_are_restricted():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    assert tool_names(n["opening"]) == []
    assert tool_names(n["identity"]) == ["verify_identity"]
    assert tool_names(n["third_party"]) == ["schedule_callback"]
    assert tool_names(n["negotiate"]) == [f"create_promise_p{i}" for i in (1, 2, 3)]
    model_called = {name for node in n.values() for name in tool_names(node)}
    assert not model_called & {"get_account", "close_call", "transfer_to_agent"}


def test_engine_runs_account_transfer_and_close_in_order():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    assert engine_names(n["load_account"]) == ["get_account"]
    assert engine_names(n["xfer"]) == ["transfer_to_agent"]
    assert engine_names(n["close"]) == ["close_call"]
    assert [t["target_node"] for t in n["finalize"]["transitions"]] == ["xfer", "close"]
    assert n["xfer"]["transitions"][-1]["target_node"] == "close"
    assert n["close"]["transitions"][-1]["target_node"] == "hang_up"
    body = n["close"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"][
        "properties"
    ]
    assert body["outcome"]["default"] == "{{close_outcome}}"
    assert body["reason"]["default"] == "{{close_reason}}"
    assert body["customer_id"]["default"] == "{{customer_id}}"


def test_every_row_has_an_exit_node_and_stage_exits_match_phases():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    for row in SPEC_A["rows"]:
        assert f"ev_{row['id']}" in n
        for stage in row["phases"]:
            targets = {t["target_node"] for t in n[stage]["transitions"] if t.get("is_tool_call")}
            assert f"ev_{row['id']}" in targets, (row["id"], stage)
            assert exit_tool_name(row["id"]) in n[stage]["task_message"]


def test_identity_gate_uses_spec_field_with_both_boolean_spellings():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    gate = n["identity"]["transitions"][0]
    assert gate["target_node"] == "load_account"
    conds = gate["condition"]["conditions"]
    assert {c["operand"] for c in conds} == {"true", "True"}
    assert all(c["variable"] == "verify_identity_response.data.all_verified" for c in conds)


def test_multi_product_slots_bake_product_ids():
    s = spec_ab()
    assert check_spec(s, TOOLS) == []
    n = render(s, TOOLS, BRIEF)["nodes"]
    names = tool_names(n["negotiate"])
    assert names == [f"create_promise_p{k}" for k in (1, 2, 3)] + [
        f"add_note_p{k}" for k in (1, 2, 3)
    ]
    for tool in n["negotiate"]["tools"]:
        k = tool["function"]["name"][-1]
        body = tool["function"]["parameters"]["properties"]["body"]["properties"]
        assert body["product_id"]["default"] == "{{p" + k + "_id}}"
        assert tool["function"]["parameters"]["properties"]["url"]["default"].endswith(
            tool["function"]["name"].rsplit("_p", 1)[0]
        )
    assert validate(render(s, TOOLS, BRIEF)) == []


def test_render_is_deterministic():
    a = json.dumps(render(SPEC_A, TOOLS, BRIEF), sort_keys=True)
    b = json.dumps(render(copy.deepcopy(SPEC_A), TOOLS, BRIEF), sort_keys=True)
    assert a == b


def test_sandbox_runs_are_minimised():
    """Every sandbox run returns ALL variables and large outputs were seen truncated on the
    platform (2026-10-10): no pre-hooks, and endings before negotiation use no code node."""
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    for node in n.values():
        for tool in node.get("tools") or []:
            assert "pre_process_code" not in tool, node["name"]
    for row in SPEC_A["rows"]:
        ev = n[f"ev_{row['id']}"]
        if "negotiate" in row["phases"]:
            assert ev["node_type"] == "code"
        else:
            assert ev["node_type"] == "api_request", row["id"]
            calls = engine_names(ev) + (
                engine_names(n[f"cl_{row['id']}"]) if f"cl_{row['id']}" in n else []
            )
            assert calls[-1] == "close_call"
            body = (n.get(f"cl_{row['id']}") or ev)["pre_actions"][0]["function"]["parameters"][
                "properties"
            ]["body"]["properties"]
            assert body["outcome"]["default"] == row["outcome"]
            assert ("reason" in body) == bool(row["reason"])


def test_turn_caps_end_on_the_stage_default_row():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    for stage, rid in SPEC_A["default_rows"].items():
        assert n[stage]["max_turn_transition"] == f"ev_{rid}"


def test_negotiate_states_the_attempt_procedure_and_read_back_honesty():
    # PUB-12 (3-rep runs at 78994a2 and 90b737d): with correct per-product facts the model still
    # offered the floor after an early-band product's only attempt, and once made no attempt at all.
    # It also read back "I have recorded ..." before create_promise ran.
    task = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "make that product's NEXT listed attempt" in task
    assert "never skip one, never add one" in task
    assert "(not even the floor)" in task
    assert 'never say "I have recorded" before the create_promise result says so' in task


def test_negotiate_has_no_attempt_procedure_without_an_attempt_plan():
    s = copy.deepcopy(SPEC_A)
    s["attempts"] = []
    task = render(s, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "ATTEMPTS:" not in task


def test_notes_come_before_the_goodbye():
    # PUB-05 on the A+B agent: "only as the very last step" led to goodbye first, add_note after,
    # then an empty reply and no close_call.
    s = copy.deepcopy(SPEC_A)
    s["notes"]["used"] = True
    task = render(s, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "After every product is settled and BEFORE any goodbye" in task
    assert "very last step" not in task


def _holds(cond: dict, vs: dict) -> bool:
    """Evaluate a rendered condition the way kit workflow-format.md describes the operators."""
    if "logic" in cond:
        parts = [_holds(c, vs) for c in cond["conditions"]]
        return any(parts) if cond["logic"] == "or" else all(parts)
    value = vs.get(cond["variable"])
    op = cond["operator"]
    if op == "equals":
        return value is not None and str(value) == str(cond["operand"])
    if op == "contains":
        return value is not None and cond["operand"].lower() in str(value).lower()
    if op == "not_equals":  # kit: the inverse of equals, so an unset variable is not equal
        return not (value is not None and str(value) == str(cond["operand"]))
    if op == "is_not_set":
        return value is None
    raise AssertionError(op)


def _notes_spec(k: int) -> dict:
    s = copy.deepcopy(SPEC_A)
    s["notes"]["used"] = True
    s["meta"]["max_products"] = k
    return s


def _products(n: int, k: int = 3) -> dict:
    """Slot ids as setup/account_facts write them: p1..pn used, the rest 'none'."""
    return {f"p{i}_id": (f"p{i}" if i <= n else "none") for i in range(1, k + 1)}


def _first_route(wf: dict, vs: dict) -> str | None:
    for tr in wf["nodes"]["negotiate"]["transitions"]:
        if "logic" in tr["condition"] and _holds(tr["condition"], vs):
            return tr["target_node"]
    return None


def test_notes_done_route_fires_only_when_every_product_is_settled_and_noted():
    # PUB-05 / PUB-12 at d46b807: goodbye said with the last add_note, then empty replies, no
    # close_call. negotiate now leaves to ev_notes(_p) on the note results themselves.
    wf = render(_notes_spec(3), TOOLS, BRIEF)
    first, second = wf["nodes"]["negotiate"]["transitions"][:2]
    assert (first["target_node"], second["target_node"]) == ("ev_notes_p", "ev_notes")
    assert len(first["condition"]["conditions"]) + len(second["condition"]["conditions"]) == 11
    note = {f"add_note_p{n}_response.data.ok": "true" for n in (1, 2, 3)}
    three = _products(3)
    p1_rec_rest_noted = three | {"p1_recorded": "yes"} | {k: note[k] for k in list(note)[1:]}
    assert _first_route(wf, p1_rec_rest_noted) == "ev_notes_p"
    assert _first_route(wf, three | note) == "ev_notes"
    assert _first_route(wf, _products(1) | {"add_note_p1_response.data.ok": "True"}) == "ev_notes"
    # names of the bank's list and id fields play no part (audit F17/F41/F58)
    assert "products" not in json.dumps(wf["nodes"]["negotiate"]["transitions"][:2])
    two = _products(2) | {"p1_recorded": "yes", "add_note_p2_response.data.ok": "true"}
    assert _first_route(wf, two) == "ev_notes_p"
    # still open: p3 has neither a promise nor a note
    still_open = three | {"p1_recorded": "yes", "add_note_p2_response.data.ok": "true"}
    assert _first_route(wf, still_open) is None
    # promises only: the model's own goodbye and ENDING close the call as before
    assert _first_route(wf, three | {f"p{n}_recorded": "yes" for n in (1, 2, 3)}) is None
    # a failed note does not count
    assert _first_route(wf, _products(1) | {"add_note_p1_response.data.ok": "false"}) is None


def test_ev_notes_speak_fixed_closings_then_end_through_the_default_negotiate_event():
    # 1bc0c1d rep 3: an llm entry line was blocked and a Turkish filler was spoken; 52b947c: when
    # the setup sandbox run failed, "{{closing_text}}" was read out literally. Fixed text only.
    wf = render(_notes_spec(3), TOOLS, BRIEF)
    default = wf["nodes"][f"ev_{SPEC_A['default_rows']['negotiate']}"]
    line = SPEC_A["success_lines"]["promise"]
    for name, text in (
        ("ev_notes_p", f"{line} Thank you for your time. Goodbye."),
        ("ev_notes", "Thank you for your time. Goodbye."),
    ):
        ev = wf["nodes"][name]
        assert ev["node_type"] == "code" and ev["passthrough"] is True
        assert ev["on_enter"] == {"type": "tts", "text": text} and "{{" not in text
        assert ev["transitions"] == [
            {
                "target_node": "finalize",
                "description": "always",
                "condition": {"operator": "always"},
            }
        ]
        # the same event as the default ending (its auto-notes are moot: every product is settled)
        vs, dvs = {}, {}
        exec(_code(ev), {"vars": vs})
        exec(_code(default), {"vars": dvs})
        assert vs["end_event"] == dvs["end_event"] == SPEC_A["default_rows"]["negotiate"]
    assert validate(wf) == []


def test_no_notes_route_without_notes():
    wf = render(SPEC_A, TOOLS, BRIEF)
    assert not {"ev_notes", "ev_notes_p"} & set(wf["nodes"])
    assert all(
        not t["target_node"].startswith("ev_notes") for t in wf["nodes"]["negotiate"]["transitions"]
    )


def test_dates_resolve_weekday_phrases_before_comparing():
    # PUB-11 rep 3 at d46b807: "this Friday" (16 Oct) was answered as if it were after the
    # deadline, which is also a Friday (23 Oct); p1/p2 were recorded on the deadline.
    task = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "first turn it into a calendar date with the DATE TABLE" in task
    assert "Compare dates, never weekday names" in task


def test_attempts_never_re_ask_today_and_carry_the_listed_date():
    # PUB-06 (A+B agent, 52b947c rep 3): after "too much" the floor was offered for today, then
    # again for Friday (judged as two floor offers). X-B2: "today" re-asked for a single product.
    task = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "never ask again whether the customer can pay today" in task
    assert "uses exactly the date listed for that attempt" in task


def test_notes_route_grows_linearly_enough_for_five_products():
    # audit F20: the old expansion was 3^K; for each product count n it is now 2^n - 1 groups
    wf = render(_notes_spec(5), TOOLS, BRIEF)
    first, second = wf["nodes"]["negotiate"]["transitions"][:2]
    assert len(first["condition"]["conditions"]) + len(second["condition"]["conditions"]) == 57
    vs = (
        _products(4, 5)
        | {"p1_recorded": "yes"}
        | {f"add_note_p{n}_response.data.ok": "true" for n in (2, 3, 4)}
    )
    assert _first_route(wf, vs) == "ev_notes_p"
    assert _first_route(wf, _products(5, 5) | {"p1_recorded": "yes"}) is None


def test_callback_prompt_follows_a_combined_date_time_field():
    # audit F04/F31/F61: variant-c has one 'when' field; the prompt said
    # "with when as YYYY-MM-DD and  as HH:MM" (an empty second field name).
    spec = copy.deepcopy(SPEC_A)
    spec["callback"]["time_field"] = ""
    task = render(spec, TOOLS, BRIEF)["nodes"]["third_party"]["task_message"]
    assert " and  as HH:MM" not in task
    assert "holding the date and the time together, exactly in this format:" in task


def test_callback_prompt_with_separate_fields_is_unchanged():
    task = render(SPEC_A, TOOLS, BRIEF)["nodes"]["third_party"]["task_message"]
    cb = SPEC_A["callback"]
    assert (
        f"with {cb['date_field']} as YYYY-MM-DD and {cb['time_field']} as HH:MM (24 hour)." in task
    )


def test_opening_only_endings_are_reachable_from_third_party():
    # audit F03: the opening routes wrong_number/deceased answers to third_party; a row the LLM
    # tagged 'opening' only had no exit there, so the call could only close as callback/no_callback.
    spec = copy.deepcopy(SPEC_A)
    for r in spec["rows"]:
        if r["id"] in ("not_reached_wrong_number", "not_reached_deceased"):
            r["phases"] = ["opening"]
    n = render(spec, TOOLS, BRIEF)["nodes"]
    targets = {t["target_node"] for t in n["third_party"]["transitions"] if t.get("is_tool_call")}
    assert {"ev_not_reached_wrong_number", "ev_not_reached_deceased"} <= targets
    assert exit_tool_name("not_reached_deceased") in n["third_party"]["task_message"]
    assert "ev_not_verified_declined" not in targets  # about the customer, not a third party


def test_model_tool_fields_keep_the_api_description():
    # audit F05: our generic wording replaced the API's (its formats are the authority).
    wf = render(SPEC_A, TOOLS, BRIEF)
    body = wf["nodes"]["identity"]["tools"][0]["function"]["parameters"]["properties"]["body"]
    desc = body["properties"][SPEC_A["identity"]["answer_field"]]["description"]
    assert desc.startswith("The customer's answer") and " API: For date_of_birth:" in desc


def _renamed_customer_api(tmp_path, new: str = "client_id"):
    api = json.loads((ROOT / "kit" / "tools" / "openapi.json").read_text())
    for op in api["paths"].values():
        schema = op["post"]["requestBody"]["content"]["application/json"]["schema"]
        schema["properties"][new] = schema["properties"].pop("customer_id")
        schema["required"] = [new if r == "customer_id" else r for r in schema.get("required", [])]
    path = tmp_path / "api.json"
    path.write_text(json.dumps(api))
    return load_tool_api(path)


def test_a_renamed_customer_id_field_is_still_baked(tmp_path):
    # audit F09/F56: the call variable stays customer_id, the API calls the field client_id.
    tools = _renamed_customer_api(tmp_path)
    assert check_spec(SPEC_A, tools) == []
    wf = render(SPEC_A, tools, BRIEF)
    dumped = json.dumps(wf)
    assert '"client_id": {"type": "string", "default": "{{customer_id}}"' in dumped or (
        '"client_id"' in dumped and "{{customer_id}}" in dumped
    )
    body = wf["nodes"]["load_account"]["pre_actions"][0]["function"]["parameters"]["properties"]
    assert "{{customer_id}}" in json.dumps(body)


def test_prompts_handle_customer_speech_styles():
    # Style sweep at 52b947c (0 sandbox errors): cut-off customer turns were taken as refusals,
    # answers in pieces re-asked whole, questions back answered by restating the question,
    # sympathy repeated, support offered for mere stress.
    wf = render(SPEC_A, TOOLS, BRIEF)
    system = wf["system_prompt"]
    assert "breaks off mid-sentence" in system
    # 276302f talkative PUB-07: "Yes, I confirm. I'm just looking" was cut off, so the yes was
    # ignored and the read-back asked 3 more times until the customer hung up. PUB-06/PUB-05: the
    # "repeat your last offer" rule for a second fragment re-offered the floor 3 times and the support
    # team twice, which the judge counts as offering again.
    assert "First read what it already says" in system
    assert "act on that part as you would on a complete message" in system
    assert (
        "Never repeat a question, an offer, an amount or a date because a message was cut off"
        in system
    )
    assert "repeat your last" not in system
    # 676e9df styled PUB-06 rep 2: the simulated customer's chatter was cut at the same point 20+
    # times; "Please go on." only invited more chatter. A second cut-off asks for a short answer.
    # 347e01d styled PUB-03 (corrects): "It is the 12th of July" (no year) came cut off twice; the
    # loop breaker skipped parts, "Please go on." x4, and the customer hung up after 13 s.
    breaker = "Sorry, your message was cut off. Could you give me the whole answer in a few words?"
    assert breaker in system and "a whole answer then replaces the parts so far" in system
    assert "to a part or to a cut-off message without a reply" in system
    nego0 = wf["nodes"]["negotiate"]["task_message"]
    assert 'but if your previous reply was already "Please go on.", use the cut-off line' in nego0
    assert "only as often as that rule says in the whole call" in system
    ident = wf["nodes"]["identity"]["task_message"]
    assert "join the parts the customer gave since the last verify_identity result" in ident
    assert "never ask the whole question again for a part" in ident
    assert "Do not repeat the security question in that message" in ident
    nego = wf["nodes"]["negotiate"]["task_message"]
    assert "a cut-off message that holds no yes, no, date or amount is no reply" in nego
    assert "uses no attempt" in nego
    assert "only after the customer has described that situation" in nego
    # Voice test 577a2cd4: "can we make it in instalments" got "would you like me to connect you
    # with restructuring?" and a "not right now"; brief A rule 41 says to transfer.
    assert "do it at once without asking whether they want it" in nego
    assert "ask first only when the rule itself says to offer it or to ask" in nego
    assert "that day lies INSIDE that period, not in a later week" in nego
    assert "period's row" not in nego  # the DATE TABLE has no period rows (exp07, c45758f)


def test_engine_calls_missing_a_required_field_are_reported(tmp_path):
    # audit F57: a hidden API adding a required field to close_call would be silently omitted.
    from freya_builder.validate import unsent_required

    assert unsent_required(render(SPEC_A, TOOLS, BRIEF), TOOLS) == []
    api = json.loads((ROOT / "kit" / "tools" / "openapi.json").read_text())
    body = api["paths"]["/close_call"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    body["properties"]["summary"] = {"type": "string"}
    body["required"] = [*body.get("required", []), "summary"]
    path = tmp_path / "api.json"
    path.write_text(json.dumps(api))
    tools = load_tool_api(path)
    found = unsent_required(render(SPEC_A, tools, BRIEF), tools)
    assert found and all(
        "close_call is sent without required field(s) ['summary']" in w for w in found
    )


def test_a_single_product_brief_still_gets_three_product_slots():
    # Review gap 2: the page says hidden-brief customers have one to three products.
    assert SPEC_A["meta"]["max_products"] == 1
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    assert tool_names(n["negotiate"]) == [f"create_promise_p{i}" for i in (1, 2, 3)]
    wide = copy.deepcopy(SPEC_A)
    wide["meta"]["max_products"] = 5
    assert len(tool_names(render(wide, TOOLS, BRIEF)["nodes"]["negotiate"])) == 5


def test_stage_caps_leave_room_for_cut_off_messages():
    # 276302f talkative PUB-02: 11 cut-off messages in 30 s used up the third_party cap of 12 and
    # closed as no_callback just before the callback time was given. Only user turns count.
    from freya_builder.render import CAPS

    assert CAPS["opening"] >= 25 and CAPS["third_party"] >= 40 and CAPS["identity"] >= 40
    assert CAPS["negotiate"] >= 120


def test_negotiate_joins_dates_and_amounts_given_in_parts():
    # 676e9df styled PUB-07 (pieces): "Monday the." then "26th." got the after-deadline answer (2 Nov)
    # instead of the holiday line (27 Oct). The page: customers say "a number said in two parts".
    nego = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "A date or an amount may come in parts over several messages" in nego
    # PUB-06 talkative, twice: "this Friday" became "Friday, October 17th" (a Friday in 2025).
    assert "never pair a weekday with a date from memory" in nego
    assert "join the parts the customer gave since your last question" in nego


NOTE_ROWS = (
    "paid",
    "no_promise_refused",
    "no_promise_hardship",
    "no_promise_dispute",
    "no_promise_service_error",
)


def test_with_notes_note_endings_stay_but_point_to_the_notes_route():
    # Styled extra-B at 676e9df: "I paid both" took the paid ending with no notes (Brief B rule 8
    # wants a note per product). Removing those endings (e233cb8) left refusals to talk, a missing
    # account and a second promise failure without an exit (diff review 3, 9, 11): they stay, and
    # their ENDINGS line points to the notes instead.
    n = render(spec_ab(), TOOLS, BRIEF)["nodes"]
    targets = {t["target_node"] for t in n["negotiate"]["transitions"] if t.get("is_tool_call")}
    nego = n["negotiate"]["task_message"]
    assert {f"ev_{rid}" for rid in NOTE_ROWS} <= targets
    for rid in NOTE_ROWS:
        line = next(x for x in nego.splitlines() if x.startswith(f"- {exit_tool_name(rid)}:"))
        assert "noted with this ending's reason automatically" in line
    assert "automatically" not in next(
        x for x in nego.splitlines() if x.startswith(f"- {exit_tool_name('promise')}:")
    )
    # Notes come last and only where the brief requires them; the duties of a situation first.
    assert "do for that product what the brief says for that ending" in nego
    assert "unless a brief rule ends the call as a refusal" in nego
    assert "go on with the next product" in nego
    assert "a product without a promise gets a note" not in nego  # diff review 4: Brief B's rule
    assert "Never add notes when the call is or must be transferred" in nego


def test_without_notes_every_negotiate_ending_stays():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    targets = {t["target_node"] for t in n["negotiate"]["transitions"] if t.get("is_tool_call")}
    assert {f"ev_{rid}" for rid in NOTE_ROWS} <= targets


def test_review_fixes_in_the_prompts():
    # Diff review at a3e6c77, after e233cb8 / 96c37ad / 557161d.
    wf = render(SPEC_A, TOOLS, BRIEF)
    system, nego = wf["system_prompt"], wf["nodes"]["negotiate"]["task_message"]
    # 6/15: one definition of a complete reply; a value that may go on is a part
    assert "A value that may still go on" in system and "is only a part" in system
    # 7: the brief's precedence before "transfer at once"
    assert "If a brief rule says another situation the customer also described comes first" in nego
    # 14: no practice-case value as the PARTS example
    assert "Monday the" not in nego and "26th" not in nego
    # 1: a spec whose rows all end with a goodbye line puts no goodbye into NOTES
    fx = ROOT / "tests" / "fixtures"
    vr = json.loads((fx / "spec_variant_r.json").read_text())
    vtools = load_tool_api(fx / "briefs" / "variant-r.openapi.json")
    vnego = render(vr, vtools, "")["nodes"]["negotiate"]["task_message"]
    notes = next(x for x in vnego.splitlines() if x.startswith("NOTES:"))
    assert "goodbye." not in notes.lower().replace("before any goodbye", "")


def test_engine_owns_its_fields_over_engine_fields():
    # Diff review 12: engine_fields were merged last and could replace the computed outcome.
    s = copy.deepcopy(SPEC_A)
    s["engine_fields"] = [{"tool": "close_call", "field": "outcome", "value": "no_promise"}]
    wf = render(s, TOOLS, BRIEF)
    close = wf["nodes"]["close"]["pre_actions"][0]["function"]["parameters"]["properties"]
    assert close["body"]["properties"]["outcome"]["default"] == "{{close_outcome}}"


def test_attempts_name_the_forbidden_today_question():
    # a8b70ea styled extra-B PUB-12 r3: "Regarding the car loan, can you make the payment of 140
    # today?" after the opening question (Brief B rule 4 forbids it); the rule alone was ignored.
    nego = render(spec_ab(), TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert 'never "can you pay <this product> today?"' in nego


def _code(node: dict) -> str:
    return node["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def _next(node: dict, vs: dict) -> str:
    for tr in node["transitions"]:
        cond = tr["condition"]
        if cond.get("operator") == "always" or ("logic" in cond and _holds(cond, vs)):
            return tr["target_node"]
    raise AssertionError("no route")


def test_a_note_ending_adds_the_missing_notes_in_code():
    # 676e9df and a8b70ea styled A-under-A+B PUB-08 (0/3 twice): "I already paid" took the paid
    # ending with no note, though Brief B rule 8 wants one per product without a promise. With
    # notes in use, a note-derived ending now notes every open product with its reason, in code.
    wf = render(_notes_spec(3), TOOLS, BRIEF)
    n = wf["nodes"]
    assert validate(wf) == []
    vs = {}
    exec(_code(n["ev_paid"]), {"vars": vs})
    assert vs == {"end_event": "paid", "autonote_reason": "paid"}
    for k in (1, 2, 3):
        call = n[f"an_{k}"]["pre_actions"][0]["function"]
        assert call["name"] == "add_note"
        body = {
            f: v["default"]
            for f, v in call["parameters"]["properties"]["body"]["properties"].items()
        }
        assert body["product_id"] == f"{{{{p{k}_id}}}}" and body["reason"] == "{{autonote_reason}}"
    # one product, nothing recorded or noted: note it, then finalize
    vs = _products(1)
    assert _next(n["ev_paid"], vs) == "an_1" and _next(n["an_1"], vs) == "finalize"
    # three products: P1 promised, P2 noted by the model, P3 open: only P3 gets a note
    vs = _products(3) | {"p1_recorded": "yes", "add_note_p2_response.data.ok": "True"}
    assert _next(n["ev_paid"], vs) == "an_3" and _next(n["an_3"], vs) == "finalize"
    # every product settled: straight to finalize
    vs = _products(2) | {"p1_recorded": "yes", "p2_recorded": "yes"}
    assert _next(n["ev_paid"], vs) == "finalize"


def test_without_notes_endings_go_straight_to_finalize():
    n = render(SPEC_A, TOOLS, BRIEF)["nodes"]
    assert n["ev_paid"]["transitions"] == [nodes_always("finalize")]
    assert not [k for k in n if k.startswith("an_")]


def test_a_named_date_is_answered_by_first_saying_it_as_written_in_facts():
    # exp07 echodate (15bcbad, PUB-07): every failing call answered "Monday the 26th" (a holiday)
    # without naming it ("The latest date I can record is ..."); every passing call began with the
    # date. Making the reply start with the date as FACTS writes it: 6 of 6 calls right (F1: 4 of 6).
    nego = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    dates = next(x for x in nego.split("\n") if x.startswith("DATES: "))
    assert (
        "When you answer a date the customer named, start your reply with that date as written in"
        ' FACTS (for example "<weekday> <day> <month> <year> is ..."), then say what its line in'
        " FACTS says." in dates
    )
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\b(January|October|November)\b", dates)


# ---- identity step v2 (docs/proposals/2026-10-11-identity-fix-v2.md §3-§4) -------------------
# M1 replay: complete answers that a full stop, a complaint or a cut-off followed were held
# (d10044ef, 79778b2e, 6902b731), and "Why do you need that?" closed as declined (68d28036).

T3 = "COMPLETE: join the parts the customer gave"
T4 = "A full year has four digits"
T5 = "An answer in letters or words (a code, a name) is complete"
T6 = "CUT-OFF: count only the customer's messages"
T7 = "If the customer says they already answered"
T2A = "Ask the questions one at a time and keep each complete answer."
T9 = "Check the security answers. CALL it once the customer has given a complete answer"
OVERRIDE = "For a date, a year or digits, these tests decide what is complete"
FX = ROOT / "tests" / "fixtures"


def _ident(wf: dict) -> str:
    return wf["nodes"]["identity"]["task_message"]


def _numbered(task: str) -> list[str]:
    return [x for x in task.splitlines() if re.match(r"\d+\. ", x)]


def _variant(name: str) -> tuple[dict, list]:
    spec = json.loads((FX / f"spec_variant_{name}.json").read_text())
    return spec, load_tool_api(FX / "briefs" / f"variant-{name}.openapi.json")


def _three_questions() -> dict:
    s = copy.deepcopy(SPEC_A)
    s["identity"]["questions"] = [
        {"key": "birth_year", "ask": "What is your year of birth?", "format": "year"},
        {"key": "postcode", "ask": "What is your postcode?", "format": "alnum"},
        {
            "key": "first_school",
            "ask": "What was the name of your first school?",
            "format": "text",
        },
    ]
    return s


def _one_question() -> dict:
    s = copy.deepcopy(SPEC_A)
    s["identity"]["questions"] = s["identity"]["questions"][:1]
    return s


def _no_explain() -> dict:
    s = copy.deepcopy(SPEC_A)
    s["identity"]["decline_explain"] = ""
    return s


def _all_at_once_tools(tmp_path) -> list:
    """verify_identity takes customer_id and one string field per question key, no field/answer."""
    api = json.loads((ROOT / "kit" / "tools" / "openapi.json").read_text())
    body = api["paths"]["/verify_identity"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    keys = [q["key"] for q in SPEC_A["identity"]["questions"]]
    body["properties"] = {"customer_id": {"type": "string"}} | {k: {"type": "string"} for k in keys}
    body["required"] = ["customer_id", *keys]
    path = tmp_path / "api.json"
    path.write_text(json.dumps(api))
    return load_tool_api(path)


def test_complete_when_parses_formats_like_the_hooks():
    # U1: lower/strip like hooks.py; digits:N only for N > 0; everything else is text.
    date = ("date", "a day, a month and a full year", "the day, the month and the year")
    year = ("year", "a full year", "the year, all four digits")
    text = ("text", "all of it", "the whole answer")
    expected = {
        "date": date,
        " Date ": date,
        "year": year,
        "digits:4": ("digits", "4 digits (or all of it, if it has letters)", "the 4 digits"),
        "DIGITS:5": ("digits", "5 digits (or all of it, if it has letters)", "the 5 digits"),
        "digits": text,
        "digits:x": text,
        "digits:0": text,
        "alnum": text,
        "text": text,
        "time": text,
        "": text,
    }
    for fmt, row in expected.items():
        assert _complete_when(fmt) == row, fmt


def test_identity_task_spec_a_states_complete_tests_and_short_asks():
    # U2
    wf = render(SPEC_A, TOOLS, BRIEF)
    task = _ident(wf)
    assert "complete when it has a day, a month and a full year" in task
    assert 'short ask: "Just the 4 digits, please."' in task
    assert T4 in task and T6 in task and T7 in task
    assert T5 not in task
    nego = wf["nodes"]["negotiate"]["task_message"]
    assert 'but if your previous reply was already "Please go on.", use the cut-off line' in nego


def test_identity_task_variant_c_year_and_five_digits():
    # U3
    spec, tools = _variant("c")
    task = _ident(render(spec, tools, ""))
    assert "a full year" in task and "5 digits" in task
    assert 'ask at once "Just the year, all four digits, please."' in task
    assert T5 not in task


def test_identity_task_three_questions_with_text_answers():
    # U4: year / alnum / text
    wf = render(_three_questions(), TOOLS, BRIEF)
    task = _ident(wf)
    assert [x[:3] for x in _numbered(task)] == ["1. ", "2. ", "3. "]
    assert "complete when it has all of it" in task
    assert T5 in task
    assert 'unless it ends on half a word or on "and", "the" or "of"' in task
    assert "A first part of a code" in task
    assert OVERRIDE in task
    assert validate(wf) == []


def test_identity_task_one_date_question():
    # U5
    wf = render(_one_question(), TOOLS, BRIEF)
    task = _ident(wf)
    assert len(_numbered(task)) == 1
    for block in (T3, T4, T6, T7):
        assert block in task
    assert T5 not in task
    assert validate(wf) == []


def test_identity_task_all_at_once_verify_identity(tmp_path):
    # U6: no question/answer field, so the per-answer CALL sentences would send a partial body.
    wf = render(SPEC_A, _all_at_once_tools(tmp_path), BRIEF)
    task = _ident(wf)
    assert T2A in task
    assert "(field date_of_birth;" in task
    assert "CALL verify_identity with it at once" not in task
    assert T7 not in task
    assert wf["nodes"]["identity"]["tools"][0]["function"]["description"].startswith(T9)
    assert validate(wf) == []
    per_answer = render(SPEC_A, TOOLS, BRIEF)["nodes"]["identity"]["tools"][0]["function"]
    assert per_answer["description"].startswith("Check one security answer.")


def test_identity_task_without_decline_explanation():
    # U7: no `say ""`, and the brief decides what declining does.
    task = _ident(render(_no_explain(), TOOLS, BRIEF))
    assert 'say ""' not in task and "explain once" not in task
    assert "do what the BANK BRIEF says for it" in task
    assert "Such questions never end the call unless another ENDING's trigger names them" in task


def test_identity_task_declining_and_resend_wording():
    # U8: declining is the brief's; why-questions get X without an ending; a value given again
    # after its result is a new answer; corrections count only before a full stop.
    task = _ident(render(SPEC_A, TOOLS, BRIEF))
    for text in (
        "is only what the BANK BRIEF and the ENDING for declining say",
        'say "These questions protect your account." without repeating',
        "is not this explanation",
        "as the brief says for that question",
        "even the same value, is a new answer: send it",
        "before any full stop",
        "replaces that part of the answer just checked",
    ):
        assert text in task, text
    assert "(why you need it, what the call is about)" not in task
    assert "Never send the same answer twice" not in task


def test_identity_variants_render_deterministically_and_validate(tmp_path):
    # U9
    cases = [
        (SPEC_A, TOOLS),
        _variant("r"),
        _variant("c"),
        (_three_questions(), TOOLS),
        (_one_question(), TOOLS),
        (SPEC_A, _all_at_once_tools(tmp_path)),
        (_no_explain(), TOOLS),
    ]
    for spec, tools in cases:
        wf = render(spec, tools, BRIEF)
        again = render(copy.deepcopy(spec), tools, BRIEF)
        assert json.dumps(wf, sort_keys=True) == json.dumps(again, sort_keys=True)
        assert validate(wf) == []
