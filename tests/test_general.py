"""The general flow (user decision D6, 11 Oct): a call the collections renderer cannot represent
builds a document-driven agent instead of failing. Synthetic library-loans reproducer (written by
the Simulation chat, unrelated to any case); the practice collections path is unchanged."""

import copy
import io
from pathlib import Path

from test_cli import API
from test_pipeline import SPEC_A, TOOLS, _FakeFreya

from freya_builder import cli, general, language, llm, pipeline
from freya_builder.contract import tools_from_operations
from freya_builder.trace import Trace
from freya_builder.validate import validate

MOCK = "https://mock.example.dev"
BRIEF = """# City Library: loans enquiry line (synthetic)
Members phone the library to ask which books they have on loan. The call passes the member
number. Variables: `memberNumber` (7 digits), `now` (call date-time,
for example 2026-10-12T10:30:00+01:00).
1. Greet: "Welcome to the City Library loans line." Do not ask who they are.
2. Call list_loans with the member number. Read each loan's title and due date, overdue first.
3. To renew a book call renew_loan with the loan id; only books that are not overdue.
4. For a librarian or a fine, call transfer_to_librarian.
5. Thank the member and say goodbye before ending the call."""
CONTRACT = """# Service contract (synthetic)
POST /api/list_loans: memberNumber (string, required) -> loans[loanId,title,dueDate,overdue]
POST /api/renew_loan: memberNumber, loanId (required) -> renewed, newDueDate, reason
POST /api/transfer_to_librarian: memberNumber (required), topic (fine|other) -> ok"""


def _field(name, required=True, enum=()):
    return {
        "name": name,
        "type": "string",
        "required": required,
        "description": "",
        "enum": list(enum),
    }


OPERATIONS = [  # a plausible role-named reading of this contract
    {
        "name": "get_account",
        "path": "/api/list_loans",
        "method": "POST",
        "summary": "List loans.",
        "request": [_field("memberNumber")],
        "response": [],
    },
    {
        "name": "renew_loan",
        "path": "/api/renew_loan",
        "method": "POST",
        "summary": "Renew a loan.",
        "request": [_field("memberNumber"), _field("loanId")],
        "response": [],
    },
    {
        "name": "transfer_to_agent",
        "path": "/api/transfer_to_librarian",
        "method": "POST",
        "summary": "Hand the call to a librarian.",
        "request": [_field("memberNumber"), _field("topic", False, ["fine", "other"])],
        "response": [],
    },
]
SETUP = {
    "bank_name": "City Library",
    "agent_self_description": "the library's phone assistant",
    "call_vars": [
        {
            "name": "memberNumber",
            "description": "the member number",
            "role": "customer_id",
            "example": "1234567",
        },
        {
            "name": "now",
            "description": "call date and time",
            "role": "now",
            "example": "2026-10-12T10:30:00+01:00",
        },
    ],
    "opening_line": "Welcome to the City Library loans line.",
    "amendments": [],
    "consolidated_rules": "1. Greet the member. " + "2. Read each loan from list_loans. " * 20,
}
LIB_TOOLS = tools_from_operations(OPERATIONS, MOCK)


def _fake_llm(trace, purpose, system, user, schema, name, **k):
    if "tool API" in purpose or "contract" in purpose:
        return {"operations": OPERATIONS}
    if "call setup" in purpose:
        return copy.deepcopy(SETUP)
    raise AssertionError(f"unexpected model call: {purpose}")


def _spec(monkeypatch, lang=None):
    monkeypatch.setattr(llm, "chat_json", _fake_llm)
    monkeypatch.setattr(
        language,
        "detect",
        lambda t, b: lang or {"language": "English", "goodbye": language.GOODBYE_EN},
    )
    out = io.StringIO()
    return pipeline.extract(Trace(out), BRIEF, LIB_TOOLS), out.getvalue()


def test_missing_roles():
    assert general.missing_roles(TOOLS) == []
    assert general.missing_roles(LIB_TOOLS) == ["verify_identity", "create_promise", "close_call"]


def test_missing_roles_switch_to_the_general_flow_without_collections_calls(monkeypatch):
    spec, trace = _spec(monkeypatch)
    assert "the tools have no verify_identity, create_promise, close_call" in trace
    assert "building a general agent" in trace
    assert spec["meta"]["call_vars"][0]["name"] == "memberNumber"
    assert spec["_prompt_brief"] == SETUP["consolidated_rules"].strip()


