"""Summarise a kit/tools/run_cases.py --out JSON file; optionally print the failed calls.

python scripts/show_run.py runs/baseline-minimal-A.json [--calls] [--all]
"""

import argparse
import json

from _kit import freya
from callview import format_messages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--calls", action="store_true", help="print transcripts of failed cases")
    ap.add_argument("--all", action="store_true", help="with --calls: passed cases too")
    a = ap.parse_args()
    run = json.load(open(a.results))
    print(
        f"agent {run['agent_id']} | {run['passed']}/{run['total']} passed | reps {run.get('runs')} "
        f"| {run.get('seconds')} s | simulation {run.get('simulation_id')}"
    )
    for row in run["rows"]:
        mark = "PASS" if row["pass"] else "FAIL"
        tools = " > ".join(row["tools"])
        print(f"{mark} {row['id']} {row['level']:<6} {row['family']:<14} | {tools}")
        for reason in row["failed"]:
            print(f"       - {reason}")
    if not a.calls:
        return
    for row in run["rows"]:
        if (row["pass"] and not a.all) or not row.get("call_id"):
            continue
        call = freya.get_call(row["call_id"])
        ended = call.get("endedReason")
        print(f"\n===== {row['id']} {row['family']} | call {row['call_id']} | {ended}")
        print("\n".join(format_messages(call.get("messages") or [])))


if __name__ == "__main__":
    main()
