"""Code-node mains of docs/design.md §9: setup_main, account_main and finalize_main.

Assembled after the modules a main uses (calendar_core, flatvars, policy_helpers; finalize needs
only flatvars). codegen.py puts the spec subset in C, adds the spec's inlined date expressions to
it (fn_deadline, fn_attempt, fn_window_min, fn_window_max, fn_callback: functions of today,
now_date, deadline, p_days_late) and calls one main. Sandbox rules: no new imports, never raise, no double curly braces, and every variable a
prompt or condition reads gets a value first (C['defaults']). Every value comes from C.

Names such as spoken, collect_list or add_business_days come from the modules assembled before
this one (calendar_core, flatvars, policy_helpers), hence the F821 exemption below.
"""

# ruff: noqa: F821

import datetime
import re


def _put_defaults(vs, C):
    for key, value in (C.get("defaults") or {}).items():
        vs[key] = value


def _debug(vs, C, text):
    try:
        vs[C.get("debug_var") or "facts_debug"] = str(text)[:300]
    except Exception:
        pass


def _calendar(C):
    set_calendar(C.get("workdays") or [], C.get("holidays") or [])


MONTH_NAMES = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def _24h(hour, minute, half):
    """Hour on the 24-hour clock; half is 'a', 'p' or None (am/pm)."""
    if half == "p" and hour < 12:
        hour += 12
    if half == "a" and hour == 12:
        hour = 0
    return hour, minute


def _month(word):
    """1-12 for a month name or its abbreviation ('oct', 'sept'), else 0."""
    for i, name in enumerate(MONTH_NAMES):
        if len(word) >= 3 and name.startswith(word):
            return i + 1
    return 0


