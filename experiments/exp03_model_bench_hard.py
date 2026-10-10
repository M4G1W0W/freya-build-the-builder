"""Experiment 03: model choice on the HARD inputs — synthetic unseen briefs (tests/fixtures/briefs).

variant-r: raw bank material (mail + policy extract + amending memo + code list).
variant-c: clean spec with every value changed (identity, bands, holidays, outcome codes, queues).
Same extraction schema as exp02; truth comes from each fixture's answer key. Each model runs
twice per fixture.

    python experiments/exp03_model_bench_hard.py [model ...]
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from exp02_model_bench import DEFAULT_MODELS, ROOT, SCHEMA, SYSTEM, one  # noqa: F401

FIX = ROOT / "tests" / "fixtures" / "briefs"
norm = lambda s: str(s or "").strip().lower()  # noqa: E731


def truth_from_key(key: dict) -> dict:
    queues = key.get("transfer_queues") or {}
    return {
        "identity_fields_in_order": [q["field"] for q in key["identity_questions"]],
        "max_wrong_answers_total": key["max_wrong_answers_total"],
        "holidays": sorted(key["holidays"]),
        "bands": sorted(
            (
                b["days_late_min"],
                b["days_late_max"],
                b["deadline_business_days_after_today"],
                b["persuasion_attempts"],
            )
            for b in key["bands"]
        ),
        "callback_earliest": key["callback_window"]["earliest"],
        "callback_latest": key["callback_window"]["latest"],
        "floors": {(norm(k), norm(v)) for k, v in key["floor_field_by_product_type"].items()},
        "pairs": {(norm(o["outcome"]), norm(o.get("reason"))) for o in key["outcome_table"]},
        "phrases": {norm(p["sentence"]) for p in key.get("required_phrases") or []},
        "next_following_week": "following calendar week" in norm(key["next_weekday_meaning"]),
        "hardship_queue": next((v for k, v in queues.items() if "hardship" in k), ""),
        "human_queue": queues.get("human_request", ""),
    }


def score(out: dict, t: dict) -> tuple[int, list[str]]:
    m = []
    if out.get("identity_fields_in_order") != t["identity_fields_in_order"]:
        m.append(f"identity={out.get('identity_fields_in_order')}")
    if out.get("max_wrong_answers_total") != t["max_wrong_answers_total"]:
        m.append(f"max_wrong={out.get('max_wrong_answers_total')}")
    if sorted(out.get("holidays", [])) != t["holidays"]:
        m.append(f"holidays={sorted(out.get('holidays', []))}")
    bands = sorted(
        (
            b["days_late_min"],
            b["days_late_max"],
            b["deadline_nth_business_day_after_today"],
            b["persuasion_attempts"],
        )
        for b in out.get("bands", [])
    )
    if bands != t["bands"]:
        m.append(f"bands={bands}")
    if (out.get("callback_earliest"), out.get("callback_latest")) != (
        t["callback_earliest"],
        t["callback_latest"],
    ):
        m.append(f"callback={out.get('callback_earliest')}-{out.get('callback_latest')}")
    floors = {
        (norm(f["product_type"]), norm(f["field"]))
        for f in out.get("floor_field_by_product_type", [])
    }
    if floors != t["floors"]:
        m.append(f"floors={sorted(floors)}")
    pairs = {
        (norm(p["outcome"]), norm(p["reason"]).replace("none", ""))
        for p in out.get("outcome_reason_pairs", [])
    }
    if pairs != t["pairs"]:
        m.append(f"pairs -{sorted(t['pairs'] - pairs)} +{sorted(pairs - t['pairs'])}")
    if norm(out.get("post_promise_sentence")) not in t["phrases"]:
        m.append(f"post_promise={out.get('post_promise_sentence')!r}")
    if out.get("next_weekday_means_following_calendar_week") != t["next_following_week"]:
        m.append("next_weekday")
    if norm(out.get("queue_for_hardship_support")) != norm(t["hardship_queue"]):
        m.append(f"hardship_q={out.get('queue_for_hardship_support')}")
    if norm(out.get("queue_for_human_request")) != norm(t["human_queue"]):
        m.append(f"human_q={out.get('queue_for_human_request')}")
    return 11 - len(m), m


def main() -> None:
    models = sys.argv[1:] or DEFAULT_MODELS
    fixtures = {}
    for v in ("variant-r", "variant-c"):
        brief = (FIX / f"{v}.md").read_text()
        api = (FIX / f"{v}.openapi.json").read_text()
        user = f"# BRIEF\n\n{brief}\n\n# TOOL API (OpenAPI)\n\n{api}"
        fixtures[v] = (user, truth_from_key(json.loads((FIX / f"{v}.answer.json").read_text())))
    jobs = [(m, v) for m in models for v in fixtures for _ in range(2)]

    def run(job):
        m, v = job
        r = one(m, fixtures[v][0])
        r["fixture"] = v
        if "out" in r:
            r["score"], r["misses"] = score(r["out"], fixtures[v][1])
        return r

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(run, jobs))
    (ROOT / "runs" / "exp03_model_bench_hard.json").write_text(
        json.dumps(results, indent=1, default=list)
    )
    print(f"{'model':<13} {'fixture':<10} {'run1':>6} {'run2':>6} {'same':>5} {'secs':>8}  misses")
    for m in models:
        for v in fixtures:
            rs = [r for r in results if r["model"] == m and r["fixture"] == v]
            if any("error" in r for r in rs):
                print(f"{m:<13} {v:<10} ERROR {next(r['error'] for r in rs if 'error' in r)[:120]}")
                continue
            same = rs[0]["out"] == rs[1]["out"]
            secs = "/".join(f"{r['seconds']:.0f}" for r in rs)
            miss = "; ".join(sorted(set(rs[0]["misses"] + rs[1]["misses"])))[:230]
            print(
                f"{m:<13} {v:<10} {rs[0]['score']:>3}/11 {rs[1]['score']:>3}/11 {str(same):>5} {secs:>8}  {miss}"
            )


if __name__ == "__main__":
    main()
