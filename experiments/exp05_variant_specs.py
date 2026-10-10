"""Experiment 05: score extracted specs of the synthetic unseen briefs against their answer keys.

Reads runs/exp04_<variant>.json (from exp04) and tests/fixtures/briefs/<variant>.answer.json.
Date expressions are EVALUATED (local helpers mirroring the sandbox vocabulary) on several days,
so equivalent expressions written differently still match.

    python experiments/exp05_variant_specs.py variant-r variant-c
"""

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from freya_builder.sandbox import calendar_core as cc  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "briefs"
DAYS = [dt.date(2026, 10, d) for d in (12, 14, 16, 19, 22, 28, 30)]


def helpers(workdays, holidays):
    wd, hol = set(workdays), set(holidays)
    return {
        "add_days": lambda d, n: d + dt.timedelta(days=n),
        "add_business_days": lambda d, n: cc.nth_business_day_after(d, n, wd, hol),
        "next_business_day": lambda d: cc.nth_business_day_after(d, 1, wd, hol),
        "business_day_on_or_after": lambda d: cc.next_business_day_on_or_after(d, wd, hol),
        "business_day_on_or_before": lambda d: next(
            d - dt.timedelta(days=i)
            for i in range(30)
            if cc.is_business_day(d - dt.timedelta(days=i), wd, hol)
        ),
        "last_business_day_of_week": lambda d: cc.last_business_day_of_week(d, wd, hol),
        "is_business_day": lambda d: cc.is_business_day(d, wd, hol),
        "date": dt.date,
        "min": min,
        "max": max,
    }


def main():
    for v in sys.argv[1:] or ["variant-r", "variant-c"]:
        spec = json.loads((ROOT / "runs" / f"exp04_{v}.json").read_text())
        key = json.loads((FIX / f"{v}.answer.json").read_text())
        print(f"===== {v}")
        cal = spec["calendar"]
        ok = lambda c, label, extra="": print(("OK  " if c else "DIFF"), label, extra)  # noqa: E731
        ok(
            sorted(cal["holidays"]) == sorted(key["holidays"]),
            "holidays",
            f"{cal['holidays']} vs {key['holidays']}",
        )
        nw = cal["next_weekday"]
        ok(
            (nw == "following_week")
            == ("following calendar week" in key["next_weekday_meaning"].lower()),
            "next_weekday",
            nw,
        )
        q = [x["key"] for x in spec["identity"]["questions"]]
        ok(q == [x["field"] for x in key["identity_questions"]], "identity questions", q)
        env = helpers(cal["business_weekdays"], cal["holidays"])
        kb = sorted(key["bands"], key=lambda b: b["days_late_min"])
        sb = sorted(spec["bands"], key=lambda b: b["min_days"])
        same_shape = [(b["min_days"], b["max_days"], b["attempts"]) for b in sb] == [
            (b["days_late_min"], b["days_late_max"], b["persuasion_attempts"]) for b in kb
        ]
        ok(
            same_shape,
            "bands (min, max, attempts)",
            [(b["min_days"], b["max_days"], b["attempts"]) for b in sb],
        )
        if same_shape:
            bad = []
            for b, k in zip(sb, kb, strict=True):
                for today in DAYS:
                    got = eval(
                        b["deadline_expr"],
                        {"__builtins__": {}},
                        env | {"today": today, "now_date": today},
                    )
                    want = cc.nth_business_day_after(
                        today,
                        k["deadline_business_days_after_today"],
                        set(cal["business_weekdays"]),
                        set(key["holidays"]),
                    )
                    if got != want:
                        bad.append((b["name"], str(today), str(got), str(want)))
            ok(not bad, "band deadlines evaluated on 7 days", bad[:3])
        cw = key["callback_window"]
        ok(
            (spec["callback"]["start"], spec["callback"]["end"]) == (cw["earliest"], cw["latest"]),
            "callback window",
            (spec["callback"]["start"], spec["callback"]["end"]),
        )
        floors = {t["api_value"]: t["floor_field"] for t in spec["products"]["types"]}
        ok(floors == key["floor_field_by_product_type"], "floors", floors)
        pairs = {(r["outcome"], r["reason"]) for r in spec["rows"]}
        want = {(o["outcome"], o.get("reason") or "") for o in key["outcome_table"]}
        ok(
            pairs == want,
            "outcome rows",
            f"missing={sorted(want - pairs)} extra={sorted(pairs - want)}",
        )
        queues = {r["queue"] for r in spec["rows"] if r["queue"]}
        ok(queues == set(key["transfer_queues"].values()), "queues", queues)
        phrases = {p["sentence"].strip().lower() for p in key["required_phrases"]}
        sl = spec["success_lines"]["promise"].strip().lower()
        ok(sl in phrases, "post-promise sentence", spec["success_lines"]["promise"])
        print(
            "attempts:",
            [(a["n"], a["bands"], a["amount"], a["date_expr"]) for a in spec["attempts"]],
        )
        print("opening:", spec["opening"]["line"])


if __name__ == "__main__":
    main()
