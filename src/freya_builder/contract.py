"""The tool API when the run gets a case folder and a mock URL instead of a tool API file.

Hackathon page (Submit tab): `build.py {case_folder} {mock_url}`; the agent's tools call the
team's own mock, written from the folder's service contract. An OpenAPI JSON file in the folder
is used as is; otherwise one model call reads the contract out of the documents. Either way
every tool's URL is the mock URL plus the contract's path.
"""

import json

from . import llm
from .toolapi import Field, Tool, parse_tool_api
from .trace import Trace

ROLES = (
    ("verify_identity", "check who is on the line"),
    ("get_account", "read the customer's account, debts or products"),
    ("create_promise", "record a promise to pay"),
    ("add_note", "record a note, a dispute or another remark on the account"),
    ("schedule_callback", "book a call back"),
    ("transfer_to_agent", "hand the call to a human"),
    ("close_call", "record the call's final outcome"),
)

REQUIRED = ("verify_identity", "get_account", "create_promise", "close_call")  # spec.check_spec
_INTRO = (
    "You turn a bank's service contract into the HTTP tools of a phone agent. Report only the "
    "operations the documents define. Copy every path, field name, type, enum value and required "
    "flag exactly as the contract writes them; never invent an operation or a field. "
)
_SHAPE = (
    "\npath: the operation's path below the service base URL, starting with '/'. request: the "
    "JSON body fields (for GET, the query parameters). response: the fields of a successful "
    "response body; children: the fields of an object, or of an array's items."
)
SYSTEM = (
    _INTRO
    + "Name each operation with the role name below whose purpose it serves (each role name at "
    "most once); an operation that fits no role keeps the contract's own operation name in "
    "snake_case.\n" + "\n".join(f"- {name}: {purpose}" for name, purpose in ROLES) + _SHAPE
)
# When the role reading misses a role the collections flow needs, the call is another kind of call
# (general.py): read again with the contract's own names, so no operation is forced into a role.
SYSTEM_OWN_NAMES = (
    _INTRO
    + "List EVERY operation the contract defines. Name each with the contract's own operation "
    "name in snake_case (if it has none, the last segment of its path)." + _SHAPE
)

_TYPES = ["string", "number", "integer", "boolean", "array", "object"]
_LEAF = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "type", "description"],
    "properties": {
        "name": {"type": "string"},
        "type": {"type": "string", "enum": _TYPES},
        "description": {"type": "string"},
    },
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["operations"],
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "path", "method", "summary", "request", "response"],
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "method": {"type": "string", "enum": ["POST", "GET", "PUT", "PATCH", "DELETE"]},
                    "summary": {"type": "string"},
                    "request": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "type", "required", "description", "enum"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": _TYPES},
                                "required": {"type": "boolean"},
                                "description": {"type": "string"},
                                "enum": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "response": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "type", "description", "children"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": _TYPES},
                                "description": {"type": "string"},
                                "children": {"type": "array", "items": _LEAF},
                            },
                        },
                    },
                },
            },
        }
    },
}


def is_url(arg: str) -> bool:
    return arg.lower().startswith(("http://", "https://"))


def openapi_file(files: list[tuple[str, str]]) -> tuple[str, dict] | None:
    """The first .json document in the folder that is an OpenAPI description (has `paths`)."""
    for rel, text in files:
        if not rel.lower().endswith(".json"):
            continue
        try:
            doc = json.loads(text)
        except ValueError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("paths"), dict) and doc["paths"]:
            return rel, doc
    return None


def on_mock(doc: dict, mock_url: str) -> list[Tool]:
    return parse_tool_api({**doc, "servers": [{"url": mock_url.rstrip("/")}]})


def tools_from_operations(operations: list[dict], mock_url: str) -> list[Tool]:
    base = mock_url.rstrip("/")
    tools, seen = [], set()
    for op in operations:
        name = str(op.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        path = "/" + str(op.get("path") or name).strip().lstrip("/")
        request = tuple(
            Field(
                name=str(f["name"]),
                type=str(f.get("type") or "string"),
                required=bool(f.get("required")),
                description=str(f.get("description") or ""),
                enum=tuple(str(v) for v in f.get("enum") or ()),
            )
            for f in op.get("request") or []
            if f.get("name")
        )
        response = tuple(
            Field(
                name=str(f["name"]),
                type=str(f.get("type") or "string"),
                required=False,
                description=str(f.get("description") or ""),
                children=tuple(
                    Field(
                        name=str(c["name"]),
                        type=str(c.get("type") or "string"),
                        required=False,
                        description=str(c.get("description") or ""),
                    )
                    for c in f.get("children") or []
                    if c.get("name")
                ),
            )
            for f in op.get("response") or []
            if f.get("name")
        )
        tools.append(
            Tool(
                name=name,
                url=base + path,
                method=str(op.get("method") or "POST").upper(),
                summary=str(op.get("summary") or ""),
                request=request,
                response=response,
            )
        )
    return tools


def contract_tools(trace: Trace, files: list[tuple[str, str]], mock_url: str) -> list[Tool]:
    found = openapi_file(files)
    if found:
        rel, doc = found
        tools = on_mock(doc, mock_url)
        trace.step(f"tool API from {rel} (OpenAPI), every URL on the mock: {len(tools)} tools")
    else:
        text = "\n\n".join(f"===== FILE: {rel} =====\n{body}" for rel, body in files)
        out = llm.chat_json(
            trace, "read the tool API out of the service contract", SYSTEM, text, SCHEMA, "tools"
        )
        tools = tools_from_operations(out.get("operations") or [], mock_url)
        missing = [r for r in REQUIRED if r not in {t.name for t in tools}]
        if missing:
            trace.step(
                f"no operation for {', '.join(missing)}: reading the contract with its own names"
            )
            out = llm.chat_json(
                trace,
                "re-read the contract with its own operation names",
                SYSTEM_OWN_NAMES,
                text,
                SCHEMA,
                "tools",
            )
            own = tools_from_operations(out.get("operations") or [], mock_url)
            if len(own) >= len(tools):
                tools = own
        trace.step(f"tool API read from the documents, every URL on the mock: {len(tools)} tools")
    if not tools:
        raise ValueError("no service operations found in the case folder")
    for t in tools:
        fields = ",".join(f.name for f in t.request)
        trace.step(f"tool {t.name} {t.method} {t.url} request=[{fields}]")
    return tools
