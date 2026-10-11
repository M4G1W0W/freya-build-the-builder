"""The builder's brief-reading pipeline: consolidate -> extract spec -> check/repair; render; self-test.

Plugged into cli.run(). All brief knowledge comes from the LLM reading the brief; this module holds
only generic instructions (with invented, generic examples).
"""

import json
import time

from . import platform
from .datecheck import check_dates
from .expr import FUNCS, NAMES
from .llm import LLMError, budget_left, chat_json
from .spec import MIN_SLOTS, SPEC_SCHEMA, check_spec, schema_problems
from .toolapi import Tool
from .trace import Trace

REPAIR_ROUNDS = 2
SMOKE_WAITS = (5, 15)  # the smoke test is optional: a short retry schedule
REPAIR_MIN_S = (
    300  # a repair call takes about a minute; below this the best spec so far is deployed
)

CONSOLIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["clean", "raw"]},
        "documents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "role": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["title", "role", "date"],
                "additionalProperties": False,
            },
        },
        "amendments": {"type": "array", "items": {"type": "string"}},
        "consolidated_rules": {"type": "string"},
    },
    "required": ["kind", "documents", "amendments", "consolidated_rules"],
    "additionalProperties": False,
}

CONSOLIDATE_SYSTEM = """You prepare a bank's specification for outbound collections phone calls so that a phone agent can follow it.
The input is either ONE clean specification (possibly in several files where a later file extends an earlier one), or RAW bank material: e-mails, policy extracts, memos that change the policy, code lists.
1. kind: "clean" if it is a specification written as rules for the call (even across several files); "raw" otherwise.
2. documents: each document with its role (specification, extension, e-mail, policy, memo, code list, other) and date if given.
3. amendments: every change a later or more authoritative document makes to an earlier one (one line each). Ignore proposals that were not approved and opinions in e-mails that the policy or memo does not confirm.
4. consolidated_rules: ONE complete, numbered rule list for the call, as the bank wants it NOW: every rule of the policy with all amendments applied, superseded text removed, codes replaced by the exact values of the tool API, every required sentence quoted verbatim, every number, date, time and list kept exactly. Keep the order of the call (opening, someone else answers, identity, stating the debt, dates, amounts, getting the promise, recording, special situations, closing with the outcome table). Do not invent rules. For a clean specification, reproduce all its rules faithfully (merging extension files: an extension's rule replaces the base rule it says it replaces)."""

