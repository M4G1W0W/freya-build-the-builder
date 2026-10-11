"""Unit tests for dashboard/rules.py and the integrity of dashboard/rules_catalog.json (no network).

uv run pytest dashboard/test_rules.py

Whether each catalog quote is still in its source is checked at read time by the dashboard (a changed
source shows as stale there), not here: the team's docs keep changing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rules as RC  # noqa: E402

CATALOG = json.loads(RC.CATALOG.read_text())
LABELS = {"official", "internal", "locally derived"}
CATEGORIES = (
    set(RC.ORGANIZER)
    | set(RC.INTERNAL)
    | {
        "interpretation",
        "clarification",
        "case_provenance",
        "source_date",
    }
)


def test_find_quote_exact_then_whitespace_normalised():
    text = "Rules\n\nNothing from a hidden brief\n  may be written into the builder.\n"
    assert RC.find_quote(text, "Nothing from a hidden brief")[2] == "exact"
    start, end, how = RC.find_quote(text, "hidden brief may be written")
    assert how == "whitespace-normalised" and text[start:end] == "hidden brief\n  may be written"
    assert RC.find_quote(text, "may be changed") is None


def test_case_diff_reports_each_field_and_missing_cases():
    kit = [{"id": "PUB-01", "identity": {"dob": "x"}, "checks": ["a"]}, {"id": "PUB-02"}]
    page = [{"id": "PUB-01", "checks": ["a"]}, {"id": "PUB-03"}]
    diffs = RC.case_diff(kit, page)
    assert {"case": "PUB-01", "field": "identity", "kit": {"dob": "x"}, "page": None} in diffs
    assert {"case": "PUB-02", "field": "(whole case)", "kit": True, "page": False} in diffs
    assert {"case": "PUB-03", "field": "(whole case)", "kit": False, "page": True} in diffs


def test_istanbul_is_utc_plus_three():
    t = RC._istanbul("2026-10-11T17:00:00Z")
    assert t["utc"] == "2026-10-11T17:00:00Z" and t["istanbul"].startswith("Sun 11 Oct 20:00")


def test_catalog_labels_and_categories_are_valid():
    registry = {s["file"]: s for s in CATALOG["sources"]}
    assert {s["label"] for s in CATALOG["sources"]} <= LABELS
    for it in CATALOG["items"]:
        assert it["category"] in CATEGORIES, it["topic"]
        assert it["source_file"] in registry, it["source_file"]
        assert it["quote"].strip(), it["topic"]


def test_organizer_rules_and_clarifications_cite_only_official_sources():
    registry = {s["file"]: s["label"] for s in CATALOG["sources"]}
    for it in CATALOG["items"]:
        if it["category"] in RC.ORGANIZER or it["category"] == "clarification":
            assert registry[it["source_file"]] == "official", (it["topic"], it["source_file"])


def test_fixtures_are_never_labelled_official():
    for s in CATALOG["sources"]:
        if s["file"].startswith("tests/fixtures/"):
            assert s["label"] == "locally derived", s["file"]
        if s["file"].startswith("kit/"):
            assert s["label"] == "official", s["file"]


def test_deadlines_rest_on_official_quotes():
    registry = {s["file"]: s["label"] for s in CATALOG["sources"]}
    for d in CATALOG["deadlines"]:
        assert d["utc"].endswith("Z") and d["derivation"]
        assert all(registry[b["source_file"]] == "official" for b in d["basis"]), d["what"]
