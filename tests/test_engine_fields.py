"""Review gap 8a: the page says hidden tool APIs keep the seven tool names but "their fields and
allowed values can change". A new required field on a tool the workflow engine calls (get_account,
close_call, transfer_to_agent) used to be left out of every call, so no outcome reached the ledger."""

import copy
import json
from pathlib import Path

from freya_builder.render import render
from freya_builder.spec import check_spec
from freya_builder.toolapi import load_tool_api, parse_tool_api
from freya_builder.validate import unsent_required, validate

ROOT = Path(__file__).resolve().parents[1]
API = json.loads((ROOT / "kit" / "tools" / "openapi.json").read_text())
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())
BRIEF = (ROOT / "kit" / "briefs" / "brief-a.md").read_text()


def changed_api() -> list:
    """The kit API with one more required field on close_call and on transfer_to_agent."""
    api = copy.deepcopy(API)
    close = api["paths"]["/close_call"]["post"]["requestBody"]["content"]["application/json"]
    close["schema"]["properties"]["summary"] = {"type": "string"}
    close["schema"]["required"].append("summary")
    xfer = api["paths"]["/transfer_to_agent"]["post"]["requestBody"]["content"]["application/json"]
    xfer["schema"]["properties"]["priority"] = {"type": "string", "enum": ["normal", "urgent"]}
    xfer["schema"]["required"].append("priority")
    return parse_tool_api(api)


FILLED = [
    {"tool": "close_call", "field": "summary", "value": "{{close_outcome}} {{close_reason}}"},
    {"tool": "transfer_to_agent", "field": "priority", "value": "normal"},
]


def with_fields(fields: list[dict]) -> dict:
    spec = copy.deepcopy(SPEC_A)
    spec["engine_fields"] = copy.deepcopy(fields)
    return spec


def engine_bodies(wf: dict, tool: str) -> list[dict]:
    out = []
    for node in wf["nodes"].values():
        for action in node.get("pre_actions") or []:
            fn = action.get("function") or {}
            if fn.get("name") == tool:
                props = fn["parameters"]["properties"]["body"]["properties"]
                out.append({k: v.get("default") for k, v in props.items()})
    return out


def test_kit_api_needs_no_engine_fields():
    assert check_spec(with_fields([]), load_tool_api(ROOT / "kit" / "tools" / "openapi.json")) == []


def test_a_new_required_engine_field_is_a_spec_problem_until_filled():
    tools = changed_api()
    problems = check_spec(with_fields([]), tools)
    assert any("close_call requires 'summary'" in p for p in problems)
    assert any("transfer_to_agent requires 'priority'" in p for p in problems)
    assert check_spec(with_fields(FILLED), tools) == []


def test_engine_field_values_are_checked():
    tools = changed_api()
    bad_enum = [FILLED[0], {**FILLED[1], "value": "high"}]
    assert any("not in API enum" in p for p in check_spec(with_fields(bad_enum), tools))
    bad_var = [{**FILLED[0], "value": "{{mystery}}"}, FILLED[1]]
    assert any("{{mystery}}" in p for p in check_spec(with_fields(bad_var), tools))
    early = [*FILLED, {"tool": "get_account", "field": "customer_id", "value": "{{close_outcome}}"}]
    assert any(
        "get_account" in p and "close_outcome" in p for p in check_spec(with_fields(early), tools)
    )
    ghost = [*FILLED, {"tool": "close_call", "field": "nope", "value": "x"}]
    assert any("'nope'" in p for p in check_spec(with_fields(ghost), tools))


def test_every_engine_call_sends_the_filled_fields():
    tools = changed_api()
    wf = render(with_fields(FILLED), tools, BRIEF)
    assert validate(wf) == []
    assert unsent_required(wf, tools) == []
    closes = engine_bodies(wf, "close_call")
    assert len(closes) > 3 and all("summary" in b for b in closes)
    # the computed close keeps the runtime placeholders; endings before negotiation close with
    # literal values, so their placeholders are filled from the row at build time
    assert any(b["summary"] == "{{close_outcome}} {{close_reason}}" for b in closes)
    literal = [b for b in closes if "{{" not in b["outcome"]]
    assert literal and all("{{" not in b["summary"] for b in literal)
    assert all(b["summary"].startswith(b["outcome"]) for b in literal)
    assert all(b["priority"] == "normal" for b in engine_bodies(wf, "transfer_to_agent"))
