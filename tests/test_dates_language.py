"""The DATES rule for a call that is not in English (review 11 Oct, 16:40 UTC): FACTS and the DATE
TABLE spell dates in English, so 'say them as written' contradicted 'Speak <language>'. English
renders stay byte-identical. Nothing here comes from a final case."""

import copy

from test_pipeline import SPEC_A, TOOLS

from freya_builder import language, pipeline


def _negotiate_prompts(spec) -> list[str]:
    wf = pipeline.render(spec, TOOLS)
    return [
        n["task_message"] for n in wf["nodes"].values() if "DATES:" in (n.get("task_message") or "")
    ]


def test_english_dates_rule_is_unchanged():
    prompts = _negotiate_prompts(copy.deepcopy(SPEC_A))
    assert prompts
    for p in prompts:
        assert all(phrase in p for phrase in language.DATES_AS_WRITTEN)
        assert language.localize_dates(p, "English") == p
        assert language.localize_dates(p, None) == p


def test_another_language_says_the_dates_in_that_language():
    spec = copy.deepcopy(SPEC_A)
    spec["language"] = "Turkish"
    prompts = _negotiate_prompts(spec)
    assert prompts
    for p in prompts:
        assert not any(phrase in p for phrase in language.DATES_AS_WRITTEN)
        assert "as written" not in p
        assert "say them in Turkish (the same weekday, day, month and year)" in p
        assert "start your reply with that date from FACTS, said in Turkish" in p
        assert "Compare dates, never weekday names" in p


def test_only_the_dates_rule_differs_between_english_and_turkish():
    en = copy.deepcopy(SPEC_A)
    tr = copy.deepcopy(SPEC_A)
    tr["language"] = "Turkish"
    a, b = pipeline.render(en, TOOLS), pipeline.render(tr, TOOLS)
    a_neg = a["nodes"]["negotiate"]["task_message"]
    b_neg = b["nodes"]["negotiate"]["task_message"]
    assert language.localize_dates(a_neg, "Turkish") == b_neg != a_neg
    for name in a["nodes"]:
        if name != "negotiate":
            assert a["nodes"][name] == b["nodes"][name], name
