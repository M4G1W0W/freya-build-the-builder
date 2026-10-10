"""Calendar arithmetic that runs INSIDE a Freya code node (and is unit-tested locally).

Sandbox constraints (kit/docs/tools-and-code.md, "Code nodes and code_exec"):
- only `json`, `re`, `datetime` are known to import; this file imports nothing else
- the source must contain no double curly braces (the engine may template them)
- never raise: callers wrap their use in try/except

Every rule value (working weekdays, holidays, offsets) is a parameter. Nothing here knows a brief.
"""

import datetime

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_now(text):
    """'2026-10-14T11:00' (or a date) -> datetime. Raises ValueError on garbage."""
    text = str(text).strip().replace("Z", "")
    if len(text) == 10:
        return datetime.datetime.fromisoformat(text + "T00:00")
    return datetime.datetime.fromisoformat(text[:19])


def to_date(text):
    return datetime.date.fromisoformat(str(text)[:10])


def is_business_day(day, workdays, holidays):
    """workdays: weekday numbers (Mon=0). holidays: set of ISO date strings."""
    return day.weekday() in workdays and day.isoformat() not in holidays


def nth_business_day_after(day, n, workdays, holidays):
    """The n-th business day strictly after `day` (n >= 1). n == 0 returns `day` itself."""
    current, count = day, 0
    while count < n:
        current = current + datetime.timedelta(days=1)
        if is_business_day(current, workdays, holidays):
            count += 1
    return current


def next_business_day_on_or_after(day, workdays, holidays):
    current = day
    for _ in range(400):
        if is_business_day(current, workdays, holidays):
            return current
        current = current + datetime.timedelta(days=1)
    return current


def last_business_day_of_week(day, workdays, holidays):
    """Last business day in the Monday-Sunday week containing `day`, or None if there is none."""
    monday = day - datetime.timedelta(days=day.weekday())
    for back in range(6, -1, -1):
        candidate = monday + datetime.timedelta(days=back)
        if is_business_day(candidate, workdays, holidays):
            return candidate
    return None


def weekday_in_week(day, weekday, weeks_ahead):
    """The given weekday (0=Mon) in the calendar week `weeks_ahead` weeks after the week of `day`."""
    monday = day - datetime.timedelta(days=day.weekday())
    return monday + datetime.timedelta(days=7 * weeks_ahead + weekday)


def next_occurrence(day, weekday, include_today):
    delta = (weekday - day.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return day + datetime.timedelta(days=delta)


def spoken(day):
    """'Friday 16 October 2026' — unambiguous for read-backs."""
    return WEEKDAYS[day.weekday()].capitalize() + " " + str(day.day) + " " + day.strftime("%B %Y")