SPEC_SYSTEM = f"""You read a bank's specification for outbound collections phone calls and fill a JSON policy spec that a program turns into a phone agent. Accuracy is everything: every value must come from the specification or the tool API; never invent rules.

GENERAL
- Use the EXACT field names and enum values of the tool API wherever a field asks for an API name or value.
- Copy sentences the specification requires the agent to say verbatim.
- Use "" for an empty string value and [] for an empty list. Never leave a value out.

EXPRESSIONS (deadline_expr, date_expr, min_expr, max_expr, day_exprs) are tiny Python expressions that return a date.
- Names: {", ".join(sorted(NAMES))}. today and now_date = the call's date; deadline = the product's deadline (only inside attempts and promise_window); p_days_late = the product's days late.
- Functions: {", ".join(sorted(FUNCS))}.
  add_business_days(d, n) = the n-th business day strictly after d; next_business_day(d) = the first business day strictly after d; business_day_on_or_after(d) / business_day_on_or_before(d); last_business_day_of_week(d) (Monday-Sunday week); last_business_day_of_month(d); end_of_month(d); add_days(d, n); weekday_in_week(d, weekday 0=Mon, weeks_ahead); is_business_day(d); date(y, m, d).
- Allowed syntax: calls, names, integers, comparisons, and/or/not, + and -, and "x if condition else y". No attributes, no keywords, no lambdas, no braces.
- Generic examples: "the 9th business day after today" -> add_business_days(today, 9); "the last business day of this week, or of next week if today is that day" -> last_business_day_of_week(today) if last_business_day_of_week(today) > today else last_business_day_of_week(add_days(today, 7)); "the next business day" -> next_business_day(today); "the deadline" -> deadline.

FIELDS
- meta.call_vars: every variable the call starts with. role: customer_id (the id passed to the bank tools), now (current date and time), addressing (used to name or address the customer), other. example: the example value given, else "".
- meta.max_products: the largest number of late products one customer can have per the specification (1 if it says one product).
- calendar.business_weekdays: weekday numbers, Monday=0. calendar.holidays: ISO dates, after amendments. calendar.next_weekday: "following_week" if "next <weekday>" means that weekday in the following calendar week, "next_occurrence" if it means the next such day. calendar.numeric_date_order: how a date said only in numbers is read.
- products: field names of the get_account response (list_field = the array of products; id_field, type_field, past_due_field, days_late_field). products.types: one entry per product type value of the tool API that the specification covers; label = how the agent names it in speech, may contain product fields in single braces like {{last4}}; floor_field = the product field holding the lowest acceptable amount; floor_percent = 0, unless the specification defines that lowest amount as a percentage of the past-due amount: then floor_percent = that percentage (e.g. 30) and floor_field = "".
- bands: one per lateness band. deadline_expr = the latest allowed promise date. attempts = number of persuasion attempts. transfer_row = the row id if this band must be transferred, else "".
- attempts: the persuasion ladder. bands = band names it applies to ([] = all bands). amount: "full", "floor", or "full_or_floor" (the full amount, or the floor if the customer already said the full amount is too much). date_expr = the date proposed. note = the specification's wording of this attempt.
- promise_window: earliest and latest allowed promise date as expressions; business_days_only. non_business_day = what to offer when the customer names a weekend day or holiday inside the window (next_business_day, previous_business_day, or ask_again). after_max = what to do when the customer names a date after the latest allowed date (offer_max = offer the latest date; ask_again).
- callback: enabled if a callback can be booked; day_exprs = the allowed callback days; start/end = allowed times "HH:MM"; after_now = must be later than now; date_field/time_field = schedule_callback request field names ("" if a field does not exist); booked_row = the row used after booking.
- opening.line: the agent's exact first utterance: the required opening sentence(s) followed by the confirmation question, with call variables written as {{{{name}}}} (double braces). Never use the word "recorded" in the opening (it is reserved for confirming a recorded promise): to say that the call is recorded, say "we are recording this call". opening.confirm_criteria: what counts as the customer confirming, and what to do if unclear. opening.forbidden_before_verified: words and topics never said before identity is verified (include product names if the specification forbids naming the product).
- identity.questions: in order. key = the value of verify_identity's question field. ask = the question to say. format: "date", "digits:N", "year", "alnum" or "text". identity.question_field / answer_field = verify_identity request field names. If verify_identity instead takes every answer in one call (one request field per answer), each key = the request field for that answer, and question_field, answer_field and answer_ok_field = "". gate_field = the verify_identity response boolean meaning ALL checks passed. answer_ok_field = the response boolean for this one answer. remaining_field = the response integer of wrong answers left ("" if none). hint_field = the response field carrying hints ("" if none). hints = what to do for each hint value. failed_line = what the agent says when the check fails. decline_explain = what the agent says once when the customer refuses to answer. failed_row = the row used when the check fails.
- rows: one per (outcome, reason) row of the outcome table, reason "" when the table gives none. id = "<outcome>_<reason>" or "<outcome>". phases = the call steps where this ending can happen: opening (before anyone is identified), third_party (someone else answered), identity (during the security questions), negotiate (after verification). trigger = when, in at most 30 words from the specification. say_before_end = exact sentences required before ending this way ([] if none); a quoted sentence is copied verbatim, and a rule "say that X" gives the sentence X ("say that payments can take a day to appear" -> "Payments can take a day to appear."). queue = the transfer queue value if this ending transfers the call, else "".
- close_precedence: ordered rules that compute the final outcome from what was actually recorded. when: "transferred" (the ending row has a queue), "ending_wins" (the call ended through the given row, or a product has a note with note_reason), "promise_recorded", "all_notes_reason" (every product has a note with note_reason), "any_note", "always". then: "event_row" (the row of the ending the agent chose), "row" (the given row id), "first_note_reason_not" (outcome = the given outcome, reason = the first note reason, in product order, that is not note_reason). Add an "ending_wins" entry (then "row", row = that ending's row id, note_reason = the add_note reason it gives, else "") ONLY for a non-transfer ending that the specification says keeps its own outcome even when a promise was already recorded, placed right before "promise_recorded"; never for a reason given to a single product. End with {{"when": "always", "then": "event_row"}}.
- default_rows: the row to use per step if the call ends there without an explicit ending (the most conservative row of that step).
- notes: used = the specification uses add_note; product_field/reason_field = add_note request field names; on_transfer = notes are allowed when the call is transferred.
- promise_fields / transfer_field / close_fields: request field names in the tool API.
- engine_fields: the program itself sends get_account (with the customer id), close_call (customer id, outcome, reason) and transfer_to_agent (customer id, queue). For every OTHER field the tool API marks required on one of these three tools, add {{"tool", "field", "value"}}. value = the exact value the specification or the tool API gives for it (an enum value where the field has an enum), or a placeholder in double braces: a meta.call_vars name, and for close_call and transfer_to_agent also {{{{close_outcome}}}}, {{{{close_reason}}}} or {{{{xfer_queue}}}}. [] when these tools need nothing more.
- disclosure: intro = what the agent says right after verification before the amounts; product_sentence = a template for one product using {{label}}, {{past_due}}, {{days_late}}; first_ask_single / first_ask_multi = the exact first request for payment.
- success_lines.promise = the exact sentence after a promise is recorded. failure_rules.promise = the specification's rule when recording fails.
- stage_rules: for each step, the specification's rules that apply there (short; cite rule numbers or titles).
- unmodeled: specification rules that no field above captures (short lines). They stay in the agent's prompt."""


