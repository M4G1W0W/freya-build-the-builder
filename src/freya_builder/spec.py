"""PolicySpec v1: the structured reading of a brief (docs/design.md §3), and its checks.

`SPEC_SCHEMA` is a strict JSON schema (every property required, no extra keys) so the builder LLM
can be forced to emit it. Optional values use "" or [] instead of null. `check_spec` cross-checks
a spec against the tool API: every value we will send must be in the API's enums.

Date/amount rules are small Python EXPRESSIONS over a fixed helper vocabulary (see expr.py); they
are validated with an AST whitelist and inlined into code-node source at build time.
"""

import re
from typing import Any

from .expr import check_expr
from .toolapi import Tool

STR: dict = {"type": "string"}
INT: dict = {"type": "integer"}
BOOL: dict = {"type": "boolean"}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


def obj(props: dict) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


CALL_VAR = obj(
    {
        "name": STR,
        "role": {"type": "string", "enum": ["customer_id", "now", "addressing", "other"]},
        "example": STR,
    }
)
PRODUCT_TYPE = obj(
    {"api_value": STR, "label": STR, "floor_field": STR, "floor_percent": {"type": "number"}}
)
BAND = obj(
    {
        "name": STR,
        "min_days": INT,
        "max_days": INT,
        "deadline_expr": STR,
        "attempts": INT,
        "transfer_row": STR,
    }
)
ATTEMPT = obj(
    {
        "n": INT,
        "bands": arr(STR),
        "amount": {"type": "string", "enum": ["full", "floor", "full_or_floor"]},
        "date_expr": STR,
        "note": STR,
    }
)
QUESTION = obj({"key": STR, "ask": STR, "format": STR})
HINT = obj({"value": STR, "instruction": STR, "counts_as_wrong": BOOL})
ROW = obj(
    {
        "id": STR,
        "outcome": STR,
        "reason": STR,
        "phases": arr(
            {"type": "string", "enum": ["opening", "third_party", "identity", "negotiate"]}
        ),
        "trigger": STR,
        "say_before_end": arr(STR),
        "queue": STR,
    }
)
PRECEDENCE = obj(
    {
        "when": {
            "type": "string",
            "enum": [
                "transferred",
                "ending_wins",
                "promise_recorded",
                "all_notes_reason",
                "any_note",
                "always",
            ],
        },
        "note_reason": STR,
        "then": {"type": "string", "enum": ["event_row", "row", "first_note_reason_not"]},
        "row": STR,
        "outcome": STR,
    }
)

