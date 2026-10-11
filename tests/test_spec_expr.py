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
        (lambda s: s["identity"].update(gate_field=""), "identity gate_field is empty"),
        (lambda s: s["identity"].update(answer_ok_field=""), "identity answer_ok_field is empty"),
        (lambda s: s["identity"].update(gate_field="wrong_answers_left"), "is integer"),
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


def test_every_note_reason_finalize_can_close_with_has_a_row():
    # audit F46/F64/F71: finalize's first_note_reason_not closes with the note's reason; without a
    # matching row that reason may not exist in close_call's vocabulary.
    spec = copy.deepcopy(SPEC_A)
    spec["notes"]["used"] = True
    spec["close_precedence"].insert(
        -1,
        {
            "when": "any_note",
            "note_reason": "paid",
            "then": "first_note_reason_not",
            "row": "",
            "outcome": "no_promise",
        },
    )
    assert not [p for p in check_spec(spec, TOOLS) if "no row" in p]
    spec["rows"] = [r for r in spec["rows"] if r["id"] != "no_promise_dispute"]
    assert any("no row ('no_promise', 'dispute')" in p for p in check_spec(spec, TOOLS))


def test_floor_percent_is_checked():
    spec = copy.deepcopy(SPEC_A)
    for t in spec["products"]["types"]:
        t["floor_field"], t["floor_percent"] = "", 30
    assert check_spec(spec, TOOLS) == []
    spec["products"]["types"][0]["floor_percent"] = 150
    assert any("floor_percent 150 not in 0..100" in p for p in check_spec(spec, TOOLS))
    spec = copy.deepcopy(SPEC_A)
    spec["products"]["types"][0]["floor_field"] = ""
    assert any("floor field ''" in p for p in check_spec(spec, TOOLS))


SPEC_C = json.loads((ROOT / "tests" / "fixtures" / "spec_variant_c.json").read_text())
TOOLS_C = load_tool_api(ROOT / "tests" / "fixtures" / "briefs" / "variant-c.openapi.json")


def with_ending_wins(**entry) -> dict:
    """The variant-c spec with an ending_wins entry before promise_recorded (review gap 7)."""
    spec = copy.deepcopy(SPEC_C)
    rule = {"when": "ending_wins", "note_reason": "insolvency", "then": "row"}
    rule |= {"row": "no_commitment_insolvency", "outcome": ""} | entry
    rules = spec["close_precedence"]
    rules.insert(next(i for i, c in enumerate(rules) if c["when"] == "promise_recorded"), rule)
    return spec


def test_ending_wins_entry_is_accepted():
    assert schema_problems(with_ending_wins(), SPEC_SCHEMA) == []
    assert check_spec(with_ending_wins(), TOOLS_C) == []
    assert check_spec(with_ending_wins(note_reason=""), TOOLS_C) == []


@pytest.mark.parametrize(
    "entry, needle",
    [
        ({"then": "event_row"}, "then must be 'row'"),
        ({"row": "ghost"}, "unknown row 'ghost'"),
        ({"row": "transferred_senior"}, "without a queue"),
        ({"row": "not_verified_failed"}, "negotiate-phase"),
        ({"note_reason": "bankrupt"}, "not an add_note reason"),
        ({"note_reason": "already_paid"}, "already used by"),
    ],
)
def test_ending_wins_guards(entry, needle):
    problems = check_spec(with_ending_wins(**entry), TOOLS_C)
    assert any(needle in p for p in problems), problems


def test_ending_wins_note_reason_needs_notes():
    spec = copy.deepcopy(SPEC_A)  # Brief A uses no add_note
    rule = {"when": "ending_wins", "note_reason": "hardship", "then": "row"}
    spec["close_precedence"].insert(0, rule | {"row": "no_promise_hardship", "outcome": ""})
    assert any("notes are not used" in p for p in check_spec(spec, TOOLS))
    spec["close_precedence"][0]["note_reason"] = ""
    assert check_spec(spec, TOOLS) == []
