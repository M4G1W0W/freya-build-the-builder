"""A general phone agent for calls the collections flow cannot represent (user decision D6, 11 Oct).

The collections renderer needs the roles spec.check_spec lists (an identity check, an account read,
a payment promise, a closing record). When the service contract has no operation for one of them,
the builder renders this instead of failing: one conversation step that follows the documents'
consolidated rules, with every contract operation as a tool on the mock, the call's variables baked
into matching request fields, and an end step. Everything comes from the documents and the contract;
nothing here knows a case. Workflow shapes follow kit/docs/workflow-format.md and
tools-and-code.md, built with the same helpers as the collections renderer (nodes.py, toolapi.py).
"""

import dataclasses
import re
from urllib.parse import urlsplit

from . import hooks, language, llm, nodes
from .contract import REQUIRED
from .toolapi import Tool, model_tool
from .trace import Trace

MIN_RULES_CHARS = 200

SETUP_SYSTEM = """You prepare a company's documents for a phone agent that answers or makes one kind of phone call, so that it can follow them. The documents may be one clean specification or raw material of any kind (mails, memos, extracts, lists, notes) written at different times that do not always agree. Return:
- bank_name: the company's name as the documents write it.
- agent_self_description: who the agent is on the call, in a few English words (for example "the company's phone assistant").
- call_vars: every variable the call gives the agent (the documents name them, often in a list of variables or as {{name}}): its exact name, what it holds, role (customer_id = the id of the caller or customer, now = the date and time of the call, other), and an example value from the documents ("" if none).
- opening_line: the first sentence the agent says when the call starts, in the language of the call: the documents' own greeting word for word if they give one, else a short greeting naming the company.
- amendments: every change a later or more authoritative document makes to an earlier one (one line each).
- consolidated_rules: ONE complete, numbered rule list for the call as the company wants it NOW: every rule with all later or more authoritative changes applied and superseded text removed; every sentence the agent must say quoted word for word in the documents' language; every number, date, time, code, list and condition kept exactly; for each service the agent uses, when to call it, with which values, and what to do with each kind of result (an empty result, an error, each status); what the agent must never say or do; when to hand the call to a person and when to end it. Keep the order of the call. Do not invent rules and add nothing the documents do not say."""

SETUP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "bank_name",
        "agent_self_description",
        "call_vars",
        "opening_line",
        "amendments",
        "consolidated_rules",
    ],
    "properties": {
        "bank_name": {"type": "string"},
        "agent_self_description": {"type": "string"},
        "call_vars": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description", "role", "example"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "role": {"type": "string", "enum": ["customer_id", "now", "other"]},
                    "example": {"type": "string"},
                },
            },
        },
        "opening_line": {"type": "string"},
        "amendments": {"type": "array", "items": {"type": "string"}},
        "consolidated_rules": {"type": "string"},
    },
}


def missing_roles(tools: list[Tool]) -> list[str]:
    names = {t.name for t in tools}
    return [r for r in REQUIRED if r not in names]


CREDENTIAL_FIELDS = {
    "client_secret",
    "client_id",
    "grant_type",
    "password",
    "refresh_token",
    "api_key",
}
SEP = "__"  # a nested request field 'a.b' is the flat body leaf 'a__b' (kit: flat body leaves only)


def _last(name: str) -> str:
    return re.split(r"\.|__", name)[-1]


def service_tools(tools: list[Tool]) -> tuple[list[Tool], list[Tool]]:
    """(kept, dropped): an operation that takes credentials (a token endpoint) is plumbing between
    systems, not something the agent does on the call."""
    dropped = [
        t for t in tools if any(_last(f.name).lower() in CREDENTIAL_FIELDS for f in t.request)
    ]
    return [t for t in tools if t not in dropped], dropped


def _segment(t: Tool) -> str:
    seg = urlsplit(t.url).path.rstrip("/").split("/")[-1]
    name = re.sub(r"\W", "_", seg)
    if "{" in seg or not re.search("[A-Za-z]", seg) or not re.fullmatch(r"[A-Za-z_]\w{0,63}", name):
        return ""
    return name


def named_by_path(tools: list[Tool]) -> list[Tool]:
    """In the general flow the role names mean nothing: call each tool by its path's last segment
    (the contract's own operation name) when that name is unique among all final names."""
    names: list[str] = []
    for i, t in enumerate(tools):
        cand = _segment(t)
        others = [_segment(o) or o.name for j, o in enumerate(tools) if j != i]
        names.append(cand if cand and cand not in others and cand not in names else t.name)
    if len(set(names)) < len(names):
        return tools
    return [dataclasses.replace(t, name=n) for t, n in zip(tools, names, strict=True)]


def _expand(fields: tuple, prefix: str = "") -> list:
    """Object fields with children (an OpenAPI body) become dotted leaves, like the model's."""
    out = []
    for f in fields:
        name = prefix + f.name
        if f.children and f.type == "object":
            out.extend(_expand(f.children, name + "."))
        else:
            out.append(dataclasses.replace(f, name=name, children=()))
    return out


