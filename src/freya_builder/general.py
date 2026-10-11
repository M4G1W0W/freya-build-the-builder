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
from .toolapi import Tool, model_tool
from .trace import Trace

REQUIRED = ("verify_identity", "get_account", "create_promise", "close_call")  # spec.check_spec
MIN_RULES_CHARS = 200

SETUP_SYSTEM = """You prepare a company's documents for a phone agent that answers or makes one kind of phone call, so that it can follow them. The documents may be one clean specification or raw material (e-mails, several versions of an analysis, memos, announcements, a flow drawing, FAQ, meeting notes) written at different times that do not always agree. Return:
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


def named_by_path(tools: list[Tool]) -> list[Tool]:
    """In the general flow the role names mean nothing: call each tool by its path's last segment
    (the contract's own operation name) when that is a unique identifier."""
    wanted = [re.sub(r"\W", "_", urlsplit(t.url).path.rstrip("/").split("/")[-1]) for t in tools]
    out = []
    for t, name in zip(tools, wanted, strict=True):
        ok = re.fullmatch(r"[A-Za-z_]\w{0,63}", name or "") and wanted.count(name) == 1
        out.append(dataclasses.replace(t, name=name) if ok else t)
    return out


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
    trace.step("call variables: " + ", ".join(f"{v['name']} ({v['role']})" for v in call_vars))
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
        "general": {"opening_line": out["opening_line"].strip()},
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


def post_hook() -> str:
    return hooks._post("", _POST, {k: hooks.lit(v) for k, v in POST_TEXT.items()})


def baked_fields(spec: dict, tools: list[Tool]) -> dict[str, str]:
    """Request field -> call variable: same name (any case); else, for the caller's id, the one
    field every tool requires (a renamed id, as spec.customer_field does for collections)."""
    by_lower = {v["name"].lower(): v["name"] for v in spec["meta"]["call_vars"]}
    out = {
        f.name: by_lower[f.name.lower()]
        for t in tools
        for f in t.request
        if f.name.lower() in by_lower
    }
    cid = _var(spec, "customer_id")
    if cid and cid not in out.values():
        common: set[str] | None = None
        for t in tools:
            names = {f.name for f in t.request if f.required}
            common = names if common is None else common & names
        if common and len(common) == 1:
            out[next(iter(common))] = cid
    return out


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
- To end the call: say the goodbye ("{goodbye}") and call transition_to_hang_up in the same turn. When a rule hands the call to a person, call that tool first, tell the customer, then end the call the same way.

THE CALL GIVES YOU (never ask the customer for these)
{given}

RULES
{brief_text}
"""


def render(spec: dict, tools: list[Tool], brief_text: str = "") -> dict:
    tools = named_by_path(tools)
    bake = baked_fields(spec, tools)
    post = post_hook()
    tool_defs = [
        model_tool(
            t,
            t.summary or t.name,
            {f.name: "{{" + bake[f.name] + "}}" for f in t.request if f.name in bake},
            post_process_code=post,
        )
        for t in tools
    ]
    assist = nodes.conversation(
        "assist",
        "Help the customer as the RULES say, from the first message to the goodbye.",
        [nodes.tool_transition("hang_up", "End the call after the goodbye has been said.")],
        tools=tool_defs,
        on_enter={"type": "tts", "text": spec["general"]["opening_line"]},
        first_entry_only=True,
    )
    test_vars = {v["name"]: v["example"] for v in spec["meta"]["call_vars"] if v["example"]}
    return {
        "initial_node": "assist",
        "system_prompt": system_prompt(spec, brief_text),
        "nodes": {"assist": assist, "hang_up": nodes.end_node("hang_up", "call_closed")},
        "global_nodes": {},
        "test_variables": test_vars,
    }