def _parse_when(raw, order):
    """datetime of a date-time text, or None. Accepts ISO, 2026/10/14, 14.10.2026 or 10/14/2026
    (order: the spec's numeric date order), 14 October 2026 and Oct 14, 2026, each with an
    optional time such as 11:00, 9.05 or 7pm."""
    text = str(raw).strip()
    try:
        return parse_now(text)
    except Exception:
        pass
    low = text.lower()
    ymd = None
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", low)
    if m:
        ymd = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if ymd is None:
        m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", low)
        if m:
            a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            ymd = (y, a, b) if order == "mdy" else (y, b, a)
    if ymd is None:
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)\.?,?\s+(\d{4})", low)
        if m and _month(m.group(2)):
            ymd = (int(m.group(3)), _month(m.group(2)), int(m.group(1)))
    if ymd is None:
        m = re.search(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", low)
        if m and _month(m.group(1)):
            ymd = (int(m.group(3)), _month(m.group(1)), int(m.group(2)))
    if ymd is None:
        return None
    rest = low[: m.start()] + " " + low[m.end() :]
    hour, minute = 0, 0
    for t in re.finditer(r"(\d{1,2})(?:[:.h](\d{2}))?\s*(?:([ap])\.?\s?m\b)?", rest):
        if t.group(2) or t.group(3):
            hour, minute = _24h(int(t.group(1)), int(t.group(2) or 0), t.group(3))
            break
    try:
        return datetime.datetime(ymd[0], ymd[1], ymd[2], hour, minute)
    except Exception:
        return None


def _now(vs, C):
    """(datetime of the call's `now`, how it was found). Falls back to the server clock."""
    for raw in (vs.get(C.get("now_var") or "now"), vs.get("today_iso")):
        if raw is None or str(raw).strip() == "":
            continue
        found = _parse_when(raw, C.get("date_order"))
        if found is not None:
            return found, "ok"
    return datetime.datetime.now(), "clock"


def _num(value):
    """A finite float, or None."""
    try:
        if value is None or isinstance(value, bool):
            return None
        n = float(str(value).replace(",", "").strip())
        return n if n == n and abs(n) != float("inf") else None
    except Exception:
        return None


def _int(value):
    n = _num(value)
    return None if n is None else int(round(n))


def _amount(value):
    """Amount as a number with 2 decimals, e.g. 420.00."""
    return "not available" if value is None else format(value, ".2f")


def _spoken_amount(value):
    """The bank's figure for speech: 420 or 2125.10 (no currency is added)."""
    if value is None:
        return ""
    return str(int(value)) if value == int(value) else format(value, ".2f")


def _ds(d):
    return "not available" if d is None else d.isoformat() + " (" + spoken(d) + ")"


def _short(d):
    return d.isoformat() + " (" + WEEKDAYS[d.weekday()].capitalize() + ")"


def _ev(fn, today, deadline, days_late):
    """Run one inlined spec expression; a date or None, never an exception."""
    try:
        value = fn(today, today, deadline, days_late)
        if isinstance(value, str):
            value = datetime.date.fromisoformat(value.strip()[:10])
        if isinstance(value, datetime.datetime):
            value = value.date()
        if isinstance(value, datetime.date):
            return value
    except Exception:
        pass
    return None


def _hm(text):
    """'HH:MM' from '10:00', '9.30', '19h30', '10', '7pm' or '7:30 p.m.'; '' when unreadable."""
    m = re.match(r"\s*(\d{1,2})(?:[:.h](\d{2}))?\s*(?:([ap])\.?\s?m\b)?", str(text or "").lower())
    if not m:
        return ""
    hour, minute = _24h(int(m.group(1)), int(m.group(2) or 0), m.group(3))
    return format(hour, "02d") + ":" + format(minute, "02d")


def _fill(template, values, vs=None):
    """Replace {name} or a doubled-brace name with values[name], else with the short string
    variable `name` of vs (a call variable such as a last name); '' when unknown. No str.format,
    so no format errors, and no brace is left for the engine or the voice."""

    def one(m):
        value = values.get(m.group(1))
        if value is None and vs is not None:
            found = vs.get(m.group(1))
            value = found if isinstance(found, str) and len(found) <= 80 else None
        return "" if value is None else str(value)

    pattern = r"\{\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}?"
    return re.sub(pattern, one, str(template or ""))


def _day_note(d, today):
    """'business day', or what the day is and the business days around it."""
    if is_business_day(d):
        return "business day"
    kind = "non-working day"
    if d.isoformat() in HOLIDAYS:
        kind = "holiday"
    elif d.weekday() >= 5:
        kind = "weekend"
    before = business_day_on_or_before(d)
    after = business_day_on_or_after(d)
    text = kind + ", not a business day"
    if before is not None:
        text += "; business day before: " + _short(before)
        if before < today:
            text += " (already past)"
    if after is not None:
        text += "; next business day: " + _short(after)
    return text


def _when(d, today):
    if d == today:
        return " (today)"
    return " (already past)" if d < today else ""


def _wd(d):
    """'Sat 2026-10-17': compact, unambiguous, ISO for tool calls."""
    return WEEKDAYS[d.weekday()][:3].capitalize() + " " + d.isoformat()


def _kind(d):
    if d.isoformat() in HOLIDAYS:
        return "holiday"
    return "weekend" if d.weekday() >= 5 else "non-working day"


def date_table(today, end, C):
    """Compact calendar (it is a workflow variable: every sandbox run returns all variables, and
    large outputs were seen truncated by the platform, so this stays small)."""
    names = ", ".join(WEEKDAYS[w][:3].capitalize() for w in sorted(WORKDAYS)) or "none"
    lines = [
        "CALENDAR: today is " + _wd(today) + ". Business days: " + names + ", except holidays.",
        "Days that are NOT business days, from today to "
        + end.isoformat()
        + " (-> next business day):",
    ]
    d, off = today, []
    while d <= end and len(off) < 80:
        if not is_business_day(d):
            after = business_day_on_or_after(d)
            off.append(_wd(d) + " " + _kind(d) + (" -> " + after.isoformat() if after else ""))
        d = d + datetime.timedelta(days=1)
    lines.append("; ".join(off) if off else "(none)")
    lines.append("Every other date in that range is a business day.")
    tomorrow = today + datetime.timedelta(days=1)
    lines.append("tomorrow = " + _wd(tomorrow))
    this_days = [weekday_in_week(today, wd, 0) for wd in range(7)]
    lines.append(
        "this <weekday> (this Monday-to-Sunday week): " + ", ".join(_wd(x) for x in this_days)
    )
    following = C.get("next_weekday") != "next_occurrence"
    if following:
        nxt = [weekday_in_week(today, wd, 1) for wd in range(7)]
        rule = "next <weekday> (that weekday in the following week): "
    else:
        nxt = [next_occurrence(today, wd, False) for wd in range(7)]
        rule = "next <weekday> (the first such weekday after today): "
    lines.append(rule + ", ".join(_wd(x) for x in nxt))
    for label, k in (("next week", 1), ("the week after next", 2)):
        lines.append(
            label
            + " (Monday-to-Sunday week): "
            + _wd(weekday_in_week(today, 0, k))
            + " to "
            + _wd(weekday_in_week(today, 6, k))
        )
    last_bd = last_business_day_of_month(today)
    line = "end of this month = " + _wd(end_of_month(today))
    if last_bd is not None:
        line += "; last business day of this month = " + _wd(last_bd)
    lines.append(line)
    # Every day with its weekday: the model otherwise pairs weekdays and dates from another year's
    # calendar ("this Friday" = 17 Oct, "Monday the 26th" read as after the deadline).
    lines.append("EVERY DAY (take weekdays from here, never from memory):")
    start = weekday_in_week(today, 0, 0)
    for _ in range(8):
        if start > end:
            break
        days = [start + datetime.timedelta(days=i) for i in range(7)]
        lines.append(
            "week "
            + start.isoformat()
            + ": "
            + ", ".join(
                WEEKDAYS[x.weekday()][:3].capitalize() + " " + str(x.day) + " " + x.strftime("%b")
                for x in days
            )
        )
        start = start + datetime.timedelta(days=7)
    return "\n".join(lines)


def _table_end(today, C):
    """Latest date any band deadline or promise window can reach, plus 14 days (capped)."""
    ends = []
    fns = C.get("fn_deadline") or []
    for i, band in enumerate(C.get("bands") or []):
        if i >= len(fns):
            break
        for days_late in (band.get("min_days"), band.get("max_days")):
            deadline = _ev(fns[i], today, None, days_late)
            ends.append(deadline)
            if C.get("fn_window_max"):
                ends.append(_ev(C["fn_window_max"], today, deadline, days_late))
    ends = [d for d in ends if d is not None and d >= today]
    last = max(ends) if ends else today + datetime.timedelta(days=30)
    last = min(last, today + datetime.timedelta(days=120))
    return last + datetime.timedelta(days=14)


def callback_slots(now, today, C):
    cb = C.get("callback") or {}
    if not cb.get("enabled"):
        return "(no callback window in the brief)"
    start, end = _hm(cb.get("start")), _hm(cb.get("end"))
    days = []
    for fn in C.get("fn_callback") or []:
        d = _ev(fn, today, None, None)
        if d is not None and d >= today and d not in days:
            days.append(d)
    lines = ["CALLBACK SLOTS (a callback can be booked only inside these; HH:MM, 24-hour clock):"]
    for d in sorted(days):
        head = "- " + d.isoformat() + " (" + spoken(d) + "): "
        now_hm = now.strftime("%H:%M")
        if d == today and cb.get("after_now") and now_hm >= start:
            if now_hm >= end:
                lines.append(head + "no time left today (it is already " + now_hm + ")")
            else:
                lines.append(head + "later than " + now_hm + " (now), until " + end)
        else:
            lines.append(head + "from " + start + " to " + end)
    if len(lines) == 1:
        lines.append("- none")
    return "\n".join(lines)


def setup_main(vs, C):
    _put_defaults(vs, C)
    try:
        _calendar(C)
        now, how = _now(vs, C)
        today = now.date()
        if how != "ok":
            _debug(vs, C, "now unreadable; server clock used")
        vs["today_iso"] = today.isoformat()
        vs["today_facts"] = (
            "Today is "
            + spoken(today)
            + " ("
            + today.isoformat()
            + "), "
            + now.strftime("%H:%M")
            + ". Today is "
            + ("a business day." if is_business_day(today) else "not a business day.")
        )
    except Exception as e:
        _debug(vs, C, "setup: " + str(e))
        return
    try:
        vs["date_table"] = date_table(today, _table_end(today, C), C)
    except Exception as e:
        _debug(vs, C, "date table: " + str(e))
    try:
        vs["callback_slots"] = callback_slots(now, today, C)
    except Exception as e:
        _debug(vs, C, "callback slots: " + str(e))


def _raw_fields(vs, prefix, index, item):
    """Product fields as the bank sent them: flattened strings keep leading zeros ('0377')."""
    out = {}
    for key, value in item.items():
        raw = vs.get(prefix + "." + str(index) + "." + str(key))
        out[key] = raw if isinstance(raw, str) else value
    return out


def _band(days_late, C):
    """(index, band) whose day range holds days_late; outside every range, the nearest band."""
    bands = C.get("bands") or []
    if not bands or days_late is None:
        return -1, None
    for i, band in enumerate(bands):
        if int(band.get("min_days")) <= days_late <= int(band.get("max_days")):
            return i, band
    if days_late < min(int(b.get("min_days")) for b in bands):
        i = min(range(len(bands)), key=lambda j: int(bands[j].get("min_days")))
    else:
        i = max(range(len(bands)), key=lambda j: int(bands[j].get("max_days")))
    return i, bands[i]


def _attempt_amount(kind, past_due, floor):
    full = "the full past-due amount " + _amount(past_due)
    if kind == "floor":
        return "the floor " + _amount(floor)
    if kind == "full_or_floor":
        return (
            full
            + ", or instead the floor "
            + _amount(floor)
            + " only if the customer said the full amount is too much before this offer"
        )
    return full


def _plan_amount(kind, past_due, floor):
    return "floor " + _amount(floor) if kind == "floor" else _amount(past_due)


def _named_date_lines(today, low, high, C):
    """What to do when the customer names a date: the brief's adjustment rules, applied in code."""
    mode = C.get("non_business_day") or "next_business_day"
    after = C.get("after_max") or "offer_max"
    out = ["- IF THE CUSTOMER NAMES A DATE (already follows the brief; do exactly this):"]
    out.append("  - a date before " + _ds(low) + ": not possible; ask for another date")
    if C.get("business_days_only"):
        out.append(
            "  - a business day from " + _ds(low) + " to " + _ds(high) + ": accept that date"
        )
    else:
        out.append("  - any date from " + _ds(low) + " to " + _ds(high) + ": accept that date")
    if after == "offer_max":
        tail = "say the latest date you can record is " + _ds(high) + " and offer that date"
    else:
        tail = "say that date cannot be recorded and ask for another date"
    if C.get("business_days_only"):
        d = low
        while d <= high:
            if not is_business_day(d):
                what = "weekend" if d.weekday() >= 5 else "not a business day"
                if d.isoformat() in HOLIDAYS:
                    what = "holiday"
                if mode == "ask_again":
                    act = "not a business day; ask for another date"
                else:
                    adj = (
                        business_day_on_or_after(d)
                        if mode == "next_business_day"
                        else business_day_on_or_before(d)
                    )
                    if adj is None or adj < low:
                        act = "not a business day and no earlier valid day; ask for another date"
                    elif adj > high:
                        act = "not a business day; " + tail
                    else:
                        act = "not a business day (" + what + "); offer " + _ds(adj) + " instead"
                out.append("  - " + _ds(d) + ": " + act)
            d = d + datetime.timedelta(days=1)
    out.append("  - a date after " + _ds(high) + ": " + tail)
    return out


def _product(k, raw, today, C, vs):
    """(facts block, disclosure sentence, deadline) for slot k."""
    slot = "P" + str(k)
    type_name = str(raw.get(C.get("type_field")) or "")
    kind = (C.get("types") or {}).get(type_name) or {}
    label = _fill(kind.get("label") or type_name.replace("_", " "), raw, vs).strip()
    past_due = _num(raw.get(C.get("past_due_field")))
    days_late = _int(raw.get(C.get("days_late_field")))
    floor_field = kind.get("floor_field") or ""
    floor_pct = _num(kind.get("floor_percent")) or 0
    if floor_pct > 0 and past_due is not None:  # a share of the past-due amount (audit F15)
        floor = round(past_due * floor_pct / 100.0, 2)
        floor_field = (
            str(int(floor_pct) if floor_pct == int(floor_pct) else floor_pct) + "% of past due"
        )
    else:
        floor = _num(raw.get(floor_field)) if floor_field else None
    bi, band = _band(days_late, C)
    fns = C.get("fn_deadline") or []
    deadline = _ev(fns[bi], today, None, days_late) if band is not None and bi < len(fns) else None
    pid = str(raw.get(C.get("id_field")) or "")
    lines = [slot + " = " + label + " (product_id " + pid + ")"]
    band_text = "none"
    if band is not None:
        band_text = (
            str(band.get("name"))
            + " ("
            + str(band.get("min_days"))
            + " to "
            + str(band.get("max_days"))
            + " days late)"
        )
        if not int(band.get("min_days")) <= (days_late or 0) <= int(band.get("max_days")):
            band_text += ", nearest band: days late is outside every band"
    lines.append(
        "- past due: "
        + _amount(past_due)
        + "; days late: "
        + str(days_late)
        + "; band: "
        + band_text
    )
    lines.append("- deadline: " + _ds(deadline))
    lines.append("- floor (" + (floor_field or "none") + "): " + _amount(floor))
    plan = []
    if band is not None:
        allowed = int(band.get("attempts") or 0)
        lines.append(
            "- persuasion attempts in this band: "
            + str(allowed)
            + (" (ONE offer only)" if allowed == 1 else "")
        )
        afns = C.get("fn_attempt") or []
        first = None
        for ai, attempt in enumerate(C.get("attempts") or []):
            n = int(attempt.get("n") or 0)
            names = attempt.get("bands") or []
            if n > allowed or (names and band.get("name") not in names) or ai >= len(afns):
                continue
            when = _ev(afns[ai], today, deadline, days_late)
            if first is None:
                first = (attempt.get("amount"), when)
            plan.append(
                str(n)
                + ") "
                + _plan_amount(attempt.get("amount"), past_due, floor)
                + " on "
                + (when.isoformat() if when is not None else "?")
            )
            line = "- attempt " + str(n) + ", on " + _ds(when)
            if when is not None and when < today:
                line += " (already past: not a valid promise date)"
            if when is not None and deadline is not None and when > deadline:
                line += " (after the deadline)"
            lines.append(line + ": " + _attempt_amount(attempt.get("amount"), past_due, floor))
        if (
            first is not None
            and first[0] == "full_or_floor"
            and first[1] is not None
            and floor is not None
        ):
            lines.append(
                "- IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH before your first offer: offer"
                + " exactly the floor "
                + _amount(floor)
                + " on "
                + _ds(first[1])
                + "; this IS attempt 1 (no other date: not today unless that is this date)"
            )
        if allowed > 0:
            lines.append(
                "- after attempt "
                + str(allowed)
                + " is refused: NO further offer for this product (not even the floor)"
            )
    low = _ev(C["fn_window_min"], today, deadline, days_late) if C.get("fn_window_min") else None
    high = _ev(C["fn_window_max"], today, deadline, days_late) if C.get("fn_window_max") else None
    if C.get("business_days_only"):
        # Same set of dates, but the bounds the model reads are themselves valid dates.
        low = business_day_on_or_after(low) if low is not None else None
        high = business_day_on_or_before(high) if high is not None else None
    if low is not None and high is not None and low > high:
        lines.append("- valid promise dates: none (no allowed date is left)")
    else:
        lines.append(
            "- valid promise dates: "
            + ("business days " if C.get("business_days_only") else "")
            + "from "
            + _ds(low)
            + " to "
            + _ds(high)
            + ", both included"
        )
    if low is not None and high is not None and low <= high:
        lines += _named_date_lines(today, low, high, C)
    tools = C.get("promise_tool", "") + str(k)
    if C.get("notes_used"):
        tools += ", " + C.get("note_tool", "") + str(k)
    lines.append("- tools for this product: " + tools)
    if band is not None and band.get("transfer_row"):
        lines.append(
            "- MANDATORY TRANSFER: end with "
            + C.get("exit_tool", "")
            + str(band.get("transfer_row"))
        )
    values = dict(raw)
    values["label"] = label
    values["past_due"] = _spoken_amount(past_due)
    values["days_late"] = "" if days_late is None else str(days_late)
    values["floor"] = _spoken_amount(floor)
    values["deadline"] = spoken(deadline) if deadline is not None else ""
    sentence = _fill((C.get("disclosure") or {}).get("product_sentence"), values, vs)
    if band is None or not C.get("attempts"):
        summary = ""
    elif not plan:
        summary = slot + ": no persuasion attempt"
    else:
        count = str(len(plan)) + (" offer only" if len(plan) == 1 else " offers")
        summary = slot + ": " + count + ": " + ", ".join(plan)
    return "\n".join(lines), sentence, deadline, summary


def account_main(vs, C):
    _put_defaults(vs, C)
    try:
        disclosure = C.get("disclosure") or {}
        vs["disclosure_text"] = _fill(disclosure.get("intro"), {}, vs).strip()
        _calendar(C)
        now, how = _now(vs, C)
        today = now.date()
        prefix = C.get("prefix") or ""
        items = collect_list(vs, prefix)
        if not items or get_value(vs, C.get("ok_key") or "") is False:
            _debug(vs, C, "no products (" + str(len(items)) + " items)")
            return
        K = max(1, int(C.get("K") or 1))
        used = items[:K]
        blocks, sentences, deadlines, plans = [], [], [], []
        for i, item in enumerate(used):
            k = i + 1
            raw = _raw_fields(vs, prefix, i, item)
            vs["p" + str(k) + "_id"] = str(raw.get(C.get("id_field")) or "") or "none"
            try:
                block, sentence, deadline, summary = _product(k, raw, today, C, vs)
            except Exception as e:
                block = "P" + str(k) + ": the facts could not be computed (" + str(e)[:80] + ")"
                sentence, deadline, summary = "", None, ""
            blocks.append(block)
            if summary:
                plans.append(summary)
            if sentence:
                sentences.append(sentence)
            deadlines.append("P" + str(k) + " " + _ds(deadline))
        head = "ACCOUNT (from get_account, in the bank's order): " + str(len(used)) + " product"
        head += "s" if len(used) != 1 else ""
        parts = [head] + blocks
        if len(used) > 1:
            parts.append("Deadline per product: " + "; ".join(deadlines) + ".")
        if plans:
            parts.append(
                "OFFER PLAN (one offer per refusal, in this order; after a product's last offer is "
                "refused, no other offer for it, not even the floor): " + "; ".join(plans) + "."
            )
        if len(items) > K:
            parts.append(
                "The bank returned "
                + str(len(items))
                + " products; only P1 to P"
                + str(K)
                + " have tools."
            )
        for k in range(len(used) + 1, K + 1):
            vs["p" + str(k) + "_id"] = "none"  # also when setup's run failed: routes read it
            unused = C.get("promise_tool", "") + str(k)
            if C.get("notes_used"):
                unused += " or " + C.get("note_tool", "") + str(k)
            parts.append("P" + str(k) + ": not in use (never call " + unused + ")")
        vs["account_facts"] = "\n\n".join(parts)
        ask = (
            disclosure.get("first_ask_single")
            if len(used) == 1
            else disclosure.get("first_ask_multi")
        )
        text = [disclosure.get("intro") or ""] + sentences + [ask or ""]
        text = [_fill(t, {}, vs) for t in text]
        vs["disclosure_text"] = " ".join(t.strip() for t in text if t and t.strip())
        vs["product_count"] = str(len(used))
        vs["account_status"] = "ok"
        if how != "ok":
            _debug(vs, C, "now unreadable; server clock used")
    except Exception as e:
        _put_defaults(vs, C)
        _debug(vs, C, "account: " + str(e))


def _succeeded(vs, tool, ok_field):
    """Did the last call of `tool` succeed? The ok flag, else the HTTP envelope."""
    flag = get_value(vs, tool + "_response.data." + ok_field)
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, (int, float)) and flag in (0, 1):
        return flag == 1
    status = get_value(vs, tool + "_response.status")
    code = _num(vs.get(tool + "_response.status_code"))
    if status is None and code is None:
        return False
    if get_value(vs, tool + "_response.data.error") not in (None, ""):
        return False
    return str(status).strip().lower() == "success" and code is not None and code < 400


