import copy
import json
from pathlib import Path

import pytest

from freya_builder.expr import check_expr
from freya_builder.spec import SPEC_SCHEMA, check_spec, schema_problems
from freya_builder.toolapi import load_tool_api

ROOT = Path(__file__).resolve().parents[1]
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())
TOOLS = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")


def test_fixture_matches_strict_schema():
    assert schema_problems(SPEC_A, SPEC_SCHEMA) == []


def test_fixture_is_consistent_with_kit_tool_api():
    assert check_spec(SPEC_A, TOOLS) == []


def test_schema_is_strict_everywhere():
    def walk(s, path="root"):
        if s.get("type") == "object":
            assert s.get("additionalProperties") is False, path
            assert set(s["required"]) == set(s["properties"]), path
            for k, sub in s["properties"].items():
                walk(sub, f"{path}.{k}")
        if s.get("type") == "array":
            walk(s["items"], f"{path}[]")

    walk(SPEC_SCHEMA)


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda s: s["rows"][0].update(outcome="promised"), "not in API enum"),
        (lambda s: s["rows"][2].update(queue="plans"), "queue 'plans'"),
        (lambda s: s["identity"]["questions"][0].update(key="postcode"), "identity question"),
        (lambda s: s["identity"].update(gate_field="verified_all"), "gate_field"),
        (lambda s: s["promise_fields"].update(date_field="when"), "create_promise has no field"),
        (lambda s: s["default_rows"].update(opening="nope"), "default row"),
        (
            lambda s: s["default_rows"].update(
                negotiate=next(r["id"] for r in s["rows"] if r["queue"])
            ),
            "must not transfer",
        ),
        (lambda s: s["bands"][0].update(deadline_expr="__import__('os')"), "deadline"),
        (lambda s: s["close_precedence"][1].update(row="ghost"), "unknown row"),
        (lambda s: s["products"].update(id_field="pid"), "is not a field of"),
        (lambda s: s["products"]["types"][0].update(api_value="mortgage"), "product type"),
        (lambda s: s["products"]["types"][0].update(floor_field="min_due"), "floor field"),
    ],
)
def test_check_spec_catches(mutate, needle):
    spec = copy.deepcopy(SPEC_A)
    mutate(spec)
    problems = check_spec(spec, TOOLS)
    assert any(needle in p for p in problems), problems


@pytest.mark.parametrize(
    "expr",
    [
        "add_business_days(today, 12)",
        "last_business_day_of_week(today) if last_business_day_of_week(today) != today else last_business_day_of_week(add_days(today, 7))",
        "min(deadline, end_of_month(today))",
        "deadline",
    ],
)
def test_good_expressions(expr):
    assert check_expr(expr) == []


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('x')",
        "today.replace(day=1)",
        "{'a': 1}",
        "lambda: 1",
        "add_business_days(today, n=3)",
        "open('f')",
        "",
        "1.5",
    ],
)
def test_bad_expressions(expr):
    assert check_expr(expr) != []
