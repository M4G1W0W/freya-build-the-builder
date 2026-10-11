"""Fix 1 semantic audit (2026-10-11): an ending's "First say" list must not hold a mid-call question.

Fixture: a fresh cand-eng.6 (a170935) --dry extraction of Brief A + B (fresh6/spec-ab4). Fix 1's
say_before_end sentence pulled mid-call lines into closing rows: transferred_support and
no_promise_hardship carry "Would you like me to connect you with the customer support team?", and
transferred_human carries "Can I help you first?". The ENDINGS header has the agent say the listed
sentences and call the transition in the SAME message, so the question is asked again (brief A rules
32, 42: offer once, ask once) and can never be answered. Seen in 6 of 16 fresh Fix-1 extractions
(ab3, ab4, raw2, vr2, vc2, vc4), 0 of 13 pre-Fix-1 ones. Not fixed: strict xfail until it is.
"""

import json
import re
from pathlib import Path

import pytest

from freya_builder.render import _endings_text

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "tests" / "fixtures" / "fix1_audit_spec_ab4.json").read_text())


def _closing_questions(spec: dict) -> list[str]:
    out = []
    for stage in ("opening", "third_party", "identity", "negotiate"):
        for line in _endings_text(spec, stage).splitlines()[1:]:
            said = line.split(" First say ", 1)[1] if " First say " in line else ""
            out += [f"{stage}: {s}" for s in re.findall(r'"([^"]*)"', said) if s.endswith("?")]
    return out


def test_fixture_reproduces_the_audit_finding():
    found = _closing_questions(SPEC)
    assert any("customer support team?" in q for q in found)
    assert any("Can I help you first?" in q for q in found)


@pytest.mark.xfail(strict=True, reason="Fix 1 audit: closing rows hold mid-call questions; open")
def test_no_ending_asks_a_question_in_its_goodbye_message():
    assert _closing_questions(SPEC) == []
