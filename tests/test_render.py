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
    body = n["close"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
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
    assert names == [f"create_promise_p{k}" for k in (1, 2, 3)] + [f"add_note_p{k}" for k in (1, 2, 3)]
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
