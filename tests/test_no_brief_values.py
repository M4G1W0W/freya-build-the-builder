"""Guard (docs/design.md §5): the builder's code must not know the practice briefs.

Public Brief A/B values may appear only in tests/ and docs/. A hidden-brief value must never be
added anywhere (competition rule); this test catches the public ones.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENY = [
    "2026-10-26",
    "2026-11-11",
    "2026-11-26",
    "2026-12-25",
    "phone_last4",
    "date_of_birth",
    "minimum_payment",
    "instalment_amount",
    "restructuring",
    "Freya Bank",
    "collections team",
    "text message confirming",
    "day_month_swapped",
    "wrong_answers_left",
    "freya-bank-mock",
]


def builder_sources() -> list[Path]:
    files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "builder").rglob("*.py"))
    assert files
    return files


def test_no_practice_brief_values_in_builder_code():
    hits = []
    for path in builder_sources():
        text = path.read_text()
        hits += [f"{path.relative_to(ROOT)}: {token}" for token in DENY if token in text]
    assert hits == []
