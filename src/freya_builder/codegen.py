"""code_exec sources of the code nodes (docs/design.md §9): setup, account_facts, finalize, ev_*.

Each source = sandbox modules + `CONFIG` (the spec subset the node needs, hex-encoded by
sandbox.assemble) + a main. The main defines every spec date expression as a plain function
`_e<i>(today, now_date, deadline, p_days_late)`: checked by expr.check_expr and inlined here, so
nothing is eval'd at run time. Then it calls one main of sandbox/facts.py.

No brief knowledge: every value comes from the spec. Node and tool names are the §9 contract.
"""

from .expr import check_expr, normalise
from .hooks import ARG_PREFIX
from .sandbox import assemble
from .spec import call_var, product_slots

MODULES = ["calendar_core", "flatvars", "policy_helpers", "facts"]
# Each node gets only the modules its main uses (smaller nodes; E8 has not measured the limit).
SETUP_MODULES = ["calendar_core", "policy_helpers", "facts"]
FINALIZE_MODULES = ["flatvars", "facts"]
ACCOUNT_NODE = "load_account"
PROMISE_TOOL = "create_promise_p"
NOTE_TOOL = "add_note_p"
AUTONOTE_NODE = "an_"  # an_<k>: engine-run add_note after a note-derived ending
EXIT_TOOL = "transition_to_ev_"
OK_FIELD = "ok"

# If a facts main cannot even be called, the main snippet still writes the node's defaults.
GUARD = """
try:
    globals().update(locals())
except Exception:
    pass
try:
{body}
except Exception as _error:
    try:
        for _dkey, _dvalue in CONFIG['defaults'].items():
            vars[_dkey] = _dvalue
        vars[CONFIG['debug_var']] = 'main failed: ' + str(_error)[:200]
    except Exception:
        pass
"""


def _expressions(spec: dict) -> tuple[list[str], list[str]]:
    """(function defs, main lines that put them into CONFIG) for every spec expression."""
    cb = spec["callback"]
    window = spec["promise_window"]
    groups = [
        (
            "fn_deadline",
            [(f"band {b['name']} deadline", b["deadline_expr"]) for b in spec["bands"]],
        ),
        ("fn_attempt", [(f"attempt {a['n']} date", a["date_expr"]) for a in spec["attempts"]]),
        ("fn_window_min", [("promise window min", window["min_expr"])]),
        ("fn_window_max", [("promise window max", window["max_expr"])]),
        ("fn_callback", [(f"callback day {i}", e) for i, e in enumerate(cb["day_exprs"])]),
    ]
    if not cb["enabled"]:
        groups[-1] = ("fn_callback", [])
    defs: list[str] = []
    lines: list[str] = []
    for key, items in groups:
        names = []
        for label, text in items:
            problems = check_expr(text)
            if problems:
                raise ValueError(f"spec expression {label} {text!r}: {'; '.join(problems)}")
            name = f"_e{len(defs)}"
            defs.append(
                f"def {name}(today, now_date, deadline, p_days_late):\n    return {normalise(text)}\n"
            )
            names.append(name)
        if key in ("fn_window_min", "fn_window_max"):
            lines.append(f"CONFIG['{key}'] = {names[0]}")
        else:
            lines.append(f"CONFIG['{key}'] = [{', '.join(names)}]")
    return defs, lines


def _source(spec: dict, modules: list[str], call: str, config: dict) -> str:
    defs, lines = _expressions(spec)
    body = "\n".join("    " + line for line in lines + [call])
    main = "\n".join(defs) + GUARD.replace("{body}", body)
    return assemble(modules, main, config)


def _slots(spec: dict) -> int:
    return product_slots(spec)


def _calendar(spec: dict) -> dict:
    cal = spec["calendar"]
    return {
        "workdays": sorted({int(w) for w in cal["business_weekdays"]}),
        "holidays": sorted({str(h)[:10] for h in cal["holidays"]}),
        "next_weekday": cal["next_weekday"],
        "date_order": cal["numeric_date_order"],
        "now_var": call_var(spec, "now") or "now",
    }


def _row(spec: dict, row_id: str) -> dict:
    return next((r for r in spec["rows"] if r["id"] == row_id), {})


def _empty_slots(spec: dict) -> dict:
    return {f"p{k}_id": "none" for k in range(1, _slots(spec) + 1)}


def _unavailable(spec: dict) -> str:
    return (
        "ACCOUNT NOT AVAILABLE: say you cannot access the account details right now, then end "
        f"with {EXIT_TOOL}{spec['default_rows']['negotiate']}."
    )