def flat_tool(t: Tool) -> tuple[Tool, bool]:
    """A tool whose request nests fields in objects: dot-free flat leaves (a__b), the bare parent
    objects dropped; NEST_PRE rebuilds the nested body before the request is sent."""
    fields = _expand(t.request)
    dotted = [f.name for f in fields if "." in f.name]
    if not dotted:
        return t, False
    parents = {n.rsplit(".", k)[0] for n in dotted for k in range(1, n.count(".") + 1)}
    leaves = tuple(
        dataclasses.replace(
            f, name=f.name.replace(".", SEP), description=f"{f.description} ({f.name})".strip()
        )
        for f in fields
        if f.name not in parents
    )
    return dataclasses.replace(t, request=leaves), True


NEST_PRE = """try:
    _b = config.get('body') if isinstance(config, dict) else None
    if isinstance(_b, dict):
        for _k in list(_b.keys()):
            if '__' in _k:
                _v = _b.pop(_k)
                _parts = _k.split('__')
                _n = _b
                for _p in _parts[:-1]:
                    if not isinstance(_n.get(_p), dict):
                        _n[_p] = dict()
                    _n = _n[_p]
                _n[_parts[-1]] = _v
except Exception:
    pass
"""


def extract(trace: Trace, brief_text: str, tools: list[Tool]) -> dict:
    lang = language.detect(trace, brief_text)
    out = llm.chat_json(
        trace,
        "read the call setup and rules (general flow)",
        SETUP_SYSTEM,
        brief_text,
        SETUP_SCHEMA,
        "call_setup",
    )
    for a in out["amendments"]:
        trace.step(f"amendment: {a[:200]}")
    call_vars = [v for v in out["call_vars"] if re.fullmatch(r"[A-Za-z_]\w*", v["name"])]
    for v in out["call_vars"]:
        if v not in call_vars:
            trace.warn(f"call variable {v['name']!r} is not a valid name: left out")
    for t in service_tools(tools)[1]:
        trace.warn(f"tool {t.name} takes credentials ({t.url}): not given to the agent")
    names = {v["name"] for v in call_vars}
    opening = out["opening_line"].strip()
    for ph in re.findall(r"\{\{\s*([^{}]*?)\s*\}\}", opening):
        if ph not in names:
            trace.warn(f"opening line names {{{{{ph}}}}}, which the call does not give: removed")
            opening = re.sub(r"\{\{\s*" + re.escape(ph) + r"\s*\}\}", "", opening)
    opening = re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s{2,}", " ", opening)).strip()
    if not opening:
        trace.warn("no opening line: the agent waits for the caller's first words")
    trace.step("call variables: " + ", ".join(f"{v['name']} ({v['role']})" for v in call_vars))
    _bake_check(call_vars, service_tools(tools)[0], trace)
    for t in tools:
        if t.method != "POST":
            trace.warn(f"tool {t.name}: {t.method} with a JSON body is not covered by the kit docs")
        if "{" in t.url:
            trace.warn(f"tool {t.name}: the URL keeps a path parameter: {t.url}")
    rules = out["consolidated_rules"].strip()
    if len(rules) < MIN_RULES_CHARS:
        trace.warn(f"consolidated rules are {len(rules)} chars: the prompt keeps the full text")
        rules = brief_text
    return {
        "general": {"opening_line": opening},
        "meta": {
            "bank_name": out["bank_name"],
            "agent_self_description": out["agent_self_description"],
            "call_vars": call_vars,
        },
        "opening": {"forbidden_before_verified": []},  # pipeline.selftest reads it
        **lang,
        "_prompt_brief": rules,
        "_consolidated_rules": rules,
    }


# A service result is NOT done only on an HTTP error, a failed status, ok false or an error text
# (hooks._ENVELOPE): unlike a collections write, a read may hold false fields (e.g. "late": false).
_POST = """
_gdone = (not _fail) and _okv is not False and not _err
if _gdone:
    _d['what_to_do_next'] = $SUCCESS
else:
    _d['what_to_do_next'] = $FAIL_HEAD + _bank + $FAIL_TAIL
"""
POST_TEXT = {
    "SUCCESS": "The service answered. Tell the customer only what this result says, as the RULES "
    "say; never add a value it does not contain. Then answer, ask or end as the RULES say.",
    "FAIL_HEAD": "The service did NOT do this",
    "FAIL_TAIL": ". Do not say it was done and do not give values you did not receive. Do what the "
    "RULES say when a service fails; if they say nothing, say you cannot do it right now.",
}


# A 200 whose body is a JSON list is an answer (an empty list too): the envelope expects a dict.
_LIST = """
_raw = result.get('data')
if isinstance(_raw, list):
    result['data'] = dict(items=_raw, count=len(_raw))
"""


def post_hook() -> str:
    return hooks._post(_LIST, _POST, {k: hooks.lit(v) for k, v in POST_TEXT.items()})


def _words(name: str) -> set[str]:
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)
    return {w.lower() for w in parts if len(w) >= 3}


def baked_fields(spec: dict, tools: list[Tool]) -> dict[str, str]:
    return _bake(spec["meta"]["call_vars"], tools)


