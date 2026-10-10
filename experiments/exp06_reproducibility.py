"""Experiment 06 (design E10): does the same brief give the same spec on independent runs?

Extracts the spec N times in parallel and reports which leaves differ. Typed leaves (numbers,
enums, field names, expressions) drive code and must match; prose leaves may vary in wording.

    python experiments/exp06_reproducibility.py [--n 2] brief.md [...] --api tools.json
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import _kit  # noqa: E402,F401

from freya_builder.cli import read_briefs  # noqa: E402
from freya_builder.pipeline import extract  # noqa: E402
from freya_builder.toolapi import load_tool_api  # noqa: E402
from freya_builder.trace import Trace  # noqa: E402

PROSE = (
    "trigger",
    "label",
    "ask",
    "line",
    "intro",
    "sentence",
    "note",
    "explain",
    "instruction",
    "rules",
    "criteria",
    "first_ask",
    "unmodeled",
    "stage_rules",
    "failure_rules",
    "success_lines",
    "_prompt_brief",
    "say_before_end",
)


def leaves(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list) and value and isinstance(value[0], dict) and "id" in value[0]:
        for item in sorted(value, key=lambda x: x["id"]):
            yield from leaves(item, f"{path}[{item['id']}]")
    elif isinstance(value, list):
        yield path, json.dumps(value, sort_keys=True)
    else:
        yield path, json.dumps(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("briefs", nargs="+")
    ap.add_argument("--api", default=str(ROOT / "kit/tools/openapi.json"))
    ap.add_argument("--n", type=int, default=2)
    a = ap.parse_args()
    text, tools = read_briefs(a.briefs), load_tool_api(a.api)
    with ThreadPoolExecutor(max_workers=a.n) as ex:
        specs = list(ex.map(lambda _: extract(Trace(stream=StringIO()), text, tools), range(a.n)))
    for i, s in enumerate(specs):
        (ROOT / "runs" / f"exp06_spec_{i}.json").write_text(json.dumps(s, indent=1))
    maps = [dict(leaves({k: v for k, v in s.items() if k != "_prompt_brief"})) for s in specs]
    keys = sorted(set().union(*maps))
    typed_diff, prose_diff = [], []
    for k in keys:
        vals = [m.get(k) for m in maps]
        if len(set(vals)) > 1:
            (prose_diff if any(p in k for p in PROSE) else typed_diff).append((k, vals))
    print(
        f"{len(keys)} leaves; typed differences: {len(typed_diff)}; prose differences: {len(prose_diff)}"
    )
    for k, vals in typed_diff:
        print("TYPED", k, " | ".join(str(v)[:120] for v in vals))
    for k, vals in prose_diff[:15]:
        print("prose", k, " | ".join(str(v)[:80] for v in vals))


if __name__ == "__main__":
    main()
