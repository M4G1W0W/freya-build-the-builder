"""Helper vocabulary of spec date expressions (docs/design.md §9; names = expr.FUNCS).

Runs INSIDE Freya code nodes, assembled after calendar_core.py, and is unit-tested locally.
Sandbox-safe: imports only datetime, no double curly braces. Helpers may raise on bad input;
the caller (facts.py) wraps every expression call.

The calendar is module state: WORKDAYS (weekday numbers, Monday = 0) and HOLIDAYS (ISO strings),
set by set_calendar() from the spec's CONFIG. set_calendar fills the two sets IN PLACE (no `global`
statement), so the helpers see the calendar however the engine runs the snippet: one dict, separate
globals and locals, or wrapped in a function. Nothing here knows a brief.

is_business_day and last_business_day_of_week keep calendar_core's optional (workdays, holidays)
arguments: once assembled, these definitions shadow calendar_core's, whose other functions call
them with three arguments.
"""

import datetime

WORKDAYS = set()
HOLIDAYS = set()
SEARCH_DAYS = 1000  # a helper that finds no business day within this many days returns None


def set_calendar(workdays, holidays):
    WORKDAYS.clear()
    WORKDAYS.update(int(w) for w in workdays)
    HOLIDAYS.clear()
    HOLIDAYS.update(str(h)[:10] for h in holidays)


def _day(d):
    """A date from a date, a datetime or an ISO date string."""
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, str):
        return datetime.date.fromisoformat(d.strip()[:10])
    return d


def date(y, m, d):
    return datetime.date(int(y), int(m), int(d))


def add_days(d, n):
    return _day(d) + datetime.timedelta(days=int(n))


def is_business_day(d, workdays=None, holidays=None):
    d = _day(d)
    days = WORKDAYS if workdays is None else workdays
    off = HOLIDAYS if holidays is None else holidays
    return d.weekday() in days and d.isoformat() not in off


def add_business_days(d, n):
    """The n-th business day strictly after d (strictly before for n < 0); n == 0 gives d."""
    current, n = _day(d), int(n)
    step = datetime.timedelta(days=1 if n > 0 else -1)
    count = 0
    for _ in range(SEARCH_DAYS):
        if count == abs(n):
            return current
        current = current + step
        if is_business_day(current):
            count += 1
    return current if count == abs(n) else None


def next_business_day(d):
    return add_business_days(d, 1)


def business_day_on_or_after(d):
    return _day(d) if is_business_day(d) else add_business_days(d, 1)


def business_day_on_or_before(d):
    return _day(d) if is_business_day(d) else add_business_days(d, -1)


def last_business_day_of_week(d, workdays=None, holidays=None):
    """Last business day of the Monday-Sunday week of d, or None if the week has none."""
    d = _day(d)
    monday = d - datetime.timedelta(days=d.weekday())
    for back in range(6, -1, -1):
        candidate = monday + datetime.timedelta(days=back)
        if is_business_day(candidate, workdays, holidays):
            return candidate
    return None


def end_of_month(d):
    d = _day(d)
    first_next = datetime.date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return first_next - datetime.timedelta(days=1)


def last_business_day_of_month(d):
    """Last business day of the month of d, or None if the month has none."""
    last = end_of_month(d)
    found = business_day_on_or_before(last)
    return found if found is not None and found.month == last.month else None


def weekday_in_week(d, wd, k):
    """Weekday wd (Monday = 0) in the Monday-Sunday week k weeks after the week of d."""
    d = _day(d)
    monday = d - datetime.timedelta(days=d.weekday())
    return monday + datetime.timedelta(days=7 * int(k) + int(wd))