def setup_config(spec: dict) -> dict:
    cb = spec["callback"]
    defaults = {
        "today_iso": "",
        "today_facts": "(today's date is not available)",
        "date_table": "(not available)",
        "callback_slots": "(not available)",
        "end_event": "none",
        "xfer_queue": "none",
        "close_outcome": _row(spec, spec["default_rows"]["opening"]).get("outcome", ""),
        "account_facts": "(not loaded)",
        "account_status": "not_loaded",
        "disclosure_text": "",
        "product_count": "0",
        **_empty_slots(spec),
        "finalize_debug": "",
        "setup_debug": "",
    }
    return {
        **_calendar(spec),
        "bands": [
            {"name": b["name"], "min_days": b["min_days"], "max_days": b["max_days"]}
            for b in spec["bands"]
        ],
        "callback": {
            "enabled": cb["enabled"],
            "start": cb["start"],
            "end": cb["end"],
            "after_now": cb["after_now"],
        },
        "defaults": defaults,
        "debug_var": "setup_debug",
    }


def account_config(spec: dict) -> dict:
    prod = spec["products"]
    disclosure = spec["disclosure"]
    defaults = {
        "account_status": "unavailable",
        "account_facts": _unavailable(spec),
        "disclosure_text": disclosure["intro"],
        "product_count": "0",
        **_empty_slots(spec),
        "account_debug": "",
    }
    return {
        **_calendar(spec),
        "prefix": f"{ACCOUNT_NODE}_response.data.{prod['list_field']}",
        "ok_key": f"{ACCOUNT_NODE}_response.data.{OK_FIELD}",
        "id_field": prod["id_field"],
        "type_field": prod["type_field"],
        "past_due_field": prod["past_due_field"],
        "days_late_field": prod["days_late_field"],
        "types": {
            t["api_value"]: {
                "label": t["label"],
                "floor_field": t["floor_field"],
                "floor_percent": t.get("floor_percent") or 0,
            }
            for t in prod["types"]
        },
        "bands": [
            {
                "name": b["name"],
                "min_days": b["min_days"],
                "max_days": b["max_days"],
                "attempts": b["attempts"],
                "transfer_row": b["transfer_row"],
            }
            for b in spec["bands"]
        ],
        "attempts": [
            {"n": a["n"], "bands": list(a["bands"]), "amount": a["amount"]}
            for a in spec["attempts"]
        ],
        "business_days_only": spec["promise_window"]["business_days_only"],
        "non_business_day": spec["promise_window"]["non_business_day"],
        "after_max": spec["promise_window"]["after_max"],
        "disclosure": dict(disclosure),
        "K": _slots(spec),
        "notes_used": spec["notes"]["used"],
        "promise_tool": PROMISE_TOOL,
        "note_tool": NOTE_TOOL,
        "exit_tool": EXIT_TOOL,
        "defaults": defaults,
        "debug_var": "account_debug",
    }


def finalize_config(spec: dict) -> dict:
    return {
        "rows": [
            {"id": r["id"], "outcome": r["outcome"], "reason": r["reason"], "queue": r["queue"]}
            for r in spec["rows"]
        ],
        "precedence": [dict(c) for c in spec["close_precedence"]],
        "default_rows": dict(spec["default_rows"]),
        "K": _slots(spec),
        "notes_used": spec["notes"]["used"],
        "note_reason_field": spec["notes"]["reason_field"],
        "arg_prefix": ARG_PREFIX,
        "promise_tool": PROMISE_TOOL,
        "note_tool": NOTE_TOOL,
        "autonote_prefix": AUTONOTE_NODE if spec["notes"]["used"] else "",
        "ok_field": OK_FIELD,
        "defaults": {"xfer_queue": "none", "finalize_debug": ""},
        "debug_var": "finalize_debug",
    }


def setup_source(spec: dict) -> str:
    return _source(spec, SETUP_MODULES, "setup_main(vars, CONFIG)", setup_config(spec))


def account_source(spec: dict) -> str:
    return _source(spec, MODULES, "account_main(vars, CONFIG)", account_config(spec))


def finalize_source(spec: dict) -> str:
    return assemble(
        FINALIZE_MODULES,
        GUARD.replace("{body}", "    finalize_main(vars, CONFIG)"),
        finalize_config(spec),
    )


def exit_source(event: str, autonote: str = "") -> str:
    """ev_<event> node: records which exit the model took (a row id, 'done' or 'cap_<stage>').

    With `autonote` (a note reason), the an_<k> nodes after it note every open product with it."""
    if not event:
        raise ValueError("exit event must not be empty")
    main = (
        "try:\n"
        "    vars['end_event'] = str(CONFIG['event'])\n"
        "    if CONFIG.get('autonote'):\n"
        "        vars['autonote_reason'] = str(CONFIG['autonote'])\n"
        "except Exception:\n"
        "    vars['end_event'] = 'none'\n"
    )
    return assemble([], main, {"event": event, "autonote": autonote})
