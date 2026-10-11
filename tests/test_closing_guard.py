"""A goodbye said at most endings stays a closing line (audit of 2026-10-11, cand-eng.9).

spec.early_lines keeps a sentence in the endings only when it is common to every ending of one
step. In fresh extractions the human-transfer row is in every step (a request for a human applies
before and after verification), so one extraction that drops or rewords the goodbye in that row
left no step fully covered: the goodbye became an "early" line in the other 15 rows and the render
told the agent to say it before the customer answers, "never again in the goodbye" (42 of 932
single-row variants of the 74 saved specs). A non-question sentence in more than half of all
endings is a closing line. Questions, and offers or sympathy lines shared by a few endings, are
still moved out of the endings.
"""

import copy
import json
from pathlib import Path

from freya_builder.render import _split_early_lines, render
from freya_builder.spec import early_lines
from freya_builder.toolapi import load_tool_api
from freya_builder.validate import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "tests" / "fixtures" / "fix1_audit_spec_ab4.json").read_text())
TOOLS = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")
BYE = "Thank you. Goodbye."
HELP_FIRST = "Can I help you first?"
SYMPATHY = "I am sorry to hear that."
OFFER = "Would you like me to connect you with the customer support team?"
TASKS = ("opening", "third_party", "identity", "negotiate")


def _row(spec: dict, row_id: str) -> dict:
    return next(r for r in spec["rows"] if r["id"] == row_id)


def _human_in_every_step(human_says: list[str]) -> dict:
    """The fresh-extraction shape: transferred_human is listed in every step."""
    s = copy.deepcopy(SPEC)
    human = _row(s, "transferred_human")
    human["phases"] = list(TASKS)
    human["say_before_end"] = human_says
    return s


def _early_sentences(spec: dict) -> set[str]:
    return {x for says in early_lines(spec).values() for x in says}


def test_goodbye_missing_from_the_all_step_row_stays_in_the_endings():
    s = _human_in_every_step([HELP_FIRST])
    assert BYE not in _early_sentences(s)
    wf = render(s, TOOLS)
    assert validate(wf) == []
    for node in TASKS:
        task = wf["nodes"][node]["task_message"]
        rules = task.split("ENDINGS available", 1)[0]
        assert BYE not in rules, node
        endings = [x for x in task.splitlines() if x.startswith("- transi")]
        for line in endings:
            if "transition_to_ev_transferred_human:" not in line:
                assert f'"{BYE}".' in line, line


def test_goodbye_reworded_in_the_all_step_row_stays_in_the_endings():
    s = _human_in_every_step([HELP_FIRST, "Thank you and goodbye."])
    early = early_lines(s)
    assert BYE not in _early_sentences(s)
    assert "Thank you and goodbye." not in _early_sentences(s)
    assert early == {
        "transferred_human": [HELP_FIRST],
        "transferred_support": [SYMPATHY, OFFER],
        "no_promise_hardship": [SYMPATHY, OFFER],
    }


def test_a_question_at_most_endings_is_still_moved():
    s = _human_in_every_step([HELP_FIRST, BYE])
    question = "Is there anything else I can help you with?"
    for r in s["rows"]:
        r["say_before_end"] = [question, *r["say_before_end"]]
    early = early_lines(s)
    assert all(question in early[r["id"]] for r in s["rows"])
    assert BYE not in _early_sentences(s)


def test_a_repeated_offer_or_sympathy_line_at_half_the_endings_is_still_moved():
    # Mixed (a transfer and a non-transfer ending), common to no step, in exactly half of all
    # endings: not more than half, so it is said before the customer answers, as today.
    s = _human_in_every_step([HELP_FIRST, BYE])
    rows = [r for r in s["rows"] if "negotiate" in r["phases"] and r["id"] != "transferred_human"]
    picked = rows[: len(s["rows"]) // 2]
    assert len(picked) * 2 == len(s["rows"]) and len({bool(r["queue"]) for r in picked}) == 2
    for line in ("I can connect you with the customer support team.", SYMPATHY):
        t = copy.deepcopy(s)
        for r in t["rows"]:
            r["say_before_end"] = [x for x in r["say_before_end"] if x != line]
            if r["id"] in {p["id"] for p in picked}:
                r["say_before_end"] = [line, *r["say_before_end"]]
        early = early_lines(t)
        assert all(line in early[p["id"]] for p in picked), line


def test_an_offer_at_most_endings_of_a_small_step_is_still_moved():
    # Two of the identity step's three endings (a transfer and a non-transfer) share an offer: a
    # majority of that step but 2 of 16 endings, so it is not a closing line.
    s = copy.deepcopy(SPEC)
    offer = "I can connect you with a colleague."
    for rid in ("transferred_human", "not_verified_declined"):
        _row(s, rid)["say_before_end"] = [offer, BYE]
    identity = [r["id"] for r in s["rows"] if "identity" in r["phases"]]
    assert len(identity) == 3
    early = early_lines(s)
    assert early["transferred_human"] == [offer] and early["not_verified_declined"] == [offer]


def test_shared_offer_and_sympathy_from_the_audit_fixture_are_still_moved():
    early = early_lines(_human_in_every_step([HELP_FIRST, BYE]))
    assert early == {
        "transferred_human": [HELP_FIRST],
        "transferred_support": [SYMPATHY, OFFER],
        "no_promise_hardship": [SYMPATHY, OFFER],
    }
    split = _split_early_lines(_human_in_every_step([HELP_FIRST]))
    for r in split["rows"]:
        assert SYMPATHY not in r["say_before_end"] and OFFER not in r["say_before_end"]
        assert HELP_FIRST not in r["say_before_end"]
        if r["id"] != "transferred_human":
            assert r["say_before_end"][-1] == BYE, r["id"]