SPEC_SCHEMA = obj(
    {
        "meta": obj(
            {
                "bank_name": STR,
                "agent_self_description": STR,
                "call_vars": arr(CALL_VAR),
                "max_products": INT,
            }
        ),
        "calendar": obj(
            {
                "business_weekdays": arr(INT),
                "holidays": arr(STR),
                "next_weekday": {"type": "string", "enum": ["following_week", "next_occurrence"]},
                "this_weekday": {"type": "string", "enum": ["current_week", "next_occurrence"]},
                "numeric_date_order": {"type": "string", "enum": ["dmy", "mdy", "ymd"]},
            }
        ),
        "products": obj(
            {
                "list_field": STR,
                "id_field": STR,
                "type_field": STR,
                "past_due_field": STR,
                "days_late_field": STR,
                "types": arr(PRODUCT_TYPE),
            }
        ),
        "bands": arr(BAND),
        "attempts": arr(ATTEMPT),
        "too_much": obj(
            {"offer": {"type": "string", "enum": ["attempt_1", "separate"]}, "date_expr": STR}
        ),
        "promise_window": obj(
            {
                "min_expr": STR,
                "max_expr": STR,
                "business_days_only": BOOL,
                "non_business_day": {
                    "type": "string",
                    "enum": ["next_business_day", "previous_business_day", "ask_again"],
                },
                "after_max": {"type": "string", "enum": ["offer_max", "ask_again"]},
            }
        ),
        "callback": obj(
            {
                "enabled": BOOL,
                "day_exprs": arr(STR),
                "start": STR,
                "end": STR,
                "after_now": BOOL,
                "date_field": STR,
                "time_field": STR,
                "booked_row": STR,
            }
        ),
        "opening": obj(
            {
                "line": STR,
                "confirm_criteria": STR,
                "forbidden_before_verified": arr(STR),
            }
        ),
        "identity": obj(
            {
                "questions": arr(QUESTION),
                "question_field": STR,
                "answer_field": STR,
                "gate_field": STR,
                "answer_ok_field": STR,
                "remaining_field": STR,
                "hint_field": STR,
                "hints": arr(HINT),
                "failed_line": STR,
                "decline_explain": STR,
                "failed_row": STR,
            }
        ),
        "rows": arr(ROW),
        "close_precedence": arr(PRECEDENCE),
        "default_rows": obj(
            {"opening": STR, "third_party": STR, "identity": STR, "negotiate": STR}
        ),
        "notes": obj(
            {"used": BOOL, "product_field": STR, "reason_field": STR, "on_transfer": BOOL}
        ),
        "promise_fields": obj({"product_field": STR, "amount_field": STR, "date_field": STR}),
        "transfer_field": STR,
        "close_fields": obj({"outcome_field": STR, "reason_field": STR}),
        "engine_fields": arr(obj({"tool": STR, "field": STR, "value": STR})),
        "disclosure": obj(
            {"intro": STR, "product_sentence": STR, "first_ask_single": STR, "first_ask_multi": STR}
        ),
        "success_lines": obj({"promise": STR}),
        "failure_rules": obj({"promise": STR}),
        "stage_rules": obj({"opening": STR, "third_party": STR, "identity": STR, "negotiate": STR}),
        "unmodeled": arr(STR),
    }
)


