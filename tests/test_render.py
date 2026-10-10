import copy
import json
from pathlib import Path

from freya_builder.render import exit_tool_name, render
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
    assert tool_names(n["negotiate"]) == ["create_promise_p1"]
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
    assert "NOTES: after every product is settled and BEFORE any goodbye" in task
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
    if op == "is_not_set":
        return value is None
    raise AssertionError(op)


def _notes_spec(k: int) -> dict:
    s = copy.deepcopy(SPEC_A)
    s["notes"]["used"] = True
    s["meta"]["max_products"] = k
    return s


def _products(n: int) -> dict:
    return {f"load_account_response.data.products.{i}.product_id": f"p{i + 1}" for i in range(n)}


def test_notes_done_route_fires_only_when_every_product_is_settled_and_noted():
    # PUB-05 / PUB-12 at d46b807: goodbye said with the last add_note, then empty replies, no
    # close_call. negotiate now leaves to wrap_up on the note results themselves.
    wf = render(_notes_spec(3), TOOLS, BRIEF)
    route = wf["nodes"]["negotiate"]["transitions"][0]
    assert route["target_node"] == "wrap_up"
    assert len(route["condition"]["conditions"]) == 14  # 2*3*3 combos minus the 4 without a note
    cond = route["condition"]
    ok = {f"add_note_p{n}_response.data.ok": "true" for n in (1, 2, 3)}
    three = _products(3)
    assert _holds(cond, three | {"p1_recorded": "yes"} | {k: ok[k] for k in list(ok)[1:]})
    assert _holds(cond, three | ok)
    assert _holds(cond, _products(1) | {"add_note_p1_response.data.ok": "True"})
    assert _holds(
        cond, _products(2) | {"p1_recorded": "yes", "add_note_p2_response.data.ok": "true"}
    )
    # still open: p3 has neither a promise nor a note
    assert not _holds(cond, three | {"p1_recorded": "yes", "add_note_p2_response.data.ok": "true"})
    # promises only: the model's own goodbye and ENDING close the call as before
    assert not _holds(cond, three | {f"p{n}_recorded": "yes" for n in (1, 2, 3)})
    # a failed note does not count
    assert not _holds(cond, _products(1) | {"add_note_p1_response.data.ok": "false"})


def test_wrap_up_speaks_then_ends_through_the_default_negotiate_ending():
    wf = render(_notes_spec(3), TOOLS, BRIEF)
    wrap = wf["nodes"]["wrap_up"]
    end = f"ev_{SPEC_A['default_rows']['negotiate']}"
    assert wrap["passthrough"] is True and wrap["passthrough_default_transition"] == end
    assert wrap["on_enter"]["type"] == "llm" and "goodbye" in wrap["on_enter"]["prompt"]
    assert wrap["transitions"] == [
        {"target_node": end, "description": "always", "condition": {"operator": "always"}}
    ]
    assert end in wf["nodes"] and "tools" not in wrap
    assert validate(wf) == []


def test_no_wrap_up_without_notes():
    wf = render(SPEC_A, TOOLS, BRIEF)
    assert "wrap_up" not in wf["nodes"]
    assert all(t["target_node"] != "wrap_up" for t in wf["nodes"]["negotiate"]["transitions"])


def test_dates_resolve_weekday_phrases_before_comparing():
    # PUB-11 rep 3 at d46b807: "this Friday" (16 Oct) was answered as if it were after the
    # deadline, which is also a Friday (23 Oct); p1/p2 were recorded on the deadline.
    task = render(SPEC_A, TOOLS, BRIEF)["nodes"]["negotiate"]["task_message"]
    assert "first turn it into a calendar date with the DATE TABLE" in task
    assert "Compare dates, never weekday names" in task
