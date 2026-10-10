"""Build-time date self-test (audit F32/F33/F36): runs the generated code over a grid of days."""

import copy
import json
from pathlib import Path

from freya_builder.datecheck import check_dates

ROOT = Path(__file__).resolve().parents[1]
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())
NE_FORM = (
    "last_business_day_of_week(today) if last_business_day_of_week(today) != today "
    "else last_business_day_of_week(add_days(today, 7))"
)


def test_correct_spec_has_no_date_problems():
    assert check_dates(copy.deepcopy(SPEC_A)) == []


def test_attempt_that_goes_into_the_past_on_a_weekend_is_reported():
    # variant-r's LLM spec used "!=": on a Saturday attempt 1 was the past Friday.
    spec = copy.deepcopy(SPEC_A)
    spec["attempts"][0]["date_expr"] = NE_FORM
    problems = check_dates(spec)
    assert problems and all("before today" in p for p in problems)
    assert any("Saturday" in p or "Sunday" in p for p in problems)


def test_deadline_that_cannot_be_computed_is_reported():
    spec = copy.deepcopy(SPEC_A)
    spec["bands"][0]["deadline_expr"] = "deadline"  # None inside a band deadline
    assert any("cannot be computed" in p for p in check_dates(spec))


def test_a_business_week_closed_for_holidays_is_reported():
    spec = copy.deepcopy(SPEC_A)
    spec["calendar"]["holidays"] = sorted(
        set(spec["calendar"]["holidays"])
        | {"2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"}
    )
    assert any("has no date" in p for p in check_dates(spec))
