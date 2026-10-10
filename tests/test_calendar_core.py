"""Calendar core, checked against hand-computed dates.

The holiday list below is TEST DATA ONLY (taken from the public practice Brief A to make the
expected dates checkable against the public practice cases). The module itself knows no dates.
"""

import datetime as dt

import pytest

from freya_builder.sandbox import assemble, hex_json
from freya_builder.sandbox import calendar_core as cc

MON_FRI = {0, 1, 2, 3, 4}
HOLIDAYS = {"2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"}
WED = dt.date(2026, 10, 14)


def test_parse_now():
    assert cc.parse_now("2026-10-14T11:00") == dt.datetime(2026, 10, 14, 11, 0)
    assert cc.parse_now("2026-10-14") == dt.datetime(2026, 10, 14, 0, 0)


@pytest.mark.parametrize(
    "n, expected",
    [(7, dt.date(2026, 10, 23)), (12, dt.date(2026, 11, 2)), (1, dt.date(2026, 10, 15))],
)
def test_nth_business_day_skips_weekends_and_holidays(n, expected):
    # PUB-04 expects the 7th business day (23 Oct); PUB-07 implies the 12th is after 27 Oct.
    assert cc.nth_business_day_after(WED, n, MON_FRI, HOLIDAYS) == expected


def test_holiday_moves_to_next_business_day():
    # PUB-07: 26 Oct (holiday) -> 27 Oct.
    assert cc.next_business_day_on_or_after(dt.date(2026, 10, 26), MON_FRI, HOLIDAYS) == dt.date(
        2026, 10, 27
    )
    assert cc.next_business_day_on_or_after(dt.date(2026, 10, 17), MON_FRI, HOLIDAYS) == dt.date(
        2026, 10, 19
    )


def test_last_business_day_of_week():
    assert cc.last_business_day_of_week(WED, MON_FRI, HOLIDAYS) == dt.date(2026, 10, 16)
    # A week whose Friday is a holiday ends on Thursday.
    assert cc.last_business_day_of_week(dt.date(2026, 12, 23), MON_FRI, HOLIDAYS) == dt.date(
        2026, 12, 24
    )


def test_this_and_next_weekday():
    friday = 4
    assert cc.weekday_in_week(WED, friday, 0) == dt.date(2026, 10, 16)
    assert cc.weekday_in_week(WED, friday, 1) == dt.date(2026, 10, 23)
    assert cc.next_occurrence(dt.date(2026, 10, 16), friday, include_today=False) == dt.date(
        2026, 10, 23
    )


def test_spoken():
    assert cc.spoken(dt.date(2026, 10, 16)) == "Friday 16 October 2026"


def test_assembled_source_runs_like_the_sandbox():
    main = (
        "try:\n"
        "    today = parse_now(vars.get('now')).date()\n"
        "    hol = set(CONFIG['holidays'])\n"
        "    vars['deadline'] = nth_business_day_after(today, CONFIG['n'], set(CONFIG['workdays']), hol).isoformat()\n"
        "except Exception:\n"
        "    vars['deadline'] = ''\n"
    )
    config = {
        "n": 7,
        "workdays": sorted(MON_FRI),
        "holidays": sorted(HOLIDAYS),
        "nested": {"a": {}},
    }
    source = assemble(["calendar_core"], main, config)
    assert "{{" not in source and "}}" not in source
    sandbox_vars = {"now": "2026-10-14T11:00"}
    exec(source, {"vars": sandbox_vars})
    assert sandbox_vars["deadline"] == "2026-10-23"


def test_hex_json_round_trips_nested_braces():
    value = {"a": {"b": [1, {"c": "}}"}]}}
    expr = hex_json(value)
    assert "{" not in expr
    import json  # noqa: F401  (used by eval)

    assert eval(expr) == value
