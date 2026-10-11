"""Review of the general flow (adversarial check + Simulation dry run, 11 Oct): nested request
bodies, credential operations, id baking, list bodies, tool names, the opening line, a failing
re-read and short rules. Synthetic contracts from unrelated domains only."""

import copy
import io

from test_general import LIB_TOOLS, MOCK, _spec

from freya_builder import cli, contract, general, llm, pipeline
from freya_builder.contract import tools_from_operations
from freya_builder.toolapi import Field, Tool
from freya_builder.trace import Trace
from freya_builder.validate import validate


def _f(name, required=True, type_="string", enum=()):
    return {
        "name": name,
        "type": type_,
        "required": required,
        "description": "",
        "enum": list(enum),
    }


def _op(name, path, request=()):
    return {
        "name": name,
        "path": path,
        "method": "POST",
        "summary": "",
        "request": list(request),
        "response": [],
    }


def _vars(*pairs):
    return [{"name": n, "description": "", "role": r, "example": "x"} for n, r in pairs]


def test_nested_request_fields_become_flat_leaves_rebuilt_before_sending(monkeypatch):
    spec, _ = _spec(monkeypatch)
    ops = [
        _op(
            "track",
            "/parcels/track",
            [
                _f("payload", type_="object"),
                _f("meta", type_="object"),
                _f("payload.memberNumber"),
                _f("payload.flow", enum=["A", "B"]),
                _f("meta.channel", False),
            ],
        )
    ]
    tools = tools_from_operations(ops, MOCK)
    wf = pipeline.render(spec, tools)
    assert validate(wf) == []
    tool = wf["nodes"]["assist"]["tools"][0]
    body = tool["function"]["parameters"]["properties"]["body"]
    assert set(body["properties"]) == {"payload__memberNumber", "payload__flow", "meta__channel"}
    assert body["properties"]["payload__memberNumber"]["default"] == "{{memberNumber}}"
    assert body["properties"]["payload__flow"]["enum"] == ["A", "B"]
    assert "." not in str(body["required"])
    config = {
        "body": {
            "payload__memberNumber": "1234567",
            "payload__flow": "A",
            "meta__channel": "x",
            "top": 1,
        }
    }
    exec(tool["pre_process_code"], {"config": config})
    assert config["body"] == {
        "payload": {"memberNumber": "1234567", "flow": "A"},
        "meta": {"channel": "x"},
        "top": 1,
    }


def test_an_openapi_object_body_is_flattened_too():
    child = (Field("memberNumber", "string", True), Field("note", "string", False))
    t = Tool("x", MOCK + "/x", "POST", "", (Field("payload", "object", True, children=child),))
    flat, nested = general.flat_tool(t)
    assert nested and [f.name for f in flat.request] == ["payload__memberNumber", "payload__note"]


def test_credential_operations_are_not_given_to_the_agent(monkeypatch):
    spec, _ = _spec(monkeypatch)
    ops = [
        _op("token", "/oauth/token", [_f("grant_type"), _f("client_id"), _f("client_secret")]),
        _op("lookup", "/parcels/lookup", [_f("memberNumber")]),
    ]
    tools = tools_from_operations(ops, MOCK)
    kept, dropped = general.service_tools(tools)
    assert [t.name for t in dropped] == ["token"]
    names = [
        t["function"]["name"] for t in pipeline.render(spec, tools)["nodes"]["assist"]["tools"]
    ]
    assert names == ["lookup"]


def test_the_caller_id_fallback_needs_a_shared_word():
    tools = tools_from_operations(
        [
            _op("a", "/a", [_f("trackingNumber")]),
            _op("b", "/b", [_f("trackingNumber"), _f("day", False)]),
        ],
        MOCK,
    )
    assert general._bake(_vars(("accountRef", "customer_id")), tools) == {}
    tools = tools_from_operations(
        [_op("a", "/a", [_f("customerNo")]), _op("b", "/b", [_f("customerNo")]), _op("c", "/c")],
        MOCK,
    )
    assert general._bake(_vars(("customerNumber", "customer_id")), tools) == {
        "customerNo": "customerNumber"
    }