def _field_text(f) -> str:
    text = f"{f.name}:{f.type}{' required' if f.required else ''}"
    text += f" enum={'|'.join(f.enum)}" if f.enum else ""
    text += f" ({f.description})" if f.description else ""
    if f.children:
        text += " of {" + "; ".join(_field_text(c) for c in f.children) + "}"
    return text


def _tool_api_text(tools: list[Tool]) -> str:
    out = []
    for t in tools:
        req = "; ".join(_field_text(f) for f in t.request)
        resp = "; ".join(_field_text(f) for f in t.response)
        out.append(f"- {t.name} ({t.summary})\n  request: {req}\n  response: {resp}")
    return "\n".join(out)


def consolidate(trace: Trace, brief_text: str, tools: list[Tool]) -> dict:
    user = f"# TOOL API\n{_tool_api_text(tools)}\n\n# BRIEF MATERIAL\n{brief_text}"
    out = chat_json(
        trace,
        "consolidate brief documents, apply amendments",
        CONSOLIDATE_SYSTEM,
        user,
        CONSOLIDATE_SCHEMA,
        "consolidated",
    )
    trace.step(
        f"brief kind={out['kind']} documents={len(out['documents'])} amendments={len(out['amendments'])}"
    )
    for a in out["amendments"]:
        trace.step(f"amendment: {a[:200]}")
    return out


def spec_problems(spec: dict, tools: list[Tool]) -> list[str]:
    """Schema, then API cross-checks, then the date self-test (it needs a spec that renders)."""
    problems = schema_problems(spec, SPEC_SCHEMA) or check_spec(spec, tools)
    if problems:
        return problems
    try:
        return check_dates(spec)
    except Exception as e:  # the self-test must never be the reason a build dies
        return [f"date check could not run: {type(e).__name__}: {str(e)[:200]}"]


