"""Render a PolicySpec + tool API into a Freya workflow (docs/design.md §4 and §9).

Generic: every brief value comes from the spec, every tool shape from the tool API. Prompts are
templates filled with spec values; facts that need arithmetic come from code nodes (codegen.py).
"""

import itertools
import json
import re

from . import codegen, hooks, nodes
from .codegen import OK_FIELD
from .spec import call_var
from .toolapi import Tool, engine_call, model_tool

STAGES = ("opening", "third_party", "identity", "negotiate")
CAPS = {"opening": 8, "third_party": 12, "identity": 20, "negotiate": 60}


def _tools_by_name(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _rows_for(spec: dict, stage: str) -> list[dict]:
    return [r for r in spec["rows"] if stage in r["phases"]]


def exit_tool_name(row_id: str) -> str:
    return f"transition_to_ev_{row_id}"


def _endings_text(spec: dict, stage: str) -> str:
    lines = [
        "ENDINGS available in this step (end the call ONLY this way): say what is listed, thank the "
        "person and say goodbye, and in the SAME message call the transition tool. Never call it "
        "together with another tool."
    ]
    for r in _rows_for(spec, stage):
        say = " ".join(_quote(s) for s in r["say_before_end"])
        say = f" First say {say}." if say else ""
        lines.append(f"- {exit_tool_name(r['id'])}: {r['trigger']}.{say}")
    return "\n".join(lines)


def _notes_done_transitions(k: int, note_tool: str, with_promise: str, without: str) -> list[dict]:
    """negotiate -> ev_notes* once every product has a recorded promise or a saved note, and at
    least one note was saved. A model that says goodbye together with its last add_note call then
    returns empty replies and the call never closes (PUB-05/PUB-12 at d46b807); routing on the
    result fires before any further model turn (kit tools-and-code.md).

    Reads only our own slot ids (p<n>_id, 'none' for an unused slot: setup and account_facts write
    it, whatever the bank calls its list and id fields), the sticky recorded flag and the
    platform-set note result, so parallel add_note calls cannot race. Conditions nest one AND level
    under the top OR (kit workflow-format.md): products fill slots 1..n in order, so for each count
    n the groups are "slots 1..n each recorded or noted, at least one noted, slot n+1 unused"
    (2^(K+1) - K - 2 groups). Groups with a recorded promise go to `with_promise` (its fixed
    closing carries the brief's promise sentence), the rest to `without`.
    """
    rec = lambda i: {"variable": hooks.recorded_flag(i), "operator": "equals", "operand": "yes"}  # noqa: E731
    noted = lambda i: {  # noqa: E731
        "variable": f"{note_tool}_p{i}_response.data.{OK_FIELD}",
        "operator": "contains",
        "operand": "true",
    }
    unused = lambda i: {"variable": f"p{i}_id", "operator": "equals", "operand": "none"}  # noqa: E731
    split: dict[str, list[dict]] = {with_promise: [], without: []}
    for n in range(1, k + 1):
        tail = [unused(n + 1)] if n < k else []
        for kinds in itertools.product(("rec", "note"), repeat=n):
            if "note" not in kinds:
                continue
            conds = [rec(i + 1) if kd == "rec" else noted(i + 1) for i, kd in enumerate(kinds)]
            target = with_promise if "rec" in kinds else without
            split[target].append({"logic": "and", "conditions": conds + tail})
    return [
        {
            "target_node": target,
            "description": "Every product is settled and the notes are saved",
            "condition": {"logic": "or", "conditions": groups},
        }
        for target, groups in split.items()
        if groups
    ]


def _exit_transitions(spec: dict, stage: str) -> list[dict]:
    return [
        nodes.tool_transition(f"ev_{r['id']}", f"End the call: {r['trigger']}")
        for r in _rows_for(spec, stage)
    ]


def _bake_customer(spec: dict, tool: Tool) -> dict[str, str]:
    cid = call_var(spec, "customer_id")
    return {cid: "{{" + cid + "}}"} if cid and tool.field(cid) else {}


# ---- prompts ---------------------------------------------------------------------------------


def system_prompt(spec: dict, brief_text: str, engine_tools: list[str]) -> str:
    m = spec["meta"]
    return f"""You are {m["agent_self_description"]} ({m["bank_name"]}) on an outbound phone call. Speak English. Keep every turn to one or two short sentences.

HOW TO WORK
- Follow the BANK BRIEF below exactly. When a rule says to use a tool, call the tool: saying that you did something is not enough.
- After every tool result, obey its what_to_do_next, then speak to the customer or call the next tool. Never end a turn with nothing.
- Something happened only if its tool result says so. Never say something was recorded or booked unless the result says it was.
- Call at most one tool per message.
- If a tool result is an error saying the result could not be read or parsed, call the same tool once more with the same values.
- Never compute dates or amounts yourself. Use the FACTS and the DATE TABLE given in your current task.
- If you are asked something the brief and the facts do not answer, say that you do not have that information.
- These bank actions run automatically and are not yours to call: {", ".join(engine_tools)}.
- To end the call, use only the ENDINGS listed in your current task.

BANK BRIEF (the rules you must follow)
{brief_text}
"""


def _opening_task(spec: dict) -> str:
    o = spec["opening"]
    return f"""STEP: find out who is on the line. You know nothing about the account yet. Reveal nothing beyond the opening sentence.
{spec["stage_rules"]["opening"]}
Who counts as the customer confirming: {o["confirm_criteria"]}
Before identity is verified never say: {", ".join(o["forbidden_before_verified"])}.
No bank tool is available in this step.
{_endings_text(spec, "opening")}"""


def _third_party_task(spec: dict) -> str:
    cb = spec["callback"]
    callback = (
        f"CALLBACK: only these slots are possible:\n{{{{callback_slots}}}}\n"
        f"To book one, call schedule_callback with {cb['date_field']} as YYYY-MM-DD and "
        f"{cb['time_field']} as HH:MM (24 hour)."
        if cb["enabled"]
        else "No callback can be booked."
    )
    return f"""STEP: someone other than the customer is on the line. Never say why you are calling and never mention the account, even if they offer to pay. Never ask the security questions.
{spec["stage_rules"]["third_party"]}
{callback}
{_endings_text(spec, "third_party")}"""


def _identity_task(spec: dict) -> str:
    i = spec["identity"]
    questions = "\n".join(
        f"{n}. {q['ask']} (send {i['question_field']}={q['key']}; answer format: {q['format']})"
        for n, q in enumerate(i["questions"], 1)
    )
    return f"""STEP: verify the customer's identity. Ask the security questions one at a time, in this order:
{questions}
Whenever the customer's message contains an answer to the question you asked (even if the same message also asks something or complains), CALL verify_identity with that answer FIRST, then reply. CALL verify_identity once per complete answer, with {i["question_field"]} set to the question key and {i["answer_field"]} set to the answer in the format above. If only part of an answer was given, ask for the rest first.
Obey what_to_do_next in every verify_identity result.
If the customer does not want to answer, explain once: {_quote(i["decline_explain"])}
Never mention the debt, the product, an amount or why you are calling in this step.
{spec["stage_rules"]["identity"]}
{_endings_text(spec, "identity")}"""


def _negotiate_task(spec: dict, k: int, notes: bool) -> str:
    slots = ", ".join(f"create_promise_p{n}" for n in range(1, k + 1))
    note_line = (
        "NOTES: after every product is settled and BEFORE any goodbye, and only where the brief "
        "requires a note: call add_note_pN for that product with the reason, one per message, "
        "with no other words. When every product is settled the call moves on to its closing by "
        "itself. Never add notes when the call is transferred."
        if notes
        else "Notes are not used."
    )
    attempts_line = (
        "ATTEMPTS: persuasion attempts are counted per product, and FACTS lists each product's "
        "attempts in order. Unless a brief rule says to make no persuasion attempt, each time the "
        "customer refuses or does not answer for a product, make that product's NEXT listed attempt, "
        "with exactly its amount and date: never skip one, never add one. After a product's last "
        "listed attempt is refused, make no other offer of your own for it (not even the floor). After "
        "the opening question, never ask again whether the customer can pay today: every offer of your "
        "own uses exactly the date listed for that attempt (a floor offer after the customer said the "
        "full amount is too much is attempt 1 with the floor amount, on attempt 1's date). An amount "
        "or a date the customer proposes is not a refusal: handle it with the brief and FACTS.\n"
        if spec["attempts"]
        else ""
    )
    return f"""STEP: the customer is verified and the account is loaded (get_account already ran; never call it). You have just stated the debt.
FACTS (computed by code from the brief; use these exact values, never compute your own):
{{{{today_facts}}}}
{{{{account_facts}}}}
DATE TABLE:
{{{{date_table}}}}

Follow the brief from the first ask to the confirmation and recording.
DATES: when the customer names a date, first turn it into a calendar date with the DATE TABLE (for example "this Friday" or "next Monday"), then find that date in each product's "IF THE CUSTOMER NAMES A DATE" lines in FACTS and do exactly what they say (they already apply the brief's date rules). Compare dates, never weekday names: a deadline that falls on the same weekday is a different date. Never offer the latest date unless those lines say so.
{attempts_line}RECORDING: after the read-back and a clear yes, call the create_promise tool of each agreed product ({slots}); its product id is filled in automatically, you give the amount and the date as YYYY-MM-DD. One tool per message. In the read-back say what you WILL record; never say "I have recorded" before the create_promise result says so.
{note_line}
{spec["stage_rules"]["negotiate"]}
{_endings_text(spec, "negotiate")}"""


# ---- tools -----------------------------------------------------------------------------------


def _verify_tool(spec: dict, t: Tool) -> dict:
    i = spec["identity"]
    tool = model_tool(
        t,
        "Check one security answer. CALL it every time the customer gives a complete answer to a security question.",
        _bake_customer(spec, t),
        {
            i["question_field"]: "Which security question was answered.",
            i["answer_field"]: "The customer's answer, in the format the current step asks for.",
        },
        post_process_code=hooks.verify_post(spec, i["failed_row"]),
    )
    return tool


def _callback_tool(spec: dict, t: Tool) -> dict:
    tool = model_tool(
        t,
        "Book a callback for the customer. CALL it once the person gave a day and time inside the allowed slots.",
        _bake_customer(spec, t),
        post_process_code=hooks.callback_post(spec, spec["callback"]["booked_row"]),
    )
    return tool


def _slot_tool(
    spec: dict, t: Tool, k: int, product_field: str, desc: str, post: str, pre: str
) -> dict:
    baked = _bake_customer(spec, t) | {product_field: "{{p" + str(k) + "_id}}"}
    tool = model_tool(t, desc, baked, post_process_code=post)
    tool["function"]["name"] = f"{t.name}_p{k}"
    if pre:
        tool["pre_process_code"] = pre
    return tool


# ---- graph -----------------------------------------------------------------------------------


GOODBYE = "Thank you for your time. Goodbye."
RECORDED_DISCLOSURE = re.compile(r"\b(this|the) call is (being )?recorded\b", re.IGNORECASE)


def opening_line(spec: dict) -> str:
    """The spec's opening line, without the word 'recorded' (honesty judges read it as a claim
    that something was recorded before a tool succeeded; seen on PUB-10, 2 of 3 runs)."""
    return RECORDED_DISCLOSURE.sub("we are recording this call", spec["opening"]["line"])


def render(spec: dict, tools: list[Tool], brief_text: str = "") -> dict:
    by = _tools_by_name(tools)
    k = max(1, int(spec["meta"]["max_products"]))
    notes = bool(spec["notes"]["used"]) and "add_note" in by
    rows = {r["id"]: r for r in spec["rows"]}

    engine = ["get_account", "close_call"] + (
        ["transfer_to_agent"] if "transfer_to_agent" in by else []
    )
    wf_nodes: dict[str, dict] = {}

    wf_nodes["setup"] = nodes.code_node(
        "setup", codegen.setup_source(spec), [nodes.always("opening")]
    )

    who = {
        "name": "who_answered",
        "type": "string",
        "enum_values": ["confirmed", "someone_else", "wrong_number", "deceased"],
        "description": (
            "Who answered, judged from the latest message. confirmed: the person confirms they are the "
            f"customer ({spec['opening']['confirm_criteria']}). someone_else: another person answered. "
            "wrong_number: the number does not belong to the customer. deceased: the customer has died. "
            "Leave it empty for a greeting, a question or an unclear reply."
        ),
        "min_confidence": 0.7,
    }
    wf_nodes["opening"] = nodes.conversation(
        "opening",
        _opening_task(spec),
        [
            nodes.when_equals(
                "identity", "The customer confirmed who they are", "who_answered", ["confirmed"]
            ),
            nodes.when_equals(
                "third_party",
                "Someone other than the customer answered",
                "who_answered",
                ["someone_else", "wrong_number", "deceased"],
            ),
            *_exit_transitions(spec, "opening"),
        ],
        on_enter={"type": "tts", "text": opening_line(spec)},
        first_entry_only=True,
        extraction_schema=[who],
        max_turns=CAPS["opening"],
        max_turn_target=f"ev_{spec['default_rows']['opening']}",
    )

    tp_tools = (
        [_callback_tool(spec, by["schedule_callback"])]
        if spec["callback"]["enabled"] and "schedule_callback" in by
        else []
    )
    wf_nodes["third_party"] = nodes.conversation(
        "third_party",
        _third_party_task(spec),
        _exit_transitions(spec, "third_party"),
        tools=tp_tools,
        first_entry_only=True,
        max_turns=CAPS["third_party"],
        max_turn_target=f"ev_{spec['default_rows']['third_party']}",
    )

    gate = spec["identity"]["gate_field"]
    wf_nodes["identity"] = nodes.conversation(
        "identity",
        _identity_task(spec),
        [
            nodes.when_true(
                "load_account",
                "Both security answers are verified",
                f"verify_identity_response.data.{gate}",
            ),
            *_exit_transitions(spec, "identity"),
        ],
        tools=[_verify_tool(spec, by["verify_identity"])],
        first_entry_only=True,
        max_turns=CAPS["identity"],
        max_turn_target=f"ev_{spec['default_rows']['identity']}",
    )

    account_call = engine_call(
        by["get_account"], _bake_customer(spec, by["get_account"]), retries=2
    )
    wf_nodes["load_account"] = nodes.api_node(
        "load_account", [account_call], [nodes.always("account_facts")]
    )
    wf_nodes["load_account"]["suppress_tool_results"] = True
    wf_nodes["account_facts"] = nodes.code_node(
        "account_facts", codegen.account_source(spec), [nodes.always("negotiate")]
    )

    pf = spec["promise_fields"]["product_field"]
    neg_tools = [
        _slot_tool(
            spec,
            by["create_promise"],
            n,
            pf,
            f"Record the payment promise for product P{n} (see FACTS). CALL it only after the customer confirmed the read-back.",
            hooks.promise_post(spec, n),
            "",
        )
        for n in range(1, k + 1)
    ]
    if notes:
        nf = spec["notes"]["product_field"]
        neg_tools += [
            _slot_tool(
                spec,
                by["add_note"],
                n,
                nf,
                f"Record why product P{n} (see FACTS) ended without a promise. CALL it only as the last step.",
                hooks.note_post(spec),
                "",
            )
            for n in range(1, k + 1)
        ]
    neg_default = f"ev_{spec['default_rows']['negotiate']}"
    wrap = (
        _notes_done_transitions(k, by["add_note"].name, "ev_notes_p", "ev_notes") if notes else []
    )
    wf_nodes["negotiate"] = nodes.conversation(
        "negotiate",
        _negotiate_task(spec, k, notes),
        wrap + _exit_transitions(spec, "negotiate"),
        tools=neg_tools,
        on_enter={"type": "tts", "text": "{{disclosure_text}}"},
        first_entry_only=True,
        max_turns=CAPS["negotiate"],
        max_turn_target=neg_default,
    )
    if notes:
        # A fixed closing (no model turn: nothing to block, no empty reply; no variable, so nothing
        # unset to be read out when a sandbox run failed), then the default negotiate event;
        # finalize computes the outcome from what was recorded. The platform speaks a passthrough
        # node's line when the call ends (seen 10 Oct, 14:3x UTC).
        line = spec["success_lines"]["promise"]
        for name, text in (
            ("ev_notes_p", (line + " " + GOODBYE) if line else GOODBYE),
            ("ev_notes", GOODBYE),
        ):
            node = nodes.code_node(
                name,
                codegen.exit_source(spec["default_rows"]["negotiate"]),
                [nodes.always("finalize")],
            )
            node["on_enter"] = {"type": "tts", "text": text}
            wf_nodes[name] = node

    cf = spec["close_fields"]
    ct = by["close_call"]
    xt = by.get("transfer_to_agent")
    for rid, row in rows.items():
        if "negotiate" in row["phases"]:
            # Outcome may depend on what was recorded: a code node records the event, finalize computes.
            wf_nodes[f"ev_{rid}"] = nodes.code_node(
                f"ev_{rid}", codegen.exit_source(rid), [nodes.always("finalize")]
            )
            continue
        # Nothing can have been recorded before negotiation: close with literal values, no sandbox.
        literal = {cf["outcome_field"]: row["outcome"]}
        if row["reason"]:
            literal[cf["reason_field"]] = row["reason"]
        close_lit = engine_call(ct, _bake_customer(spec, ct) | literal, retries=1)
        if row["queue"] and xt:
            xfer_lit = engine_call(
                xt, _bake_customer(spec, xt) | {spec["transfer_field"]: row["queue"]}, retries=1
            )
            wf_nodes[f"ev_{rid}"] = nodes.api_node(
                f"ev_{rid}", [xfer_lit], [nodes.always(f"cl_{rid}")]
            )
            wf_nodes[f"cl_{rid}"] = nodes.api_node(
                f"cl_{rid}", [close_lit], [nodes.always("hang_up")]
            )
        else:
            wf_nodes[f"ev_{rid}"] = nodes.api_node(
                f"ev_{rid}", [close_lit], [nodes.always("hang_up")]
            )

    finalize_next = [nodes.always("close")]
    if "transfer_to_agent" in by:
        finalize_next.insert(
            0,
            {
                "target_node": "xfer",
                "description": "The call is transferred",
                "condition": {
                    "logic": "or",
                    "conditions": [
                        {"variable": "xfer_queue", "operator": "not_equals", "operand": "none"}
                    ],
                },
            },
        )
        xt = by["transfer_to_agent"]
        xfer_call = engine_call(
            xt, _bake_customer(spec, xt) | {spec["transfer_field"]: "{{xfer_queue}}"}, retries=1
        )
        wf_nodes["xfer"] = nodes.api_node("xfer", [xfer_call], [nodes.always("close")])
    wf_nodes["finalize"] = nodes.code_node("finalize", codegen.finalize_source(spec), finalize_next)

    close_call = engine_call(
        ct,
        _bake_customer(spec, ct)
        | {cf["outcome_field"]: "{{close_outcome}}", cf["reason_field"]: "{{close_reason}}"},
        retries=1,
    )
    wf_nodes["close"] = nodes.api_node("close", [close_call], [nodes.always("hang_up")])
    wf_nodes["hang_up"] = nodes.end_node("hang_up", "call_closed")

    test_vars = {v["name"]: v["example"] for v in spec["meta"]["call_vars"] if v["example"]}
    return {
        "initial_node": "setup",
        "system_prompt": system_prompt(spec, brief_text, engine),
        "nodes": wf_nodes,
        "global_nodes": {},
        "test_variables": test_vars,
    }
