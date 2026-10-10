from pathlib import Path

from freya_builder.toolapi import engine_call, load_tool_api, model_tool, parse_tool_api

KIT_API = Path(__file__).resolve().parents[1] / "kit" / "tools" / "openapi.json"


def test_kit_tool_api_parses_all_tools():
    tools = {t.name: t for t in load_tool_api(KIT_API)}
    assert len(tools) == 7
    assert all(t.url.startswith("https://") and t.url.endswith("/" + n) for n, t in tools.items())
    assert all(t.method == "POST" for t in tools.values())
    assert all(t.field("customer_id") and t.field("customer_id").required for t in tools.values())


def test_enums_and_required_flags_come_from_the_file():
    tools = {t.name: t for t in load_tool_api(KIT_API)}
    field = tools["verify_identity"].field("field")
    assert field.enum and field.required
    reason = tools["close_call"].field("reason")
    assert reason is not None and not reason.required
    assert {f.name for f in tools["get_account"].response} >= {"ok", "products"}


SYNTHETIC = {
    "openapi": "3.0.3",
    "servers": [{"url": "https://bank.example/v9/"}],
    "components": {
        "schemas": {
            "Check": {
                "type": "object",
                "properties": {
                    "client_ref": {"type": "string"},
                    "question": {"$ref": "#/components/schemas/Question"},
                },
                "required": ["client_ref", "question"],
            },
            "Question": {"type": "string", "enum": ["postcode", "birth_year"]},
        }
    },
    "paths": {
        "/verify_identity": {
            "post": {
                "summary": "Check one answer.",
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Check"}}
                    }
                },
            }
        }
    },
}


def test_changed_fields_refs_and_server_are_read_not_assumed():
    (tool,) = parse_tool_api(SYNTHETIC)
    assert tool.url == "https://bank.example/v9/verify_identity"
    assert [f.name for f in tool.request] == ["client_ref", "question"]
    assert tool.field("question").enum == ("postcode", "birth_year")


def test_model_tool_bakes_given_fields_and_exposes_the_rest():
    (tool,) = parse_tool_api(SYNTHETIC)
    t = model_tool(tool, "CALL it every time.", baked={"client_ref": "{{customer_id}}"})
    body = t["function"]["parameters"]["properties"]["body"]
    assert body["properties"]["client_ref"] == {"type": "string", "default": "{{customer_id}}"}
    q = body["properties"]["question"]
    assert q["enum"] == ["postcode", "birth_year"] and q["default"] == "{{arg_question}}"
    assert "One of: postcode, birth_year." in q["description"]
    assert body["required"] == ["question"]
    assert t["function"]["handler"] == "__function__:api_call"


def test_engine_call_bakes_everything():
    tools = {t.name: t for t in load_tool_api(KIT_API)}
    c = engine_call(tools["close_call"], {"customer_id": "{{customer_id}}", "outcome": "paid"})
    props = c["function"]["parameters"]["properties"]["body"]["properties"]
    assert props == {
        "customer_id": {"type": "string", "default": "{{customer_id}}"},
        "outcome": {"type": "string", "default": "paid"},
    }