def test_general_workflow_validates_and_uses_every_contract_operation(monkeypatch):
    spec, _ = _spec(monkeypatch)
    wf = pipeline.render(spec, LIB_TOOLS)
    assert validate(wf) == []
    assert wf["initial_node"] == "assist"
    assist = wf["nodes"]["assist"]
    fns = {
        t["function"]["name"]: t["function"]["parameters"]["properties"] for t in assist["tools"]
    }
    assert set(fns) == {"list_loans", "renew_loan", "transfer_to_librarian"}
    assert fns["list_loans"]["url"]["default"] == MOCK + "/api/list_loans"
    body = fns["renew_loan"]["body"]["properties"]
    assert body["memberNumber"]["default"] == "{{memberNumber}}"  # given by the call: baked
    assert body["loanId"]["default"] != "{{loanId}}"  # model-filled
    assert fns["transfer_to_librarian"]["body"]["properties"]["topic"]["enum"] == ["fine", "other"]
    assert assist["on_enter"] == {"type": "tts", "text": "Welcome to the City Library loans line."}
    assert assist["transitions"][0]["target_node"] == "hang_up"
    assert wf["nodes"]["hang_up"]["node_type"] == "end_call"
    assert wf["test_variables"] == {"memberNumber": "1234567", "now": "2026-10-12T10:30:00+01:00"}
    prompt = wf["system_prompt"]
    assert "memberNumber = {{memberNumber}}" in prompt and "uses now = {{now}}" in prompt
    assert prompt.rstrip().endswith(SETUP["consolidated_rules"].strip())
    assert "Speak English." in prompt and "outbound" not in prompt


def test_general_prompt_speaks_the_call_language(monkeypatch):
    spec, _ = _spec(monkeypatch, {"language": "Spanish", "goodbye": "Gracias. Adiós."})
    prompt = pipeline.render(spec, LIB_TOOLS)["system_prompt"]
    assert prompt.startswith("You are the library's phone assistant (City Library)")
    assert "Speak Spanish" in prompt and '"Gracias. Adiós."' in prompt
    assert "the way a Spanish speaker says them" in prompt


def test_get_and_path_parameters_are_warned_not_fatal(monkeypatch):
    ops = copy.deepcopy(OPERATIONS)
    ops[0].update(method="GET", path="/api/members/{memberNumber}/loans")
    monkeypatch.setattr(llm, "chat_json", _fake_llm)
    monkeypatch.setattr(language, "detect", lambda t, b: {"language": "English", "goodbye": "Bye."})
    out = io.StringIO()
    tools = tools_from_operations(ops, MOCK)
    spec = pipeline.extract(Trace(out), BRIEF, tools)
    assert "GET with a JSON body is not covered" in out.getvalue()
    assert "keeps a path parameter" in out.getvalue()
    assert validate(pipeline.render(spec, tools)) == []


def test_the_smoke_test_runs_on_a_general_spec(monkeypatch):
    spec, _ = _spec(monkeypatch)
    fake = _FakeFreya([])
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    monkeypatch.setattr(llm, "_deadline", None)
    assert pipeline.selftest(Trace(io.StringIO()), {"workflow_id": "wf"}, spec, LIB_TOOLS) is True
    assert fake.body["customerVariables"]["memberNumber"] == "1234567"


def test_collections_specs_still_render_the_collections_flow():
    wf = pipeline.render(copy.deepcopy(SPEC_A), TOOLS)
    assert wf["initial_node"] == "setup" and "assist" not in wf["nodes"]


def test_a_folder_with_a_non_collections_contract_builds(tmp_path, monkeypatch, capsys):
    case = tmp_path / "Library"
    (case / "docs").mkdir(parents=True)
    (case / "BRIEF.md").write_text(BRIEF)
    (case / "docs" / "service-contract.md").write_text(CONTRACT)
    monkeypatch.setattr(llm, "chat_json", _fake_llm)
    monkeypatch.setattr(language, "detect", lambda t, b: {"language": "English", "goodbye": "Bye."})
    assert cli.run([str(case), MOCK, "--dry"], pipeline.extract, pipeline.render) == 0
    err = capsys.readouterr().err
    assert "building a general agent" in err and "local workflow validation: PASS" in err
    assert "END     ok=True" in err
    assert Path(API).exists()