def schema_problems(value: Any, schema: dict, path: str = "spec") -> list[str]:
    """Minimal strict-schema check for the subset SPEC_SCHEMA uses (no external library)."""
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if t in types and not isinstance(value, types[t]):
        return [f"{path}: expected {t}, got {type(value).__name__}"]
    if t == "integer" and isinstance(value, bool):
        return [f"{path}: expected integer, got boolean"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: {value!r} not in {schema['enum']}"]
    out: list[str] = []
    if t == "object":
        props = schema.get("properties", {})
        out += [f"{path}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{path}: unexpected key {k}" for k in value if k not in props]
        for k, sub in props.items():
            if k in value:
                out += schema_problems(value[k], sub, f"{path}.{k}")
    if t == "array":
        for i, item in enumerate(value):
            out += schema_problems(item, schema.get("items", {}), f"{path}[{i}]")
    return out


def _enum(tools: dict[str, Tool], tool: str, field: str) -> tuple[str, ...]:
    t = tools.get(tool)
    f = t.field(field) if t else None
    return f.enum if f else ()


# Tools the workflow engine calls itself (no model fills their fields), and the variables finalize
# sets before close_call and transfer_to_agent run.
ENGINE_TOOLS = ("get_account", "close_call", "transfer_to_agent")
LATE_VARS = ("close_outcome", "close_reason", "xfer_queue")
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def engine_sent(spec: dict, tools: list[Tool]) -> dict[str, set[str]]:
    """The fields render bakes into each engine-run call, before engine_fields."""
    cid = customer_field(spec, tools)
    cf = spec["close_fields"]
    return {
        "get_account": {cid},
        "close_call": {cid, cf["outcome_field"], cf["reason_field"]},
        "transfer_to_agent": {cid, spec["transfer_field"]},
    }


def _engine_field_problems(spec: dict, tools: list[Tool]) -> list[str]:
    """Review gap 8a: hidden tool APIs may add required fields to the engine-run tools."""
    by = {t.name: t for t in tools}
    base = engine_sent(spec, tools)
    call_vars = {v["name"] for v in spec["meta"]["call_vars"]}
    p: list[str] = []
    filled: dict[str, set[str]] = {}
    for e in spec["engine_fields"]:
        where = f"engine_fields {e['tool']}.{e['field']}"
        tool = by.get(e["tool"]) if e["tool"] in ENGINE_TOOLS else None
        if not tool:
            p.append(f"{where}: not a tool the engine calls ({', '.join(ENGINE_TOOLS)})")
            continue
        field = tool.field(e["field"])
        if not field:
            p.append(f"{where}: {e['tool']} has no request field {e['field']!r}")
            continue
        if e["field"] in base[e["tool"]]:
            p.append(f"{where}: the engine already sends this field")
        late = set(LATE_VARS) if e["tool"] != "get_account" else set()
        names = PLACEHOLDER.findall(e["value"])
        for name in names:
            if name not in call_vars | late:
                allowed = ", ".join(sorted(call_vars | late))
                p.append(f"{where}: unknown placeholder {{{{{name}}}}} (allowed here: {allowed})")
        unset = {"close_reason", "xfer_queue"} & set(names)
        if unset and not PLACEHOLDER.fullmatch(e["value"].strip()):
            # close_reason is unset for reasonless rows and xfer_queue is 'none' without a transfer:
            # alone they drop the field, inside other text they would be sent literally
            p.append(f"{where}: use {sorted(unset)} only as the whole value, not inside text")
        if not names and field.enum and e["value"] not in field.enum:
            p.append(f"{where}: {e['value']!r} not in API enum {field.enum}")
        filled.setdefault(e["tool"], set()).add(e["field"])
    for name in ENGINE_TOOLS:
        if name not in by:
            continue
        sent = base[name] | filled.get(name, set())
        for f in by[name].request:
            if f.required and f.name not in sent:
                p.append(
                    f"{name} requires {f.name!r} but the engine does not send it: add an "
                    f"engine_fields entry with its value"
                )
    return p


def _ending_wins_problems(
    i: int, c: dict, rows: dict, note_reasons: tuple[str, ...], spec: dict
) -> list[str]:
    """Review gap 7: an ending the brief keeps even after a recorded promise. finalize closes with
    its row when the agent took that ending or a note carries `note_reason`."""
    where = f"close_precedence[{i}] ending_wins"
    p: list[str] = []
    if c["then"] != "row":
        p.append(f"{where}: then must be 'row'")
    row = rows.get(c["row"])
    if row and ("negotiate" not in row["phases"] or row["queue"]):
        p.append(f"{where}: row {c['row']!r} must be a negotiate-phase ending without a queue")
    precedence = spec["close_precedence"]
    if c["row"] == spec["default_rows"]["negotiate"]:
        # notes-done and the turn caps end through the default row: every promise call closing
        # that way would take this row instead of the promise outcome (precedence review C1)
        p.append(
            f"{where}: row {c['row']!r} is default_rows.negotiate; calls that end without an "
            f"explicit ending close through it, so it must not win over a recorded promise"
        )
    later = [j for j, d in enumerate(precedence) if j > i and d["when"] == "transferred"]
    if later:
        # a transfer the agent announced must still happen (precedence review C2)
        p.append(f"{where}: must come after the 'transferred' entry at index {later[0]}")
    nr = c["note_reason"]
    taken = {
        d["note_reason"]
        for d in precedence
        if d["when"] == "all_notes_reason" or d["then"] == "first_note_reason_not"
    }
    if nr and nr not in note_reasons:
        known = ", ".join(note_reasons) or "notes are not used"
        p.append(f"{where}: note_reason {nr!r} is not an add_note reason ({known})")
    elif nr and nr in taken:
        p.append(
            f"{where}: note_reason {nr!r} is already used by an all_notes_reason or "
            f"first_note_reason_not entry"
        )
    return p


# "say" + a quoted sentence of at least 4 words; a closing quote followed by a letter is an apostrophe
SAID = re.compile(
    r"\b(?:say|says|said|tell|tells|state|states)\b[^\"\u201c\u201d\u2018\u2019]{0,40}?"
    r"[\"\u201c\u2018']([^\"\u201c\u201d]{8,300}?[.?!])[\"\u201d\u2019'](?![A-Za-z])",
    re.I,
)


def _plain(text: str) -> str:
    return " ".join(text.replace("{", "").replace("}", "").lower().split())


def _names(line: str, reason: str) -> bool:
    words = {reason, reason.replace("_", " "), reason.replace("_", "-")}
    low = line.lower()
    return any(re.search(r"(?<![a-z_])" + re.escape(w) + r"(?![a-z_])", low) for w in words)


def _unsaid_note_sentences(spec: dict, note_reasons: tuple[str, ...]) -> list[str]:
    """unmodeled is never shown to the agent. In a multi-product brief the sentence for a reason
    noted per product (e.g. already paid) landed there instead of in its row's say_before_end in
    6 of 16 extractions (engine-fixes Fix 1). Flags a said, quoted sentence on an unmodeled line
    that names a note reason when no row says it."""
    if not spec["notes"]["used"]:
        return []

    def rows_for(nr: str) -> list[dict]:
        return [
            r
            for r in spec["rows"]
            if r["reason"] == nr or r["id"] == nr or (not r["reason"] and r["outcome"] == nr)
        ]

    said = _plain(" ".join(x for r in spec["rows"] for x in r["say_before_end"]))
    p: list[str] = []
    for line in spec["unmodeled"]:
        rows = sorted({r["id"] for nr in note_reasons if _names(line, nr) for r in rows_for(nr)})
        for sentence in SAID.findall(line) if rows else []:
            if len(sentence.split()) >= 4 and _plain(sentence) not in said:
                p.append(
                    f"unmodeled holds a sentence the agent must say, {sentence!r}, but the agent "
                    f"never sees unmodeled: put it in say_before_end of the row of that per-product "
                    f"reason (one of {rows})"
                )
    return p


def check_spec(spec: dict, tools: list[Tool]) -> list[str]:
    """Problems that would make the agent send values the bank does not accept, or crash code."""
    by = {t.name: t for t in tools}
    p: list[str] = []
    need = ["verify_identity", "get_account", "create_promise", "close_call"]
    p += [f"tool API has no {n}" for n in need if n not in by]
    if not p and not call_var(spec, "customer_id"):
        p.append("meta.call_vars has no variable with role customer_id")
    elif not p and not customer_field(spec, tools):
        p.append(
            f"no request field carries the customer id: get_account has no field "
            f"{call_var(spec, 'customer_id')!r} and the tools share no single required field"
        )
    if p:
        return p

    rows = {r["id"]: r for r in spec["rows"]}
    if len(rows) != len(spec["rows"]):
        p.append("row ids are not unique")
    outcomes = _enum(by, "close_call", spec["close_fields"]["outcome_field"])
    if not outcomes:
        p.append(f"close_call has no enum field {spec['close_fields']['outcome_field']!r}")
    queues = (
        _enum(by, "transfer_to_agent", spec["transfer_field"]) if "transfer_to_agent" in by else ()
    )
    reasons = _enum(by, "close_call", spec["close_fields"]["reason_field"])
    for r in spec["rows"]:
        if outcomes and r["outcome"] not in outcomes:
            p.append(f"row {r['id']}: outcome {r['outcome']!r} not in API enum {outcomes}")
        if reasons and r["reason"] and r["reason"] not in reasons:
            p.append(f"row {r['id']}: reason {r['reason']!r} not in API enum {reasons}")
        if r["queue"] and queues and r["queue"] not in queues:
            p.append(f"row {r['id']}: queue {r['queue']!r} not in API enum {queues}")
        if not r["phases"]:
            p.append(f"row {r['id']}: no phases")
    for stage, rid in spec["default_rows"].items():
        if rid not in rows:
            p.append(f"default row for {stage} is unknown: {rid!r}")
        elif stage == "negotiate" and rows[rid]["queue"]:
            # turn caps and render's ev_notes end through it; finalize would transfer every such call
            p.append(f"default row for negotiate must not transfer: {rid!r}")
    note_reasons: tuple[str, ...] = ()
    if spec["notes"]["used"] and "add_note" in by:
        note_reasons = _enum(by, "add_note", spec["notes"]["reason_field"])
    p += _unsaid_note_sentences(spec, note_reasons)
    for i, c in enumerate(spec["close_precedence"]):
        if c["then"] == "row" and c["row"] not in rows:
            p.append(f"close_precedence[{i}] names unknown row {c['row']!r}")
        if c["when"] == "ending_wins":
            p += _ending_wins_problems(i, c, rows, note_reasons, spec)
        if c["then"] == "first_note_reason_not" and outcomes and c["outcome"] not in outcomes:
            p.append(f"close_precedence[{i}] outcome {c['outcome']!r} not in API enum")
        if c["then"] == "first_note_reason_not" and spec["notes"]["used"] and "add_note" in by:
            # finalize closes with the first note's reason as the close_call reason: every note
            # reason it can meet needs a row with this outcome and that reason (audit F46/F64/F71)
            field = by["add_note"].field(spec["notes"]["reason_field"])
            pairs = {(r["outcome"], r["reason"]) for r in spec["rows"]}
            for reason in field.enum if field else ():
                if reason != c["note_reason"] and (c["outcome"], reason) not in pairs:
                    p.append(
                        f"close_precedence[{i}] closes as {c['outcome']!r} with the note reason, "
                        f"but there is no row ({c['outcome']!r}, {reason!r}) for add_note reason "
                        f"{reason!r}"
                    )
    if spec["identity"]["failed_row"] not in rows:
        p.append(f"identity.failed_row is unknown: {spec['identity']['failed_row']!r}")
    if spec["callback"]["enabled"] and spec["callback"]["booked_row"] not in rows:
        p.append(f"callback.booked_row is unknown: {spec['callback']['booked_row']!r}")
    for b in spec["bands"]:
        if b["transfer_row"] and b["transfer_row"] not in rows:
            p.append(f"band {b['name']}: unknown transfer_row {b['transfer_row']!r}")

    ident = spec["identity"]
    vt = by["verify_identity"]
    at_once = identity_all_at_once(spec, vt)
    # empty question and answer fields mean the spec reads the tool as all-at-once: only the keys
    # are then wrong, and answer_ok_field is unused either way
    no_answer_ok = at_once or not (ident["question_field"] or ident["answer_field"])
    qkeys = [q["key"] for q in ident["questions"]]
    fields = [f.name for f in vt.request]
    shape = (
        " (if verify_identity takes every answer in one call, each identity question key is "
        "the exact request field for that answer, and question_field, answer_field and "
        'answer_ok_field are ""; request fields: ' + ", ".join(fields) + ")"
    )
    if at_once:
        cid = customer_field(spec, tools)
        for k in qkeys:
            if k not in fields:
                exact = next(f for f in fields if f.lower() == k.lower())
                p.append(f"identity question key {k!r} must be the exact request field {exact!r}")
        for f in vt.request:
            # an enum field is a setting, not a free-text answer (review of cand-eng.1)
            if f.required and f.name != cid and not f.enum and f.name.lower() not in _lower(qkeys):
                p.append(
                    f"verify_identity takes every answer in one call and requires {f.name!r}, "
                    f"but no identity question has key {f.name!r}"
                )
    elif not ident["question_field"] and not ident["answer_field"]:
        p.append(
            f"identity question keys {[k for k in qkeys if k not in fields]} are not "
            f"verify_identity request fields" + shape
        )
    else:
        keys = _enum(by, "verify_identity", ident["question_field"])
        if not vt.field(ident["question_field"]):
            p.append(f"verify_identity has no field {ident['question_field']!r}" + shape)
        if not vt.field(ident["answer_field"]):
            p.append(f"verify_identity has no field {ident['answer_field']!r}" + shape)
        for q in ident["questions"]:
            if keys and q["key"] not in keys:
                p.append(f"identity question {q['key']!r} not in API enum {keys}")
        # a repair round once named two answer fields as question and answer field (P3)
        named = [x for x in (ident["question_field"], ident["answer_field"]) if x in qkeys]
        partly = [k for k in qkeys if k.lower() in _lower(fields)]
        if named or partly:
            p.append(
                f"identity question keys {sorted(set(named + partly))} are verify_identity request "
                f"fields, so the question/answer reading cannot be right" + shape
            )
    resp_types = {f.name: f.type for f in vt.response}
    for role in ("gate_field", "answer_ok_field", "remaining_field", "hint_field"):
        if no_answer_ok and role == "answer_ok_field":
            continue
        if ident[role] and resp_types and ident[role] not in resp_types:
            p.append(f"identity {role} {ident[role]!r} is not a verify_identity response field")
    # The identity gate and the post-hook compare these with 'true': an empty or non-boolean field
    # would never open the gate (audit F01/F02/F62), silently, for every call.
    for role, meaning in (
        ("gate_field", "is true once EVERY security question has passed"),
        ("answer_ok_field", "is true when the answer just checked was correct"),
    ):
        if no_answer_ok and role == "answer_ok_field":
            continue  # one call checks every answer: the gate alone decides
        if not ident[role]:
            p.append(f"identity {role} is empty: name the verify_identity boolean that {meaning}")
        elif resp_types.get(ident[role]) not in (None, "", "boolean"):
            p.append(
                f"identity {role} {ident[role]!r} is {resp_types[ident[role]]}: name the "
                f"verify_identity boolean that {meaning}"
            )

    for role in ("product_field", "amount_field", "date_field"):
        if not by["create_promise"].field(spec["promise_fields"][role]):
            p.append(f"create_promise has no field {spec['promise_fields'][role]!r}")
    if spec["notes"]["used"]:
        if "add_note" not in by:
            p.append("notes are used but the tool API has no add_note")
        else:
            for role in ("product_field", "reason_field"):
                if not by["add_note"].field(spec["notes"][role]):
                    p.append(f"add_note has no field {spec['notes'][role]!r}")
    cb = spec["callback"]
    if cb["enabled"]:
        st = by.get("schedule_callback")
        if not st:
            p.append("callback enabled but the tool API has no schedule_callback")
        else:
            for role in ("date_field", "time_field"):
                if cb[role] and not st.field(cb[role]):
                    p.append(f"schedule_callback has no field {cb[role]!r}")
    pr = spec["products"]
    plist = next((f for f in by["get_account"].response if f.name == pr["list_field"]), None)
    if not plist:
        p.append(f"get_account response has no list field {pr['list_field']!r}")
    else:
        item = {c.name: c for c in plist.children}
        for role in ("id_field", "type_field", "past_due_field", "days_late_field"):
            if item and pr[role] not in item:
                p.append(f"products.{role} {pr[role]!r} is not a field of {pr['list_field']} items")
        api_types = item[pr["type_field"]].enum if pr["type_field"] in item else ()
        for t in pr["types"]:
            if api_types and t["api_value"] not in api_types:
                p.append(f"product type {t['api_value']!r} not in API enum {api_types}")
            pct = t.get("floor_percent") or 0
            if not 0 <= pct <= 100:
                p.append(f"product type {t['api_value']!r}: floor_percent {pct} not in 0..100")
            elif pct and not t["floor_field"]:
                pass  # the floor is that share of the past-due amount (audit F15)
            elif item and t["floor_field"] not in item:
                p.append(
                    f"floor field {t['floor_field']!r} is not a field of {pr['list_field']} items"
                )

    exprs: list[tuple[str, str]] = [
        (f"band {b['name']} deadline", b["deadline_expr"]) for b in spec["bands"]
    ]
    exprs += [(f"attempt {a['n']} date", a["date_expr"]) for a in spec["attempts"]]
    if too_much_separate(spec) and too_much(spec)["date_expr"].strip():
        exprs += [("too much offer date", too_much(spec)["date_expr"])]
    elif too_much_separate(spec):
        # attempt 1's date would make the refused offer and attempt 1 the same (review)
        p.append(
            "too_much.offer is 'separate' but date_expr is empty: give the date the "
            "specification sets for that floor offer"
        )
    exprs += [("promise window min", spec["promise_window"]["min_expr"])]
    exprs += [("promise window max", spec["promise_window"]["max_expr"])]
    exprs += [(f"callback day {i}", e) for i, e in enumerate(cb["day_exprs"])]
    for label, e in exprs:
        p += [f"{label}: {problem}" for problem in check_expr(e)]
    p += _engine_field_problems(spec, tools)
    return p


# The official page (Evaluation tab): hidden-brief customers have "one to three products". A brief whose
# extraction says fewer still gets 3 product slots, so a misread never drops a product (review gap 2).
MIN_SLOTS = 3


def product_slots(spec: dict) -> int:
    return max(MIN_SLOTS, int(spec["meta"]["max_products"]))


# Specs saved before the too_much field read like a brief that is silent about it: the floor
# offered after "too much" is attempt 1, on attempt 1's date.
TOO_MUCH_DEFAULT = {"offer": "attempt_1", "date_expr": ""}


def too_much(spec: dict) -> dict:
    return spec.get("too_much") or TOO_MUCH_DEFAULT


def too_much_separate(spec: dict) -> bool:
    """The brief says the floor offered after "too much" is not a persuasion attempt (P2)."""
    return too_much(spec)["offer"] == "separate"


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def early_lines(spec: dict) -> dict[str, list[str]]:
    """Per row id, the say_before_end sentences said BEFORE the customer answers, not at the end.

    An ending's sentences are said in the goodbye message together with its transition, so such a
    sentence was said twice and a question could never be answered (Fix 1 audit: the support offer
    question and the sympathy line in both the accept and the decline ending, "Can I help you
    first?" in the human-transfer ending; 9 of 16 fresh extractions, 0 of 13 before Fix 1). Early:
    a question, or a sentence shared by a transfer ending and a non-transfer ending (said before the
    customer picks one of them), unless it is a closing line: common to every ending of one step,
    or in more than half of all endings (one row that drops or rewords the goodbye, such as a
    human-transfer row listed in every step, must not turn the goodbye into an early line).
    """
    rows = spec["rows"]
    sayers: dict[str, list[dict]] = {}
    for r in rows:
        for s in r["say_before_end"]:
            sayers.setdefault(_words(s), []).append(r)
    out: dict[str, list[str]] = {}
    for r in rows:
        for s in r["say_before_end"]:
            shared = sayers[_words(s)]
            ids = {x["id"] for x in shared}
            mixed = len({bool(x["queue"]) for x in shared}) == 2
            common = len(ids) * 2 > len(rows) or any(
                {q["id"] for q in rows if p in q["phases"]} <= ids
                for x in shared
                for p in x["phases"]
            )
            if s.strip().endswith("?") or (mixed and not common):
                out.setdefault(r["id"], []).append(s)
    return out


def _lower(names: list[str]) -> set[str]:
    return {n.lower() for n in names}


def identity_all_at_once(spec: dict, tool: Tool) -> bool:
    """verify_identity takes every answer in one call: each identity question key is one of its
    request fields, ignoring case (perturbed rehearsal P3). question_field, answer_field and
    answer_ok_field are then unused, whatever the spec names there. A question field whose enum
    lists every key is the per-answer shape, even if a key is also a field name."""
    ident = spec["identity"]
    keys = [q["key"] for q in ident["questions"]]
    selector = tool.field(ident["question_field"]) if ident["question_field"] else None
    if selector and selector.enum and set(keys) <= set(selector.enum):
        return False
    return bool(keys) and _lower(keys) <= _lower([f.name for f in tool.request])


def call_var(spec: dict, role: str) -> str:
    return next((v["name"] for v in spec["meta"]["call_vars"] if v["role"] == role), "")


def customer_field(spec: dict, tools: list[Tool]) -> str:
    """The request field that carries the customer id: the call variable's own name when
    get_account has it, else the one field every tool requires (a renamed id, audit F09/F56)."""
    cid = call_var(spec, "customer_id")
    account = next((t for t in tools if t.name == "get_account"), None)
    if cid and account and account.field(cid):
        return cid
    common: set[str] | None = None
    for t in tools:
        names = {f.name for f in t.request if f.required}
        common = names if common is None else common & names
    return next(iter(common)) if common and len(common) == 1 else ""


def get(spec: dict, path: str) -> Any:
    node: Any = spec
    for part in path.split("."):
        node = node[part]
    return node
