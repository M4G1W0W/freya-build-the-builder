"""Experiment 04: does the LLM front end (pipeline.extract) produce the right spec?

Brief A -> compared field by field with the hand-written fixture tests/fixtures/spec_a.json.
Prints differences on the typed fields that drive code (bands, attempts, calendar, identity,
rows, precedence, field names). Prose fields are shown side by side for review, not scored.

    python experiments/exp04_extract_vs_truth.py [brief files...] [--api tools.json] [--out runs/x.json]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import _kit  # noqa: E402,F401

from freya_builder.cli import read_briefs  # noqa: E402
from freya_builder.pipeline import extract  # noqa: E402
from freya_builder.toolapi import load_tool_api  # noqa: E402
from freya_builder.trace import Trace  # noqa: E402

TYPED = [
    "meta.max_products",
    "calendar",
    "products",
    "bands",
    "promise_window",
    "callback",
    "identity.questions",
    "identity.question_field",
    "identity.answer_field",
    "identity.gate_field",
    "identity.answer_ok_field",
    "identity.remaining_field",
    "identity.hint_field",
    "identity.failed_row",
    "notes",
    "promise_fields",
    "transfer_field",
    "close_fields",
]


def get(d, path):
    for part in path.split("."):
        d = d[part]
    return d


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    api = next(
        (sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--api"),
        str(ROOT / "kit/tools/openapi.json"),
    )
    out = next(
        (sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--out"),
        str(ROOT / "runs/exp04_spec.json"),
    )
    briefs = args or [str(ROOT / "kit/briefs/brief-a.md")]
    spec = extract(Trace(), read_briefs(briefs), load_tool_api(api))
    Path(out).write_text(json.dumps(spec, indent=1))
    truth = json.loads((ROOT / "tests/fixtures/spec_a.json").read_text())
    if len(briefs) != 1 or not briefs[0].endswith("brief-a.md"):
        print(f"spec written to {out} (no fixture to compare)")
        return
    for path in TYPED:
        a, b = get(spec, path), get(truth, path)
        if path in ("identity.questions",):
            a = [(q["key"], q["format"]) for q in a]
            b = [(q["key"], q["format"]) for q in b]
        if path == "products":
            a = {k: v for k, v in a.items() if k != "types"} | {
                "types": sorted((t["api_value"], t["floor_field"]) for t in a["types"])
            }
            b = {k: v for k, v in b.items() if k != "types"} | {
                "types": sorted((t["api_value"], t["floor_field"]) for t in b["types"])
            }
        if path == "bands":
            a = [
                (x["min_days"], x["max_days"], x["deadline_expr"].replace(" ", ""), x["attempts"])
                for x in a
            ]
            b = [
                (x["min_days"], x["max_days"], x["deadline_expr"].replace(" ", ""), x["attempts"])
                for x in b
            ]
        if path == "callback":
            a = {k: v for k, v in a.items() if k != "day_exprs"} | {
                "days": [e.replace(" ", "") for e in a["day_exprs"]]
            }
            b = {k: v for k, v in b.items() if k != "day_exprs"} | {
                "days": [e.replace(" ", "") for e in b["day_exprs"]]
            }
        print(
            ("OK  " if a == b else "DIFF"),
            path,
            "" if a == b else f"\n     got:  {a}\n     want: {b}",
        )
    rows_a = sorted(
        (r["outcome"], r["reason"], tuple(sorted(r["phases"])), r["queue"]) for r in spec["rows"]
    )
    rows_b = sorted(
        (r["outcome"], r["reason"], tuple(sorted(r["phases"])), r["queue"]) for r in truth["rows"]
    )
    print(("OK  " if rows_a == rows_b else "DIFF"), "rows (outcome, reason, phases, queue)")
    for r in sorted(set(rows_a) ^ set(rows_b)):
        print("     ", "got " if r in rows_a else "want", r)
    print(
        "attempts:", [(x["n"], x["bands"], x["amount"], x["date_expr"]) for x in spec["attempts"]]
    )
    print(
        "precedence:",
        [(c["when"], c["then"], c["row"] or c["outcome"]) for c in spec["close_precedence"]],
    )
    print("opening.line:", spec["opening"]["line"])
    print("disclosure:", spec["disclosure"])
    print("success/failure:", spec["success_lines"], spec["failure_rules"])
    print("unmodeled:", spec["unmodeled"])


if __name__ == "__main__":
    main()
