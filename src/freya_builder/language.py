"""The language the phone agent speaks, read from the brief (practice briefs: English).

Hackathon page (Overview): "Practice calls are in English, the final case is in Turkish." The
builder's prompts and fixed lines are written in English; for any other language the prompt
tells the agent to say them in that language, and the builder's own goodbye is translated once.
"""

from . import llm
from .trace import Trace

ENGLISH = "English"
GOODBYE_EN = "Thank you for your time. Goodbye."

SYSTEM = (
    "You read a bank's documents for an outbound phone call. Answer with the language the phone "
    "agent must speak with the customer (its English name, e.g. English, Spanish), and translate "
    f'the sentence "{GOODBYE_EN}" into that language as a natural, polite phone goodbye. '
    "months: the 12 month names in that language, January first, in lower case."
)
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "goodbye", "months"],
    "properties": {
        "language": {"type": "string"},
        "goodbye": {"type": "string"},
        "months": {"type": "array", "items": {"type": "string"}},
    },
}
SAMPLE_CHARS = 12000


def detect(trace: Trace, brief_text: str) -> dict:
    """{"language", "goodbye"[, "months"]}: English unless the brief says otherwise. A failed
    call keeps English (a warning, not a stop: the build still produces an agent)."""
    try:
        out = llm.chat_json(
            trace, "detect the call language", SYSTEM, brief_text[:SAMPLE_CHARS], SCHEMA, "language"
        )
    except llm.LLMError as e:
        trace.warn(f"call language not detected ({str(e)[:120]}); prompts stay in English")
        return {"language": ENGLISH, "goodbye": GOODBYE_EN}
    lang = str(out.get("language") or "").strip() or ENGLISH
    if is_english(lang):
        return {"language": ENGLISH, "goodbye": GOODBYE_EN}
    months = [str(m).strip().lower() for m in out.get("months") or [] if str(m).strip()]
    trace.step(f"call language: {lang}")
    return {
        "language": lang,
        "goodbye": str(out.get("goodbye") or "").strip() or GOODBYE_EN,
        **({"months": months} if len(months) == 12 else {}),
    }


def is_english(language: str | None) -> bool:
    return (language or ENGLISH).strip().lower() in ("english", "en")


DATES_AS_WRITTEN = (
    "take both from the DATE TABLE or FACTS and say them as written there.",
    'start your reply with that date as written in FACTS (for example "<weekday> <day> <month> '
    '<year> is ...")',
)


def localize_dates(prompt: str, language: str | None) -> str:
    """For a call in another language, the DATES rule keeps the date but not its English words:
    FACTS and the DATE TABLE spell dates in English. English prompts are returned unchanged."""
    if is_english(language):
        return prompt
    same = "(the same weekday, day, month and year)"
    return prompt.replace(
        DATES_AS_WRITTEN[0],
        f"take both from the DATE TABLE or FACTS and say them in {language} {same}.",
    ).replace(
        DATES_AS_WRITTEN[1],
        f"start your reply with that date from FACTS, said in {language} {same}",
    )


def speak_line(language: str | None) -> str:
    """The prompt's first instruction; unchanged ("Speak English.") for English briefs."""
    if is_english(language):
        return "Speak English."
    return (
        f"Speak {language}, in every turn. This prompt is written in English: say every fixed line "
        f'it quotes ("Please go on.", the cut-off line, read-backs, offers, dates, amounts and the '
        f"goodbye) in {language}, with the same meaning and the same wording each time, and read "
        f"dates, amounts and currencies the way a {language} speaker says them. The customer's "
        f"{language} words for days, months and numbers mean the same as the English ones here."
    )