def _bake(call_vars: list[dict], tools: list[Tool]) -> dict[str, str]:
    """Request field -> call variable. Same name (last segment of a nested field); any case only
    for the caller's id. Else the caller's id goes into the one field every tool that requires
    something requires, when that field's name shares a word with the variable's name."""
    out = {}
    for v in call_vars:
        for t in tools:
            for f in t.request:
                last = _last(f.name)
                if last == v["name"] or (
                    v["role"] == "customer_id" and last.lower() == v["name"].lower()
                ):
                    out[f.name] = v["name"]
    cid = next((v["name"] for v in call_vars if v["role"] == "customer_id"), "")
    if cid and cid not in out.values():
        common: set[str] | None = None
        for t in tools:
            names = {f.name for f in t.request if f.required}
            if names:
                common = names if common is None else common & names
        if common and len(common) == 1:
            field = next(iter(common))
            if _words(_last(field)) & _words(cid):
                out[field] = cid
    return out


def _bake_check(call_vars: list[dict], tools: list[Tool], trace: Trace) -> None:
    tools = [flat_tool(t)[0] for t in tools]
    baked = _bake(call_vars, tools)
    cid = next((v["name"] for v in call_vars if v["role"] == "customer_id"), "")
    if cid and cid not in baked.values():
        trace.warn(f"call variable {cid} matches no request field: the model fills the id fields")
    for t in tools:
        open_ = [f.name for f in t.request if f.required and f.name not in baked]
        if open_:
            trace.step(f"tool {t.name}: the model fills the required {', '.join(open_)}")


def _var(spec: dict, role: str) -> str:
    return next((v["name"] for v in spec["meta"]["call_vars"] if v["role"] == role), "")


def system_prompt(spec: dict, brief_text: str) -> str:
    m = spec["meta"]
    lang = spec.get("language")
    said = lang if lang and not language.is_english(lang) else "English"
    given = "\n".join(
        f"- {v['name']} = {{{{{v['name']}}}}} ({v['description']})" for v in m["call_vars"]
    )
    now = _var(spec, "now")
    when = f"now = {{{{{now}}}}}" if now else "the date and time of the call"
    goodbye = spec.get("goodbye") or language.GOODBYE_EN
    return f"""You are {m["agent_self_description"]} ({m["bank_name"]}) on a phone call. {language.speak_line(lang)} Keep every turn to one or two short sentences.

HOW TO WORK
- Follow the RULES below exactly, in their order. They are the company's rules for this call.
- Every fact you tell the customer (amounts, dates, statuses, names, lists) comes from a tool result in this call or from the RULES. Never invent, guess or round a value. Never say a service did something unless its result says so.
- When a rule says to use a service, call its tool: saying that you did something is not enough. One tool per message. After every tool result, speak to the customer or call the next tool; never end a turn with nothing.
- If a tool fails or returns an error, do what the RULES say for that case; if they say nothing, tell the customer you cannot do it right now and never claim it was done.
- If the customer asks for something the RULES and the tools do not cover, say that you do not have that information or cannot do that; do not make anything up.
- Every date decision (today, tomorrow, this week, due or overdue, how many days) uses {when}, never the system clock or your memory. Say dates, amounts and numbers the way a {said} speaker says them.
- If a customer message breaks off mid-sentence, reply "Please go on." and wait for the rest.
- To end the call: say the closing line the RULES give (if they give none, say "{goodbye}") and call transition_to_hang_up in the same turn. When a rule hands the call to a person, call that tool first, tell the customer, then end the call the same way.

THE CALL GIVES YOU (never ask the customer for these)
{given}

RULES
{brief_text}
"""


def render(spec: dict, tools: list[Tool], brief_text: str = "") -> dict:
    flat = [flat_tool(t) for t in named_by_path(service_tools(tools)[0])]
    tools = [t for t, _ in flat]
    bake = baked_fields(spec, tools)
    post = post_hook()
    tool_defs = []
    for t, nested in flat:
        d = model_tool(
            t,
            t.summary or t.name,
            {f.name: "{{" + bake[f.name] + "}}" for f in t.request if f.name in bake},
            post_process_code=post,
        )
        if nested:
            d["pre_process_code"] = NEST_PRE
        tool_defs.append(d)
    opening = spec["general"]["opening_line"]
    assist = nodes.conversation(
        "assist",
        "Help the customer as the RULES say, from the first message to the goodbye.",
        [nodes.tool_transition("hang_up", "End the call after the goodbye has been said.")],
        tools=tool_defs,
        on_enter={"type": "tts", "text": opening} if opening else None,
        first_entry_only=bool(opening),
    )
    test_vars = {v["name"]: v["example"] for v in spec["meta"]["call_vars"] if v["example"]}
    return {
        "initial_node": "assist",
        "system_prompt": system_prompt(spec, brief_text),
        "nodes": {"assist": assist, "hang_up": nodes.end_node("hang_up", "call_closed")},
        "global_nodes": {},
        "test_variables": test_vars,
    }