def _post_result(data, **envelope):
    result = {"data": data, **envelope}
    exec(general.post_hook(), {"result": result})
    return result["data"]["what_to_do_next"]


def test_a_read_with_false_fields_is_done_and_errors_are_not():
    assert _post_result({"loans": [], "overdue": False}).startswith("The service answered")
    assert _post_result({"renewed": False, "ok": True}).startswith("The service answered")
    assert "did NOT do this" in _post_result({"ok": False})
    assert "did NOT do this (bank error: down)" in _post_result({"error": "down"})
    assert "did NOT do this" in _post_result({"x": 1}, status_code=503)


def test_a_renamed_id_field_is_still_baked(monkeypatch):
    spec, _ = _spec(monkeypatch)
    ops = copy.deepcopy(OPERATIONS)
    for op in ops:
        op["request"][0]["name"] = "member_no"
    tools = tools_from_operations(ops, MOCK)
    assert general.baked_fields(spec, tools) == {"member_no": "memberNumber"}
    wf = pipeline.render(spec, tools)
    body = wf["nodes"]["assist"]["tools"][0]["function"]["parameters"]["properties"]["body"]
    assert body["properties"]["member_no"]["default"] == "{{memberNumber}}"
    tools = tools_from_operations(OPERATIONS, MOCK)
    upper = copy.deepcopy(spec)
    upper["meta"]["call_vars"][0]["name"] = "MemberNumber"
    assert general.baked_fields(upper, tools) == {"memberNumber": "MemberNumber"}


def _op(name, path):
    return {
        "name": name,
        "path": path,
        "method": "POST",
        "summary": "",
        "request": [],
        "response": [],
    }


def test_a_contract_without_the_roles_is_read_again_with_its_own_names(monkeypatch):
    # A live dry run: the role reading returned 2 of 3 operations, one misnamed.
    from freya_builder import contract

    answers = [
        {"operations": [_op("get_account", "/api/list_loans"), _op("title", "/api/renew_loan")]},
        {
            "operations": [
                _op("list_loans", "/api/list_loans"),
                _op("renew_loan", "/api/renew_loan"),
                _op("transfer_to_librarian", "/api/transfer_to_librarian"),
            ]
        },
    ]
    purposes = []

    def fake(trace, purpose, *a, **k):
        purposes.append(purpose)
        return answers.pop(0)

    monkeypatch.setattr(llm, "chat_json", fake)
    out = io.StringIO()
    tools = contract.contract_tools(Trace(out), [("c.md", CONTRACT)], MOCK)
    assert [t.name for t in tools] == ["list_loans", "renew_loan", "transfer_to_librarian"]
    assert purposes[1] == "re-read the contract with its own operation names"
    assert "reading the contract with its own names" in out.getvalue()


def test_a_contract_with_every_role_is_read_once(monkeypatch):
    from freya_builder import contract

    ops = [_op(n, "/" + n) for n in general.REQUIRED]
    calls = []
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: calls.append(1) or {"operations": ops})
    tools = contract.contract_tools(Trace(io.StringIO()), [("c.md", "c")], MOCK)
    assert len(calls) == 1 and [t.name for t in tools] == list(general.REQUIRED)


def test_an_oversized_document_is_cut_for_the_model_but_an_openapi_file_still_parses(
    tmp_path, monkeypatch, capsys
):
    import json

    case = tmp_path / "c"
    case.mkdir()
    (case / "BRIEF.md").write_text("brief")
    (case / "records.json").write_text("[" + ",".join(['{"id": 1}'] * 20_000) + "]")
    doc = json.loads(Path(API).read_text())
    doc["info"] = {"title": "big", "description": "x" * 70_000}
    (case / "openapi.json").write_text(json.dumps(doc))
    seen = {}

    def fake(trace, purpose, *a, **k):
        raise AssertionError(f"no model call expected: {purpose}")

    monkeypatch.setattr(llm, "chat_json", fake)

    def extract(trace, text, tools):
        seen["text"], seen["tools"] = text, [t.name for t in tools]
        return {"_prompt_brief": text}

    def render(spec, tools):
        from test_cli import fake_render

        return fake_render(spec, tools)

    assert cli.run([str(case), MOCK, "--dry"], extract, render) == 0
    assert "verify_identity" in seen["tools"]  # the uncut OpenAPI file was parsed
    assert "cut by the builder" in seen["text"] and len(seen["text"]) < 3 * 60_000
    assert "records.json: " in capsys.readouterr().err
