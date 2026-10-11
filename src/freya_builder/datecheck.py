"""Build-time self-test of the date logic (audit F32/F33/F36).

check_spec only parses the spec's date expressions. Whether they give sensible dates depends on
the calendar and the call day, so this runs the GENERATED setup and account code (the very code
the Freya code nodes run) on a grid of call days and synthetic products, reads the facts the agent
reads, and returns problems the LLM can repair: an attempt date before today or after the
deadline, a deadline or window that cannot be computed, or a code-node error.
"""

import datetime as dt
import re

from . import codegen

GRID_DAYS = 42  # six weeks: every weekday, several weekends, month ends
SAMPLE_PAST_DUE, SAMPLE_FLOOR = "500", "150"
ATTEMPT_LINE = re.compile(r"^- attempt (\d+), on (.+?): ", re.M)
TOO_MUCH_LINE = re.compile(
    r"^- IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH[^:]*: offer exactly the floor \S+ on (.+?), once",
    re.M,
)


def _anchor(spec: dict) -> dt.date:
    for v in spec["meta"]["call_vars"]:
        if v["role"] == "now":
            try:
                return dt.date.fromisoformat(str(v["example"])[:10])
            except ValueError:
                break
    holidays = sorted(spec["calendar"]["holidays"])
    try:
        return dt.date.fromisoformat(holidays[0]) - dt.timedelta(days=14)
    except (IndexError, ValueError):
        return dt.date(2026, 10, 12)


def _days(spec: dict) -> list[dt.date]:
    start = _anchor(spec)
    days = {start + dt.timedelta(days=i) for i in range(GRID_DAYS)}
    for h in spec["calendar"]["holidays"]:
        try:
            d = dt.date.fromisoformat(h)
        except ValueError:
            continue
        days |= {d + dt.timedelta(days=i) for i in (-1, 0, 1)}
    return sorted(days)


def _products(spec: dict) -> list[tuple[str, str, dict]]:
    """(type, band, raw get_account item) at each band's first and last day, for every type."""
    p = spec["products"]
    out = []
    for t in p["types"]:
        for b in spec["bands"]:
            for days_late in sorted({int(b["min_days"]), int(b["max_days"])}):
                raw = {
                    p["type_field"]: t["api_value"],
                    p["past_due_field"]: SAMPLE_PAST_DUE,
                    p["days_late_field"]: str(days_late),
                }
                if t.get("floor_field"):
                    raw[t["floor_field"]] = SAMPLE_FLOOR
                for name in re.findall(r"\{(\w+)\}", t.get("label") or ""):
                    raw.setdefault(name, "1234")
                out.append((t["api_value"], b["name"], raw))
    return out


def _blocks(facts: str) -> list[str]:
    return [b for b in facts.split("\n\n") if re.match(r"P\d+ = ", b)]


def check_dates(spec: dict) -> list[str]:
    """Problems found by running the generated date logic; [] when every day looks sane."""
    setup = compile(codegen.setup_source(spec), "<setup>", "exec")
    account = compile(codegen.account_source(spec), "<account>", "exec")
    k = codegen._slots(spec)
    p = spec["products"]
    prefix = f"{codegen.ACCOUNT_NODE}_response.data.{p['list_field']}"
    items = _products(spec)
    found: dict[str, str] = {}

    def problem(key: str, text: str) -> None:
        found.setdefault(key, text)

    for day in _days(spec):
        when = f"{day:%A} {day.isoformat()}"
        vs = {"customer_id": "c_test", "now": f"{day.isoformat()}T11:00"}
        exec(setup, {"vars": vs})
        if vs.get("setup_debug"):
            problem("setup", f"date check: setup failed when today is {when}: {vs['setup_debug']}")
            continue
        for start in range(0, len(items), k):
            chunk = items[start : start + k]
            run = dict(vs)
            run[f"{codegen.ACCOUNT_NODE}_response.data.{codegen.OK_FIELD}"] = "true"
            for i, (_, _, raw) in enumerate(chunk):
                for field, value in raw.items():
                    run[f"{prefix}.{i}.{field}"] = value
                run[f"{prefix}.{i}.{p['id_field']}"] = f"p{i + 1}"
            exec(account, {"vars": run})
            if run.get("account_debug"):
                problem(
                    "account",
                    f"date check: account facts failed when today is {when}: "
                    f"{run['account_debug']}",
                )
                continue
            blocks = _blocks(run.get("account_facts", ""))
            if len(blocks) != len(chunk):
                problem(
                    "blocks",
                    f"date check: {len(chunk)} products gave {len(blocks)} fact "
                    f"blocks when today is {when}",
                )
                continue
            for (ptype, band, _), block in zip(chunk, blocks, strict=True):
                where = f"band {band!r} ({ptype}) when today is {when}"
                if "- deadline: not available" in block:
                    problem(
                        f"deadline:{band}",
                        f"date check: the deadline of {where} cannot be "
                        "computed (the deadline expression gives no date)",
                    )
                for line in block.splitlines():
                    if line.startswith("- valid promise dates") and "not available" in line:
                        problem(
                            f"window:{band}",
                            f"date check: the valid promise window of "
                            f"{where} cannot be computed: {line[2:120]}",
                        )
                dated = ATTEMPT_LINE.findall(block)
                dated += [("too much", d) for d in TOO_MUCH_LINE.findall(block)]
                for n, date_text in dated:
                    tag = (
                        f"attempt {n} of {where}"
                        if n != "too much"
                        else f"the too-much offer of {where}"
                    )
                    if "not available" in date_text:
                        problem(
                            f"att{n}:{band}:none",
                            f"date check: {tag} has no date "
                            "(the attempt expression gives no date on that day)",
                        )
                    elif "already past" in date_text:
                        problem(
                            f"att{n}:{band}:past",
                            f"date check: {tag} is "
                            f"{date_text.split(' ')[0]}, before today: an attempt date must "
                            "never be in the past, whatever weekday or holiday today is",
                        )
                    elif "after the deadline" in date_text:
                        problem(
                            f"att{n}:{band}:late",
                            f"date check: {tag} is "
                            f"{date_text.split(' ')[0]}, after that band's deadline",
                        )
    return list(found.values())
