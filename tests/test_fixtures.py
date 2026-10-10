"""The synthetic unseen-brief fixtures stay loadable and self-consistent.

tests/fixtures/briefs/variant-{c,r}: synthetic variants of the PUBLIC practice briefs
(see their changes_vs_public lists). Used to test that the builder generalises.
"""

import json
from pathlib import Path

import pytest

from freya_builder.toolapi import load_tool_api

FIX = Path(__file__).resolve().parent / "fixtures" / "briefs"
KIT_API = Path(__file__).resolve().parents[1] / "kit" / "tools" / "openapi.json"
VARIANTS = ["variant-c", "variant-r"]


@pytest.mark.parametrize("v", VARIANTS)
def test_fixture_tool_api_has_the_kit_tool_names(v):
    names = {t.name for t in load_tool_api(FIX / f"{v}.openapi.json")}
    assert names == {t.name for t in load_tool_api(KIT_API)}


@pytest.mark.parametrize("v", VARIANTS)
def test_answer_key_outcomes_match_tool_api_enum(v):
    key = json.loads((FIX / f"{v}.answer.json").read_text())
    tools = {t.name: t for t in load_tool_api(FIX / f"{v}.openapi.json")}
    outcome_field = next(f for f in tools["close_call"].request if f.enum)
    assert {o["outcome"] for o in key["outcome_table"]} == set(outcome_field.enum)


@pytest.mark.parametrize("v", VARIANTS)
def test_answer_key_values_differ_from_public_where_claimed(v):
    key = json.loads((FIX / f"{v}.answer.json").read_text())
    assert key["changes_vs_public"], "a variant must list its deliberate changes"
    assert key["holidays"] != ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"]