def _event_row(event, vs, C, rows):
    defaults = C.get("default_rows") or {}
    if event in rows:
        return event
    if event == "done":
        return defaults.get("negotiate", "")
    if event.startswith("cap_") and event[4:] in defaults:
        return defaults.get(event[4:], "")
    stage = "negotiate" if vs.get("account_status") == "ok" else "opening"
    return defaults.get(stage, "")


def _then(rule, event_row, notes, rows):
    then = rule.get("then")
    if then == "row":
        return rows.get(rule.get("row")) or rows.get(event_row)
    if then == "first_note_reason_not":
        skip = rule.get("note_reason")
        for _, reason in notes:
            if reason and reason != skip:
                same = [
                    r
                    for r in rows.values()
                    if r.get("outcome") == rule.get("outcome") and r.get("reason") == reason
                ]
                key = same[0].get("id") if same else str(rule.get("outcome")) + "_" + reason
                return dict(id=key, outcome=rule.get("outcome"), reason=reason, queue="")
        return None
    return rows.get(event_row)


def finalize_main(vs, C):
    _put_defaults(vs, C)
    try:
        rows = dict((r.get("id"), r) for r in C.get("rows") or [])
        K = max(1, int(C.get("K") or 1))
        ok_field = C.get("ok_field") or "ok"
        event = str(vs.get("end_event") or "none")
        promises, notes = [], []
        for k in range(1, K + 1):
            if str(vs.get("p" + str(k) + "_id") or "none") in ("", "none"):
                continue
            sticky = str(vs.get("p" + str(k) + "_recorded") or "").strip().lower() == "yes"
            if sticky or _succeeded(vs, C.get("promise_tool", "") + str(k), ok_field):
                promises.append(k)
            note_tool = C.get("note_tool", "") + str(k)
            if C.get("notes_used") and _succeeded(vs, note_tool, ok_field):
                field = str(C.get("note_reason_field") or "reason")
                prefix = str(C.get("arg_prefix") or "")
                reason = None
                # observed on the platform: <tool>_args.<arg_prefix><field>; the rest are fallbacks
                keys = ("_args." + prefix + field, "_args." + field, "_args.body." + field)
                for key in keys:
                    if reason in (None, ""):
                        reason = vs.get(note_tool + key)
                notes.append((k, str(reason or "").strip()))
        event_row = _event_row(event, vs, C, rows)
        # A row that precedence gives only for a recorded promise is never closed on the model's
        # word alone: without a recorded promise the event counts as 'done'.
        promise_rows = [
            r.get("row")
            for r in C.get("precedence") or []
            if r.get("when") == "promise_recorded" and r.get("then") == "row"
        ]
        if event_row in promise_rows and not promises:
            event_row = (C.get("default_rows") or {}).get("negotiate", event_row)
        chosen, fired = None, "none"
        for rule in C.get("precedence") or []:
            when = rule.get("when")
            if when == "transferred":
                hit = bool((rows.get(event_row) or {}).get("queue"))
            elif when == "promise_recorded":
                hit = bool(promises)
            elif when == "all_notes_reason":
                hit = bool(notes) and all(r == rule.get("note_reason") for _, r in notes)
            elif when == "any_note":
                hit = bool(notes)
            else:
                hit = when == "always"
            chosen = _then(rule, event_row, notes, rows) if hit else None
            if chosen:
                fired = str(when)
                break
        if not chosen:
            chosen = rows.get(event_row)
        if not chosen:
            _debug(vs, C, "event=" + event + "; no row for " + str(event_row))
            return
        vs["close_outcome"] = str(chosen.get("outcome") or "")
        if chosen.get("reason"):
            vs["close_reason"] = str(chosen.get("reason"))
        vs["xfer_queue"] = str(chosen.get("queue") or "") or "none"
        vs["close_key"] = str(chosen.get("id") or "")
        _debug(
            vs,
            C,
            "event="
            + event
            + "; event_row="
            + str(event_row)
            + "; rule="
            + fired
            + "; row="
            + str(chosen.get("id"))
            + "; promises="
            + ",".join("P" + str(k) for k in promises)
            + "; notes="
            + ",".join("P" + str(k) + ":" + r for k, r in notes),
        )
    except Exception as e:
        _debug(vs, C, "finalize: " + str(e))
