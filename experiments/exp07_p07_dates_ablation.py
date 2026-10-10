"""Experiment 07: which negotiate DATES wording makes the model answer a holiday as "the latest date"?

PUB-07 ("the week after next", then "Monday the 26th", a holiday 7 days before the Monday deadline)
was answered right in ~11 of 12 calls up to d46b807 and in ~3 of 15 calls from 676e9df on: the model
says "The latest date I can record is Monday 2 November" although FACTS says to offer 27 October.
Each variant renders the normal workflow from a saved spec, changes one thing, and saves it to its
own slot, so the variants can be simulated one after the other with run_cases.py --only PUB-07.

    python experiments/exp07_p07_dates_ablation.py <variant> <brief> <tool_api> --spec <spec> --slot <slot>

Variants: noweekday (drop the same-weekday sentence of 03ee6b0), noperiod (drop the period sentence
of 19664c6), old (the DATES line of 90b737d), 1slot (one product slot instead of 3, 773b0dd).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from freya_builder import cli, pipeline  # noqa: E402
from freya_builder import spec as spec_mod  # noqa: E402

WEEKDAY = (
    " Compare dates, never weekday names: a deadline that falls on the same weekday is a different"
    " date."
)
PERIOD = re.compile(r" If the customer first named a period .*?not a later one\)\.")
OLD_DATES = (
    "DATES: when the customer names a date, find it in that product's \"IF THE CUSTOMER NAMES A"
    " DATE\" lines in FACTS and do exactly what they say (they already apply the brief's date"
    " rules). Never offer the latest date unless those lines say so."
)


def _dates_line(task: str) -> str:
    lines = [ln for ln in task.split("\n") if ln.startswith("DATES: ")]
    if len(lines) != 1:
        raise SystemExit(f"expected one DATES line in negotiate, found {len(lines)}")
    return lines[0]


def _edit(task: str, variant: str) -> str:
    line = _dates_line(task)
    if variant == "noweekday":
        if WEEKDAY not in line:
            raise SystemExit("same-weekday sentence not found")
        return task.replace(line, line.replace(WEEKDAY, ""))
    if variant == "noperiod":
        new, n = PERIOD.subn("", line)
        if n != 1:
            raise SystemExit(f"period sentence found {n} times")
        return task.replace(line, new)
    if variant == "old":
        return task.replace(line, OLD_DATES)
    return task


def main() -> int:
    variant, argv = sys.argv[1], sys.argv[2:]
    if variant not in ("noweekday", "noperiod", "old", "1slot"):
        raise SystemExit(f"unknown variant {variant}")
    if variant == "1slot":
        spec_mod.MIN_SLOTS = 1

    def render(spec: dict, tools: list) -> dict:
        wf = pipeline.render(spec, tools)
        node = wf["nodes"]["negotiate"]
        before = node["task_message"]
        node["task_message"] = _edit(before, variant)
        changed = before != node["task_message"]
        print(f"exp07 variant={variant} negotiate changed={changed}", file=sys.stderr)
        print(f"exp07 DATES: {_dates_line(node['task_message'])}", file=sys.stderr)
        slots = json.dumps(wf).count('"create_promise_p')
        print(f"exp07 create_promise slot mentions: {slots}", file=sys.stderr)
        return wf

    return cli.run(argv, pipeline.extract, render, pipeline.selftest)


if __name__ == "__main__":
    sys.exit(main())
