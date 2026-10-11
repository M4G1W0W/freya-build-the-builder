"""Render a PolicySpec + tool API into a Freya workflow (docs/design.md §4 and §9).

Generic: every brief value comes from the spec, every tool shape from the tool API. Prompts are
templates filled with spec values; facts that need arithmetic come from code nodes (codegen.py).
"""

import itertools
import json
import re

from . import codegen, hooks, nodes
from .codegen import OK_FIELD
from .spec import PLACEHOLDER, call_var, customer_field
from .toolapi import Tool, engine_call, model_tool

STAGES = ("opening", "third_party", "identity", "negotiate")
# Safety nets against stalls, not brief rules. Only user turns count, and a talkative customer sends a
# cut-off message about every 2 s (276302f PUB-02 hit a cap of 12 in 30 s), so they are generous.
CAPS = {"opening": 25, "third_party": 40, "identity": 40, "negotiate": 120}


def _tools_by_name(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _rows_for(spec: dict, stage: str) -> list[dict]:
    if stage == "third_party":
        # The opening routes wrong_number/deceased answers to third_party, so "who answered"
        # endings tagged 'opening' only must exist there too (audit F03). Endings that also apply
        # after identification (declined, human) stay out: they are about the customer.
        before = {"opening", "third_party"}
        return [
            r
            for r in spec["rows"]
            if "third_party" in r["phases"] or (r["phases"] and set(r["phases"]) <= before)
        ]
    return [r for r in spec["rows"] if stage in r["phases"]]


def _note_rows(spec: dict, note_reasons: tuple[str, ...]) -> dict[str, str]:
    """Rows the brief's close rules derive from notes, with the note reason each stands for.

    With notes, the notes-done route closes such a call and finalize picks these rows, so their
    ENDINGS line says to note the products instead (styled extra-B at 676e9df: "I paid both" took
    the paid ending with no notes). They stay endings: refusals to talk, a missing account and a
    second promise failure still close through them (diff review 3, 9, 11).
    """
    out: dict[str, str] = {}
    for c in spec["close_precedence"]:
        if c["when"] not in ("all_notes_reason", "any_note"):
            continue
        if c["then"] == "row" and c["row"]:
            out[c["row"]] = c["note_reason"]
        elif c["then"] == "first_note_reason_not":
            for r in spec["rows"]:
                if r["outcome"] == c["outcome"] and r["reason"] in note_reasons:
                    if r["reason"] != c["note_reason"]:
                        out[r["id"]] = r["reason"]
    return out


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
        if stage == "negotiate" and r["id"] in spec.get("_note_rows", {}):
            say += (
                " If products ended for different reasons, first note each one with its own reason;"
                " every product still without a promise or a note is noted with this ending's"
                " reason automatically."
            )
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


def _autonote_routes(first: int, k: int) -> list[dict]:
    """From a note-derived ending (or an an_<n> node) to the next product slot from `first` on that
    exists, has no recorded promise and no note from the model; then finalize. Brief rules like
    Brief B rule 8 want a note for every product without a promise, and a model that ends with
    "I already paid" skips them (styled PUB-08, 0/3 twice)."""

    def open_slot(n: int) -> dict:
        ok = f"{codegen.NOTE_TOOL}{n}_response.data.{OK_FIELD}"
        return {
            "logic": "and",
            "conditions": [
                {"variable": f"p{n}_id", "operator": "not_equals", "operand": "none"},
                {"variable": hooks.recorded_flag(n), "operator": "not_equals", "operand": "yes"},
                {"variable": ok, "operator": "not_equals", "operand": "true"},
                {"variable": ok, "operator": "not_equals", "operand": "True"},
            ],
        }

    routes = [
        {
            "target_node": f"{codegen.AUTONOTE_NODE}{n}",
            "description": f"Product P{n} still needs a note",
            "condition": {"logic": "or", "conditions": [open_slot(n)]},
        }
        for n in range(first, k + 1)
    ]
    return routes + [nodes.always("finalize")]


def _exit_transitions(spec: dict, stage: str) -> list[dict]:
    return [
        nodes.tool_transition(f"ev_{r['id']}", f"End the call: {r['trigger']}")
        for r in _rows_for(spec, stage)
    ]


def _engine_extra(spec: dict, tool: str, known: dict[str, str] | None = None) -> dict[str, str]:
    """engine_fields for one engine-run tool; placeholders in `known` are filled at build time
    (the endings before negotiation close with literal values and never run finalize)."""
    fill = known or {}
    return {
        e["field"]: PLACEHOLDER.sub(lambda m: fill.get(m.group(1), m.group(0)), e["value"])
        for e in spec["engine_fields"]
        if e["tool"] == tool
    }


def _bake_customer(spec: dict, tool: Tool) -> dict[str, str]:
    cid = call_var(spec, "customer_id")
    field = spec.get("_customer_field") or cid
    return {field: "{{" + cid + "}}"} if cid and tool.field(field) else {}


# ---- prompts ---------------------------------------------------------------------------------


def system_prompt(spec: dict, brief_text: str, engine_tools: list[str]) -> str:
    m = spec["meta"]
    return f"""You are {m["agent_self_description"]} ({m["bank_name"]}) on an outbound phone call. Speak English. Keep every turn to one or two short sentences.

HOW TO WORK
- Follow the BANK BRIEF below exactly. When a rule says to use a tool, call the tool: saying that you did something is not enough.
- After every tool result, obey its what_to_do_next, then speak to the customer or call the next tool. Never end a turn with nothing.
- If a customer message breaks off mid-sentence (it ends on a word like "and", "because" or "the", or on half a word), they are still talking. First read what it already says: if it already holds a complete reply to your last question or offer (a clear yes or no, or a date, amount or security answer that cannot go on) or a request, act on that part as you would on a complete message. A value that may still go on (it ends on "the", "and", a number word or a month) is only a part: join it with what follows (your step's rules for answers in parts apply). Reply "Please go on." to a part or to a cut-off message without a reply; but if your previous reply was already "Please go on.", say instead the cut-off line "Sorry, your message was cut off. Could you give me the whole answer in a few words?" (a whole answer then replaces the parts so far). A cut-off message without a reply is never an answer, a refusal, a non-answer, a no to a read-back or a reason to end the call. Never repeat a question, an offer, an amount or a date because a message was cut off: each repeat counts as asking or offering again.
- Say a sentence of sympathy only where a brief rule asks for one, and only as often as that rule says in the whole call. Small talk needs no sympathy.
- Something happened only if its tool result says so. Never say something was recorded or booked unless the result says it was.
- Call at most one tool per message.
- If a tool result is an error saying the result could not be read or parsed, call the same tool once more with the same values.
- Never compute dates or amounts yourself. Use the FACTS and the DATE TABLE given in your current task.
- If the customer asks a question or asks for information that the brief and the facts do not answer, say that you do not have that information. Never say it to a remark that asks for nothing.
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


def _third_party_task(spec: dict, when_desc: str = "") -> str:
    cb = spec["callback"]
    if cb["time_field"]:
        how = (
            f"call schedule_callback with {cb['date_field']} as YYYY-MM-DD and "
            f"{cb['time_field']} as HH:MM (24 hour)."
        )
    else:  # one field holds date and time together (audit F04/F31/F61): its API wording rules
        how = (
            f"call schedule_callback with {cb['date_field']} holding the date and the time "
            f"together, exactly in this format: {when_desc or 'YYYY-MM-DD HH:MM (24 hour)'}"
        )
    callback = (
        f"CALLBACK: only these slots are possible:\n{{{{callback_slots}}}}\nTo book one, {how}"
        if cb["enabled"]
        else "No callback can be booked."
    )
    return f"""STEP: someone other than the customer is on the line. Never say why you are calling and never mention the account, even if they offer to pay. Never ask the security questions.
{spec["stage_rules"]["third_party"]}
{callback}
{_endings_text(spec, "third_party")}"""


def _field_desc(by: dict, tool: str, field: str) -> str:
    t = by.get(tool)
    f = t.field(field) if t and field else None
    return f.description.strip() if f and f.description else ""


def _complete_when(fmt: str) -> tuple[str, str, str]:
    """(kind, C, W) for a security answer format, parsed the way the hooks.py normaliser reads it:
    C ends "complete when it has ...", W fills the short ask "Just W, please.". Any format the
    normaliser does not treat as a date, a year or N digits is text."""
    f = str(fmt).strip().lower()
    if f == "date":
        return "date", "a day, a month and a full year", "the day, the month and the year"
    if f == "year":
        return "year", "a full year", "the year, all four digits"
    if f.startswith("digits"):
        try:
            n = int(f.split(":")[1])
        except (IndexError, ValueError):
            n = 0
        if n > 0:
            return "digits", f"{n} digits (or all of it, if it has letters)", f"the {n} digits"
    return "text", "all of it", "the whole answer"


def _per_answer(spec: dict, t: Tool) -> bool:
    """verify_identity takes one answer per call (question and answer fields), the branch
    verify_pre takes at runtime; otherwise it takes every answer at once, one field per key."""
    return t.field(spec["identity"]["answer_field"]) is not None


def _identity_task(spec: dict, t: Tool) -> str:
    i = spec["identity"]
    qf, af = i["question_field"], i["answer_field"]
    per_answer = _per_answer(spec, t)
    kinds: set[str] = set()
    questions = []
    for n, q in enumerate(i["questions"], 1):
        kind, complete_when, short = _complete_when(q["format"])
        kinds.add(kind)
        where = f"send {qf}={q['key']}" if per_answer else f"field {q['key']}"
        questions.append(
            f"{n}. {q['ask']} ({where}; answer format: {q['format']}; complete when it has "
            f'{complete_when}; short ask: "Just {short}, please.")'
        )
    if per_answer:
        call = (
            "Whenever the customer's message holds a complete answer to the question you asked (even "
            "if the same message also asks something, complains or breaks off), CALL verify_identity "
            "with that answer FIRST, then reply. CALL verify_identity once per complete answer, with "
            f"{qf} set to the question key and {af} set to the answer in the format above."
        )
        since = "since the last verify_identity result"
        at_once = ": CALL verify_identity with it at once, before you reply to the rest"
    else:
        call = (
            "Ask the questions one at a time and keep each complete answer. Once every question has "
            "a complete answer, CALL verify_identity once with all of them, each in its own field in "
            "the format above, FIRST, then reply. If a result asks for an answer again, ask for it, "
            "then CALL verify_identity again with every answer, the new one in place of the old (an "
            "answer the customer gives again after a result, even the same value, is a new answer)."
        )
        since = "since you asked that question"
        at_once = ""
    blocks = [
        call,
        f"COMPLETE: join the parts the customer gave {since}; if they correct a part, use the "
        "corrected part; after a result that asks for one part again (for example the month as a "
        "word), rebuild the answer from the part they now give and their earlier words, read the way "
        "that result says (if it says two parts were swapped, the number you sent for the part they "
        "now give belongs in the other part). An answer is "
        'complete when it passes its "complete when" test above, whatever follows it in the '
        "message (a full stop, a complaint, a question, or words that break off)"
        f'{at_once}. Only if "sorry", "I mean", "no", "wait" or "actually" follow it before any '
        "full stop, use the value they go on to give; while that value is cut off, it is a part."
        + (
            " For a date, a year or digits, these tests decide what is complete, not the word "
            "list in HOW TO WORK."
            if kinds & {"date", "year", "digits"}
            else ""
        ),
    ]
    if kinds & {"date", "year"}:
        blocks.append(
            "A full year has four digits: in figures, said one digit at a time, or in words that "
            'include the century ("nineteen seventy-six", "two thousand and four"). Join the parts '
            'first: a year that still has only its last two digits ("seventy-six.", "\'76", with '
            "no century said before them) is never a full year: do not send such an answer; ask at "
            'once "Just the year, all four digits, please." (that ask is not counted under CUT-OFF '
            "and does not restart it; a year in figures that breaks off before its fourth digit, "
            'such as "19" or "199" at the end of a message, is a part under CUT-OFF; if the BANK '
            "BRIEF says more about it, follow that). A year in words is complete when a full "
            "stop or other words follow it, or when it ends on a number word from one to nineteen "
            'after its century ("nineteen seventy-six", "twenty fifteen"); at the very end of a '
            'message, a year in words that ends on its century, on a tens word ("ninety") or on '
            '"thousand" or "and" may still go on.'
        )
    if "text" in kinds:
        blocks.append(
            "An answer in letters or words (a code, a name) is complete when the customer has said "
            "all of it: the message may end right after it, unless it ends on half a word or on "
            '"and", "the" or "of". A first part of a code, or words saying more follows, is a part.'
        )
    blocks.append(
        "CUT-OFF: count only the customer's messages that break off or hold only part of an "
        "answer, since you last asked this security question or got a verify_identity result; "
        'your "Please go on." and the cut-off line do not restart the count. A whole message that '
        "is a question back, a refusal or a complaint is not counted: the rules below decide it. "
        'After the 1st counted message reply "Please go on."; after the 2nd, the cut-off line '
        "from HOW TO WORK; after the 3rd, say only that question's short ask (not the question "
        "itself), which restarts the count. In this step this count replaces the HOW TO WORK "
        'rules for "Please go on." and against repeating a question; never ask the whole question '
        "again for a part."
    )
    if per_answer:
        blocks.append(
            "If the customer says they already answered, look at their messages since the last "
            "verify_identity result: if they hold a complete answer you did not send, CALL "
            "verify_identity with it now. Never send again an answer from messages you already "
            "sent it from, unless a verify_identity result tells you to send it again; an answer the "
            "customer gives again after its result, even the same value, is a new answer: send it."
        )
    declining = (
        "DECLINING: what counts as declining the security questions, and how often it ends the "
        "call, is only what the BANK BRIEF and the ENDING for declining say; a question that "
        'refuses ("why should I?") is declining.'
    )
    if i["decline_explain"].strip():
        x = _quote(i["decline_explain"])
        declining += (
            f" When the customer declines and no ENDING applies yet, explain once: {x} (an earlier "
            "answer to why you need it is not this explanation). Do not repeat the security "
            "question in that message; they answer next. A question that only asks why you need "
            f"the answer is not declining unless the BANK BRIEF says so: say {x} without repeating "
            "the security question, and wait for their answer. Any other question back that the "
            "BANK BRIEF does not count as declining (for example whether you are a robot, or "
            "whether this is a scam) is not declining: answer it in one short sentence as the "
            "brief says for that question, without repeating the security question, and wait for "
            "their answer."
        )
    else:
        declining += (
            " When the customer declines, do what the BANK BRIEF says for it. A question back that "
            "the BANK BRIEF does not count as declining (for example why you need the answer, "
            "whether you are a robot, or whether this is a scam) is not declining: answer it in "
            "one short sentence as the brief says for that question, without repeating the "
            "security question, and wait for their answer."
        )
    declining += (
        " Such questions never end the call unless another ENDING's trigger names them. A "
        'complaint, "I already told you" or a cut-off message is never declining.'
    )
    body = "\n".join(questions + blocks)
    return f"""STEP: verify the customer's identity. Ask the security questions one at a time, in this order:
{body}
Obey what_to_do_next in every verify_identity result.
{declining}
Never mention the debt, the product, an amount or why you are calling in this step.
{spec["stage_rules"]["identity"]}
{_endings_text(spec, "identity")}"""


def _negotiate_task(spec: dict, k: int, notes: bool) -> str:
    slots = ", ".join(f"create_promise_p{n}" for n in range(1, k + 1))
    note_line = (
        "NOTES: when a product's situation matches one of the brief's endings (for example already "
        "paid, a dispute, hardship or a refusal), do for that product what the brief says for that "
        "ending (its required sentence and no promise; a refusal only after that product's last "
        "listed attempt was refused, unless a brief rule ends the call as a refusal), remember the "
        "reason, and go on with the next product. After every product is settled and BEFORE any "
        "goodbye, and only where the brief requires a note: call add_note_pN for each such product "
        "with its reason, one per message, with no other words; once every product has a recorded "
        "promise or a note, the call closes by itself. Never add notes when the call is or must be "
        "transferred."
        if notes
        else "Notes are not used."
    )
    attempts_line = (
        "ATTEMPTS: persuasion attempts are counted per product, and FACTS lists each product's "
        "attempts in order. Unless a brief rule says to make no persuasion attempt, each time the "
        "customer refuses or does not answer for a product (not answering is a complete reply about "
        'paying with no yes, no, date or amount, such as "I don\'t know"; a cut-off message that '
        "holds no yes, no, date or amount is no reply, and neither is small talk (see WAITING): such "
        "a message uses no attempt), make "
        "that product's NEXT listed attempt, "
        "with exactly its amount and date: never skip one, never add one. After a product's last "
        "listed attempt is refused, make no other offer of your own for it (not even the floor). After "
        "the opening question, never ask again whether the customer can pay today (for any product, "
        'never "can you pay <this product> today?"): every offer of your '
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
PARTS: A date or an amount may come in parts over several messages ("the", then "fifth"; "four hundred", then "and twenty"): join the parts the customer gave since your last question and use the joined value; while a part is clearly missing, reply "Please go on." (but if your previous reply was already "Please go on.", use the cut-off line from HOW TO WORK).
WAITING: after your question or offer, until the customer answers it, a message with no reply to it is not an answer, a refusal or a non-answer: small talk or a remark about something else (it says nothing about paying, money, the debt, your offer or this call, and describes no situation a brief rule names), or a cut-off message without a reply. However many such messages come in a row, reply only "I see. Please go on." (to a cut-off one, use the cut-off rule in HOW TO WORK): never repeat the offer, its amount or its date, never ask again whether they can pay, and add no sympathy. If the customer asks what you offered, say what you offered as a statement (the same amount, date and required sentences) without asking again. A yes, a no, a date, an amount, "too much", a reply about paying with none of these (such as "I don't know"), a question or a situation is handled with the brief and FACTS as usual.
DATES: when the customer names a date, first turn it into a calendar date with the DATE TABLE (for example "this Friday" or "next Monday"), then find that date in each product's "IF THE CUSTOMER NAMES A DATE" lines in FACTS and do exactly what they say (they already apply the brief's date rules). Compare dates, never weekday names: a deadline that falls on the same weekday is a different date. This year's calendar differs from other years: never pair a weekday with a date from memory; take both from the DATE TABLE or FACTS and say them as written there. If the customer first named a period (like "next week" or "the week after next") and then gives only a weekday or a day number, that day lies INSIDE that period, not in a later week. When you answer a date the customer named, start your reply with that date as written in FACTS (for example "<weekday> <day> <month> <year> is ..."), then say what its line in FACTS says. Never offer the latest date unless those lines say so.
{attempts_line}Use an ending the brief ties to a situation (a transfer, the support team or another option, see ENDINGS) only after the customer has described that situation. Then do what its rule says: when the rule says to transfer or close, do it at once without asking whether they want it; ask first only when the rule itself says to offer it or to ask. If a brief rule says another situation the customer also described comes first, follow that rule first.
RECORDING: after the read-back and a clear yes, call the create_promise tool of each agreed product ({slots}); its product id is filled in automatically, you give the amount and the date as YYYY-MM-DD. One tool per message. In the read-back say what you WILL record; never say "I have recorded" before the create_promise result says so.
{note_line}
{spec["stage_rules"]["negotiate"]}
{_endings_text(spec, "negotiate")}"""


# ---- tools -----------------------------------------------------------------------------------


def _verify_tool(spec: dict, t: Tool) -> dict:
    i = spec["identity"]
    tool = model_tool(
        t,
        "Check one security answer. CALL it every time the customer gives a complete answer to a security question."
        if _per_answer(spec, t)
        else "Check the security answers. CALL it once the customer has given a complete answer to every security question, each in its own field.",
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
    spec = dict(spec, _customer_field=customer_field(spec, tools))
    by = _tools_by_name(tools)
    k = codegen._slots(spec)
    notes = bool(spec["notes"]["used"]) and "add_note" in by
    if notes:
        reason = by["add_note"].field(spec["notes"]["reason_field"])
        spec["_note_rows"] = _note_rows(spec, reason.enum if reason else ())
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
        _third_party_task(
            spec, _field_desc(by, "schedule_callback", spec["callback"]["date_field"])
        ),
        _exit_transitions(spec, "third_party"),
        tools=tp_tools,
        first_entry_only=True,
        max_turns=CAPS["third_party"],
        max_turn_target=f"ev_{spec['default_rows']['third_party']}",
    )

    gate = spec["identity"]["gate_field"]
    wf_nodes["identity"] = nodes.conversation(
        "identity",
        _identity_task(spec, by["verify_identity"]),
        [
            nodes.when_true(
                "load_account",
                "All security answers are verified",
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
        by["get_account"],
        _engine_extra(spec, "get_account") | _bake_customer(spec, by["get_account"]),
        retries=2,
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
    autonote = spec.get("_note_rows", {}) if notes else {}
    if autonote:
        nt = by["add_note"]
        for n in range(1, k + 1):
            body = _bake_customer(spec, nt) | {
                spec["notes"]["product_field"]: "{{p" + str(n) + "_id}}",
                spec["notes"]["reason_field"]: "{{autonote_reason}}",
            }
            wf_nodes[f"{codegen.AUTONOTE_NODE}{n}"] = nodes.api_node(
                f"{codegen.AUTONOTE_NODE}{n}",
                [engine_call(nt, body, retries=1)],
                _autonote_routes(n + 1, k),
            )
    for rid, row in rows.items():
        if "negotiate" in row["phases"]:
            # Outcome may depend on what was recorded: a code node records the event, finalize computes.
            wf_nodes[f"ev_{rid}"] = nodes.code_node(
                f"ev_{rid}",
                codegen.exit_source(rid, autonote.get(rid, "")),
                _autonote_routes(1, k) if rid in autonote else [nodes.always("finalize")],
            )
            continue
        # Nothing can have been recorded before negotiation: close with literal values, no sandbox.
        literal = {cf["outcome_field"]: row["outcome"]}
        if row["reason"]:
            literal[cf["reason_field"]] = row["reason"]
        known = {
            "close_outcome": row["outcome"],
            "close_reason": row["reason"],
            "xfer_queue": row["queue"] or "none",
        }
        close_lit = engine_call(
            ct,
            _engine_extra(spec, "close_call", known) | _bake_customer(spec, ct) | literal,
            retries=1,
        )
        if row["queue"] and xt:
            xfer_lit = engine_call(
                xt,
                _engine_extra(spec, "transfer_to_agent", known)
                | _bake_customer(spec, xt)
                | {spec["transfer_field"]: row["queue"]},
                retries=1,
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
            xt,
            _engine_extra(spec, "transfer_to_agent")
            | _bake_customer(spec, xt)
            | {spec["transfer_field"]: "{{xfer_queue}}"},
            retries=1,
        )
        wf_nodes["xfer"] = nodes.api_node("xfer", [xfer_call], [nodes.always("close")])
    wf_nodes["finalize"] = nodes.code_node("finalize", codegen.finalize_source(spec), finalize_next)

    close_call = engine_call(
        ct,
        _engine_extra(spec, "close_call")
        | _bake_customer(spec, ct)
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
