"""Experiment 02: which OpenAI model should the builder use to read briefs?

Task: extract a compact fact set from public Briefs A+B with a strict JSON schema (the same kind
of call the builder makes). Each model runs twice. Scored against TRUTH below, which was checked
by hand against kit/briefs/brief-a.md and brief-b.md (test data only; never used by the builder).

    python experiments/exp02_model_bench.py [model ...]
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import _kit  # noqa: E402,F401  (loads .env)

from freya_builder.llm import LLMError, chat_json  # noqa: E402
from freya_builder.trace import Trace  # noqa: E402

DEFAULT_MODELS = [
    "gpt-6.1-sol",
    "gpt-6-sol",
    "gpt-6-astra",
    "gpt-5.6-sol",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.2",
    "o3",
]

STR = {"type": "string"}
INT = {"type": "integer"}


def obj(props: dict) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


SCHEMA = obj(
    {
        "identity_fields_in_order": {"type": "array", "items": STR},
        "max_wrong_answers_total": INT,
        "holidays": {"type": "array", "items": STR},
        "bands": {
            "type": "array",
            "items": obj(
                {
                    "days_late_min": INT,
                    "days_late_max": INT,
                    "deadline_nth_business_day_after_today": INT,
                    "persuasion_attempts": INT,
                }
            ),
        },
        "callback_earliest": STR,
        "callback_latest": STR,
        "floor_field_by_product_type": {
            "type": "array",
            "items": obj({"product_type": STR, "field": STR}),
        },
        "outcome_reason_pairs": {
            "type": "array",
            "items": obj({"outcome": STR, "reason": STR}),
        },
        "post_promise_sentence": STR,
        "next_weekday_means_following_calendar_week": {"type": "boolean"},
        "queue_for_hardship_support": STR,
        "queue_for_human_request": STR,
    }
)

TRUTH = {
    "identity_fields_in_order": ["date_of_birth", "phone_last4"],
    "max_wrong_answers_total": 3,
    "holidays": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"],
    "bands": [(1, 7, 12, 1), (8, 45, 7, 2)],
    "callback_earliest": "10:00",
    "callback_latest": "19:00",
    "floor_field_by_product_type": {
        ("credit_card", "minimum_payment"),
        ("personal_loan", "instalment_amount"),
        ("car_loan", "instalment_amount"),
    },
    "outcome_reason_pairs": {
        ("promise", ""),
        ("paid", ""),
        ("transferred", "restructuring"),
        ("transferred", "human"),
        ("transferred", "support"),
        ("no_promise", "refused"),
        ("no_promise", "hardship"),
        ("no_promise", "dispute"),
        ("no_promise", "service_error"),
        ("not_verified", "failed"),
        ("not_verified", "declined"),
        ("not_reached", "callback"),
        ("not_reached", "no_callback"),
        ("not_reached", "wrong_number"),
        ("not_reached", "deceased"),
        ("not_reached", "unclear"),
    },
    "post_promise_sentence": "You will receive a text message confirming this promise.",
    "next_weekday_means_following_calendar_week": True,
    "queue_for_hardship_support": "support",
    "queue_for_human_request": "general",
}

SYSTEM = (
    "You read a bank's specification for outbound collections calls and extract facts exactly as "
    "written. Use the tool API to name identity fields and enum values. Copy required sentences "
    "verbatim. Use empty string for a reason that the outcome table leaves empty. Dates as YYYY-MM-DD."
)


def score(out: dict) -> tuple[int, list[str]]:
    misses = []
    norm = lambda s: str(s or "").strip().lower()  # noqa: E731
    for key in (
        "identity_fields_in_order",
        "max_wrong_answers_total",
        "callback_earliest",
        "callback_latest",
        "next_weekday_means_following_calendar_week",
        "queue_for_hardship_support",
        "queue_for_human_request",
    ):
        if out.get(key) != TRUTH[key]:
            misses.append(f"{key}={out.get(key)!r}")
    if sorted(out.get("holidays", [])) != TRUTH["holidays"]:
        misses.append("holidays")
    bands = sorted(
        (
            b["days_late_min"],
            b["days_late_max"],
            b["deadline_nth_business_day_after_today"],
            b["persuasion_attempts"],
        )
        for b in out.get("bands", [])
    )
    if bands != TRUTH["bands"]:
        misses.append(f"bands={bands}")
    floors = {
        (norm(f["product_type"]), norm(f["field"]))
        for f in out.get("floor_field_by_product_type", [])
    }
    if floors != TRUTH["floor_field_by_product_type"]:
        misses.append(f"floors={sorted(floors)}")
    pairs = {
        (norm(p["outcome"]), norm(p["reason"]).replace("none", ""))
        for p in out.get("outcome_reason_pairs", [])
    }
    if pairs != TRUTH["outcome_reason_pairs"]:
        misses.append(
            f"pairs missing={sorted(TRUTH['outcome_reason_pairs'] - pairs)} extra={sorted(pairs - TRUTH['outcome_reason_pairs'])}"
        )
    if norm(out.get("post_promise_sentence")) != norm(TRUTH["post_promise_sentence"]):
        misses.append("post_promise_sentence")
    total = 11
    return total - len(misses), misses


def one(model: str, user: str) -> dict:
    trace = Trace(stream=StringIO())
    t0 = time.monotonic()
    try:
        out = chat_json(trace, "bench extract", SYSTEM, user, SCHEMA, model=model, retries=1)
    except LLMError as e:
        return {"model": model, "error": str(e)[:300], "seconds": time.monotonic() - t0}
    s, misses = score(out)
    return {
        "model": model,
        "score": s,
        "misses": misses,
        "seconds": time.monotonic() - t0,
        "out": out,
    }


def main() -> None:
    models = sys.argv[1:] or DEFAULT_MODELS
    briefs = "\n\n".join(
        (ROOT / "kit" / "briefs" / f).read_text() for f in ("brief-a.md", "brief-b.md")
    )
    api = (ROOT / "kit" / "tools" / "openapi.json").read_text()
    user = f"# BRIEF (Brief B builds on Brief A)\n\n{briefs}\n\n# TOOL API (OpenAPI)\n\n{api}"
    jobs = [(m, user) for m in models for _ in range(2)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda j: one(*j), jobs))
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / "exp02_model_bench.json").write_text(
        json.dumps(results, indent=1, default=list)
    )
    by = {}
    for r in results:
        by.setdefault(r["model"], []).append(r)
    print(f"{'model':<14} {'run1':>5} {'run2':>5} {'same':>5} {'secs':>12}  misses")
    for m in models:
        rs = by[m]
        if any("error" in r for r in rs):
            print(f"{m:<14} ERROR {next(r['error'] for r in rs if 'error' in r)[:150]}")
            continue
        same = rs[0]["out"] == rs[1]["out"]
        secs = "/".join(f"{r['seconds']:.0f}" for r in rs)
        miss = "; ".join(sorted(set(rs[0]["misses"] + rs[1]["misses"])))[:200]
        print(
            f"{m:<14} {rs[0]['score']:>3}/11 {rs[1]['score']:>3}/11 {str(same):>5} {secs:>12}  {miss}"
        )


if __name__ == "__main__":
    main()