def test_only_the_callers_id_is_baked_in_any_case():
    tools = tools_from_operations([_op("book", "/book", [_f("patientId"), _f("date")])], MOCK)
    got = general._bake(_vars(("PatientID", "customer_id"), ("Date", "now")), tools)
    assert got == {"patientId": "PatientID"}


def _post(data, **env):
    result = {"data": data, **env}
    exec(general.post_hook(), {"result": result})
    return result["data"]


def test_a_list_body_is_an_answer():
    got = _post([{"slot": "09:00"}], status="success", status_code=200)
    assert got["items"] == [{"slot": "09:00"}] and got["count"] == 1
    assert got["what_to_do_next"].startswith("The service answered")
    assert _post([])["what_to_do_next"].startswith("The service answered")
    assert "did NOT" in _post([], status_code=500)["what_to_do_next"]


def test_tool_names_never_collide_or_name_a_parameter():
    tools = tools_from_operations(
        [
            _op("get_status", "/v1/status"),
            _op("status", "/v1/a/info"),
            _op("other", "/v1/b/info"),
            _op("lookup", "/v1/branches/{branchId}"),
            _op("q", "/v1/--"),
        ],
        MOCK,
    )
    names = [t.name for t in general.named_by_path(tools)]
    assert len(set(names)) == len(names)
    assert "_branchId_" not in names and "__" not in names and names[3] == "lookup"


def test_an_opening_with_an_unknown_placeholder_is_cleaned(monkeypatch):
    from test_general import SETUP, _fake_llm

    setup = copy.deepcopy(SETUP)
    setup["opening_line"] = "Hello {{first_name}}, welcome."

    def fake(trace, purpose, *a, **k):
        return setup if "call setup" in purpose else _fake_llm(trace, purpose, *a, **k)

    monkeypatch.setattr(llm, "chat_json", fake)
    monkeypatch.setattr(
        general.language, "detect", lambda t, b: {"language": "English", "goodbye": "Bye."}
    )
    out = io.StringIO()
    spec = pipeline.extract(Trace(out), "brief", LIB_TOOLS)
    assert spec["general"]["opening_line"] == "Hello, welcome."
    assert "which the call does not give: removed" in out.getvalue()
    spec["general"]["opening_line"] = ""
    assist = pipeline.render(spec, LIB_TOOLS)["nodes"]["assist"]
    assert "on_enter" not in assist and validate(pipeline.render(spec, LIB_TOOLS)) == []


def test_a_failing_own_names_reading_keeps_the_role_reading(monkeypatch):
    answers = [{"operations": [_op("get_account", "/a"), _op("renew", "/b")]}]

    def fake(trace, purpose, *a, **k):
        if answers:
            return answers.pop(0)
        raise llm.LLMError("all models failed")

    monkeypatch.setattr(llm, "chat_json", fake)
    out = io.StringIO()
    tools = contract.contract_tools(Trace(out), [("c.md", "contract")], MOCK)
    assert [t.name for t in tools] == ["get_account", "renew"]
    assert "own-names reading failed" in out.getvalue()


def test_short_folder_rules_really_keep_the_full_text():
    spec = {"_consolidated_rules": "1. short", "_prompt_brief": "1. short"}
    out = io.StringIO()
    cli.folder_prompt_brief(Trace(out), spec, "FULL TEXT")
    assert spec["_prompt_brief"] == "FULL TEXT" and "keeps the full folder text" in out.getvalue()


def test_the_closing_line_of_the_rules_comes_first(monkeypatch):
    spec, _ = _spec(monkeypatch)
    prompt = pipeline.render(spec, LIB_TOOLS)["system_prompt"]
    assert "say the closing line the RULES give (if they give none, say" in prompt


def test_setup_wording_names_no_particular_document_set():
    for word in ("flow drawing", "FAQ", "meeting", "analysis", "announcement"):
        assert word not in general.SETUP_SYSTEM
