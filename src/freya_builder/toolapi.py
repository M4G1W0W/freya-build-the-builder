"""Read the bank's tool API (OpenAPI 3) into plain data, and render Freya tool JSON from it.

Nothing here knows a tool or field name: every name, type, enum and URL comes from the file.
Freya tool shapes follow kit/docs/tools-and-code.md ("Tool function shape", "api_call body
field rules") and were verified in experiments/exp01_mechanics.py.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    required: bool
    description: str = ""
    enum: tuple[str, ...] = ()
    format: str = ""
    children: tuple["Field", ...] = ()  # properties of an object, or of an array's object items


@dataclass(frozen=True)
class Tool:
    name: str
    url: str
    method: str
    summary: str
    request: tuple[Field, ...]
    response: tuple[Field, ...] = field(default_factory=tuple)

    def field(self, name: str) -> Field | None:
        return next((f for f in self.request if f.name == name), None)


def _resolve(spec: dict, node: Any) -> Any:
    """Follow local $ref pointers (#/components/...)."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 20:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"only local $ref supported, got {ref}")
        node = spec
        for part in ref[2:].split("/"):
            node = node[part]
        seen += 1
    return node


def _fields(spec: dict, schema: Any, depth: int = 0) -> tuple[Field, ...]:
    schema = _resolve(spec, schema) or {}
    required = set(schema.get("required") or [])
    out = []
    for name, prop in (schema.get("properties") or {}).items():
        prop = _resolve(spec, prop) or {}
        nested = prop
        if prop.get("type") == "array":
            nested = _resolve(spec, prop.get("items") or {}) or {}
        children = (
            _fields(spec, nested, depth + 1) if depth < 4 and nested.get("properties") else ()
        )
        out.append(
            Field(
                name=name,
                type=str(prop.get("type") or "string"),
                required=name in required,
                description=str(prop.get("description") or ""),
                enum=tuple(str(v) for v in prop.get("enum") or ()),
                format=str(prop.get("format") or ""),
                children=children,
            )
        )
    return tuple(out)


def _json_schema(spec: dict, body: Any) -> Any:
    content = (_resolve(spec, body) or {}).get("content") or {}
    media = content.get("application/json") or next(iter(content.values()), {})
    return media.get("schema") or {}


def parse_tool_api(spec: dict) -> list[Tool]:
    servers = spec.get("servers") or [{}]
    base = str(servers[0].get("url") or "").rstrip("/")
    tools = []
    for path, ops in (spec.get("paths") or {}).items():
        for method, op in ops.items():
            if method.lower() not in ("post", "get", "put", "patch", "delete"):
                continue
            name = op.get("operationId") or path.strip("/").split("/")[-1]
            ok = (op.get("responses") or {}).get("200") or {}
            tools.append(
                Tool(
                    name=name,
                    url=base + path,
                    method=method.upper(),
                    summary=str(op.get("summary") or op.get("description") or ""),
                    request=_fields(spec, _json_schema(spec, op.get("requestBody") or {})),
                    response=_fields(spec, _json_schema(spec, ok)),
                )
            )
    return tools


def load_tool_api(path: str | Path) -> list[Tool]:
    return parse_tool_api(json.loads(Path(path).read_text()))


# ---- Freya JSON rendering -------------------------------------------------------------------

JSON_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def _leaf(f: Field, default: str, description: str = "") -> dict:
    leaf: dict[str, Any] = {"type": f.type if f.type in JSON_TYPES else "string"}
    # Our wording first, then the API's own (its formats are the authority: audit F05).
    api = f.description.strip()
    desc = (
        f"{description} API: {api}"
        if description and api and api not in description
        else (description or api)
    )
    if f.enum:
        desc = (desc + " " if desc else "") + "One of: " + ", ".join(f.enum) + "."
        leaf["enum"] = list(f.enum)
    if desc:
        leaf["description"] = desc
    leaf["default"] = default
    return leaf


def _request_params(tool: Tool, body_props: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "url": {"type": "string", "default": tool.url},
            "method": {"type": "string", "default": tool.method},
            "headers": {
                "type": "object",
                "properties": {"Content-Type": {"type": "string", "default": "application/json"}},
            },
            "body": {"type": "object", "properties": body_props, "required": required},
        },
    }


def model_tool(
    tool: Tool,
    description: str,
    baked: dict[str, str],
    field_descriptions: dict[str, str] | None = None,
    post_process_code: str = "",
    name_prefix: str = "arg_",
) -> dict:
    """A tool the dialogue model calls. Fields in `baked` get fixed values (e.g. "{{customer_id}}").

    Every other field is model-filled: its default is a placeholder that no variable defines
    (`{{<prefix><field>}}`), so the engine shows it to the model (kit/docs/tools-and-code.md,
    "How a parameter gets its value"). The prefix avoids clashing with a call variable of the
    same name, which would bake it.
    """
    field_descriptions = field_descriptions or {}
    props, required = {}, []
    for f in tool.request:
        if f.name in baked:
            props[f.name] = {"type": "string", "default": baked[f.name]}
            continue
        props[f.name] = _leaf(
            f, "{{" + name_prefix + f.name + "}}", field_descriptions.get(f.name, "")
        )
        if f.required:
            required.append(f.name)
    out = {
        "type": "function",
        "config": {"timeoutMs": 10000, "maxRetries": 0},
        "function": {
            "name": tool.name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": _request_params(tool, props, required),
        },
    }
    if post_process_code:
        out["post_process_code"] = post_process_code
    return out


def engine_call(tool: Tool, baked: dict[str, str], retries: int = 0) -> dict:
    """A call the workflow engine runs in `pre_actions` (no model involved). All values baked."""
    props = {name: {"type": "string", "default": value} for name, value in baked.items()}
    return {
        "type": "function",
        "config": {"timeoutMs": 10000, "maxRetries": retries},
        "function": {
            "name": tool.name,
            "handler": "__function__:api_call",
            "description": tool.summary or tool.name,
            "parameters": _request_params(tool, props, []),
        },
    }