def extract_spec(trace: Trace, rules_text: str, tools: list[Tool]) -> dict:
    user = f"# TOOL API\n{_tool_api_text(tools)}\n\n# SPECIFICATION\n{rules_text}"
    spec = chat_json(
        trace, "extract policy spec from brief", SPEC_SYSTEM, user, SPEC_SCHEMA, "policy_spec"
    )
    best: tuple[int, dict] | None = None  # (problem count, spec) of the best schema-valid spec
    for round_no in range(1, REPAIR_ROUNDS + 1):
        problems = spec_problems(spec, tools)
        trace.test(f"spec check (round {round_no})", not problems, f"{len(problems)} problem(s)")
        if not problems:
            return spec
        if not schema_problems(spec, SPEC_SCHEMA) and (best is None or len(problems) < best[0]):
            best = (len(problems), spec)
        for p in problems[:20]:
            trace.warn(f"spec: {p}")
        if budget_left() < REPAIR_MIN_S:
            trace.warn(
                f"build time budget: {budget_left():.0f} s left, skipping repair round {round_no}"
            )
            break
        fix_user = (
            f"{user}\n\n# YOUR PREVIOUS SPEC\n{json.dumps(spec)}\n\n# PROBLEMS FOUND BY THE CHECKER\n"
            + "\n".join(f"- {p}" for p in problems)
            + "\n\nReturn the full corrected spec."
        )
        try:
            spec = chat_json(
                trace,
                f"repair policy spec (round {round_no})",
                SPEC_SYSTEM,
                fix_user,
                SPEC_SCHEMA,
                "policy_spec",
            )
        except LLMError as e:  # keep the best spec so far rather than no agent (diff review 8)
            trace.warn(f"repair round {round_no} failed ({str(e)[:160]}); keeping the best spec")
            break
    problems = spec_problems(spec, tools)
    trace.test("spec check (final)", not problems, f"{len(problems)} problem(s)")
    if not problems:
        return spec
    if not schema_problems(spec, SPEC_SCHEMA) and (best is None or len(problems) <= best[0]):
        best = (len(problems), spec)
    if best is None:
        raise ValueError("no schema-valid spec after repair: " + "; ".join(problems[:5]))
    # An agent that is wrong in one corner scores more than no agent: deploy the best spec, loudly.
    # render() and validate() still stop the build if the spec cannot produce a workflow.
    count, spec = best
    for p in spec_problems(spec, tools)[:20]:
        trace.warn(f"UNRESOLVED spec problem (deployed anyway): {p}")
    trace.warn(f"deploying the best spec with {count} unresolved problem(s)")
    return spec


def extract(trace: Trace, brief_text: str, tools: list[Tool]) -> dict:
    c = consolidate(trace, brief_text, tools)
    rules_text = brief_text if c["kind"] == "clean" else c["consolidated_rules"]
    spec = extract_spec(trace, rules_text, tools)
    for u in spec["unmodeled"]:
        trace.warn(f"NOT ENFORCED BY CODE (kept in prompt): {u[:200]}")
    if spec["meta"]["max_products"] < MIN_SLOTS:
        trace.warn(
            f"brief read as {spec['meta']['max_products']} product(s); rendering {MIN_SLOTS} product"
            " slots (the official page: customers have one to three products)"
        )
    spec["_prompt_brief"] = rules_text
    return spec


def render(spec: dict, tools: list[Tool]) -> dict:
    from .render import render as render_workflow

    clean = {k: v for k, v in spec.items() if not k.startswith("_")}
    return render_workflow(clean, tools, spec.get("_prompt_brief", ""))


def _example(var: dict) -> str:
    if var["example"]:
        return var["example"]
    return time.strftime("%Y-%m-%dT%H:%M", time.gmtime()) if var["role"] == "now" else "x"


def _smoke_retry(e: Exception) -> bool:
    """A bare 500 from /chat/message is final: the workflow cannot start (kit/docs/api.md)."""
    return platform.transient(e) and platform.status_of(e) != 500


def selftest(trace: Trace, saved: dict, spec: dict, tools: list[Tool]) -> bool:
    """Smoke test on the published workflow: it starts, says the opening line, leaks nothing."""
    freya = platform.kit()
    variables = {v["name"]: _example(v) for v in spec["meta"]["call_vars"]}
    body = {"workflowId": saved["workflow_id"], "message": "Hello?", "customerVariables": variables}
    try:  # the kit warns a long chat turn can return 504. A repeat only opens another test chat.
        r = platform.call(
            trace,
            "POST /api/v2/chat/message",
            lambda: freya.api("POST", "/api/v2/chat/message", body),
            _smoke_retry,
            SMOKE_WAITS,
        )
    except (RuntimeError, *platform.NETWORK_ERRORS) as e:
        trace.test("chat smoke test: workflow starts", False, platform.describe(trace, e))
        return False
    reply = str(r.get("response") or "")
    forbidden = [
        w for w in spec["opening"]["forbidden_before_verified"] if w.lower() in reply.lower()
    ]
    ok = bool(reply) and "{{" not in reply and not forbidden
    trace.test("chat smoke test: opening reply", ok, f"reply={reply[:160]!r} forbidden={forbidden}")
    if r.get("callId"):
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": r["callId"]})
        except (RuntimeError, *platform.NETWORK_ERRORS):
            pass
    return ok
