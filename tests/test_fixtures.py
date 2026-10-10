"""The synthetic unseen-brief fixtures stay loadable and self-consistent.

tests/fixtures/briefs/variant-{c,r}: synthetic variants of the PUBLIC practice briefs
(see their changes_vs_public lists). Used to test that the builder generalises.
tests/fixtures/briefs/raw-a.md: Brief A re-told as raw material (e-mail, policy extract, amending
memo, CRM code list) with the SAME meaning, so it can be scored on the public Brief A cases.
"""

import json
import re
from pathlib import Path

import pytest

from freya_builder.datecheck import check_dates
from freya_builder.render import render
from freya_builder.spec import SPEC_SCHEMA, check_spec, product_slots, schema_problems
from freya_builder.toolapi import load_tool_api
from freya_builder.validate import unsent_required, validate

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


def test_raw_a_code_list_maps_to_kit_enums():
    text = (FIX / "raw-a.md").read_text()
    tools = {t.name: t for t in load_tool_api(KIT_API)}
    outcomes = set(next(f for f in tools["close_call"].request if f.enum).enum)
    queues = set(next(f for f in tools["transfer_to_agent"].request if f.enum).enum)
    rows = re.findall(r"^\| [A-Z-]+ \| [^|]+ \| `(\w+)` \| (?:`(\w+)`|\(none\)) \|$", text, re.M)
    assert {o for o, _ in rows} == outcomes
    assert len(rows) == 16
    listed = set(re.findall(r"^\| Q-[A-Z]+ \| [^|]+ \| `(\w+)` \|$", text, re.M))
    assert listed == queues


def test_extra_cases_match_the_public_accounts_they_reuse():
    # run_cases.py seeds the mock bank by case id, so an extra case must keep that case's customer.
    public = {
        c["id"]: c for c in json.loads((KIT_API.parents[1] / "public-test-set.json").read_text())
    }
    extra = json.loads((FIX.parent / "cases" / "extra-b.json").read_text())
    assert len({c["id"] for c in extra}) == len(extra)
    for c in extra:
        p = public[c["id"]]
        assert (c["brief"], c["variables"], c["identity"]) == (
            p["brief"],
            p["variables"],
            p["identity"],
        )
        assert {n["product_id"] for n in c["expected"]["notes"]} <= {
            f"p{i + 1}" for i in range(len(p["products"]))
        }


@pytest.mark.parametrize("variant", ["c", "r"])
def test_single_file_multi_product_variants_build_cleanly(variant):
    # Review gap 16: the hidden briefs are one file each, with customers of one to three products.
    # These specs were extracted at dcb3915 from our own made-up variants (with their changed tool
    # APIs); every check the build runs must stay clean on them.
    fx = Path(__file__).resolve().parent / "fixtures"
    spec = json.loads((fx / f"spec_variant_{variant}.json").read_text())
    tools = load_tool_api(fx / "briefs" / f"variant-{variant}.openapi.json")
    assert schema_problems(spec, SPEC_SCHEMA) == []
    assert check_spec(spec, tools) == []
    assert check_dates(spec) == []
    assert product_slots(spec) == 3
    wf = render(spec, tools, (fx / "briefs" / f"variant-{variant}.md").read_text())
    assert validate(wf) == [] and unsent_required(wf, tools) == []
