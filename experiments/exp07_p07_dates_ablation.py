"""Experiment 07: what makes the model answer a holiday as "the latest date" (PUB-07)?

PUB-07 ("the week after next", then "Monday the 26th", a holiday 7 days before the Monday deadline)
was answered right in ~11 of 12 calls up to d46b807 and in ~3 of 15 calls from 676e9df on: the model
says "The latest date I can record is Monday 2 November" although FACTS says to offer 27 October.
Each variant renders the normal workflow from a saved spec, changes one thing, and saves it to its
own slot, so the variants can be simulated one after the other with run_cases.py --only PUB-07.

    python experiments/exp07_p07_dates_ablation.py <variant> <brief> <tool_api> --spec <spec> --slot <slot>

Variants:
- noweekday: drop the same-weekday sentence of 03ee6b0 from the DATES line;
- noperiod: drop the period sentence of 19664c6 from the DATES line;
- old: the DATES line of 90b737d;
- 1slot: one product slot instead of 3 (773b0dd);
- nounused: 3 slots, but FACTS leaves out the "P<k>: not in use" lines;
- noperiodrows: the DATE TABLE without its "next week" / "the week after next" rows;
- notoomuch: FACTS without the "IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH" line (35c030a);
- nofactsdiff: all three FACTS patches at once (the runtime FACTS of the passing 52b947c agent);
- isokey: the after-deadline catch-all keyed by the ISO date only ("a date after 2026-11-02:"), without
  the spoken weekday that matches the customer's weekday;
- echodate (on F1, 15bcbad; the example uses placeholders, no brief value): the DATES line also says to start the answer to a named date with that date
  as written in FACTS, then say what its line says (every failing call skipped naming the date);
- offerdate (on F3, a069dd2): the ATTEMPTS line also says every offer names its amount and its date as
  written in FACTS, and the only "today" question is the opening one (F1/F3 PUB-06: floor offered "today");
- ctltext:<export.json>: HEAD code and FACTS, but the system prompt and negotiate task text of an
  exported workflow (the passing 52b947c agent);
- ctlsys:<export.json> / ctltask:<export.json>: only its system prompt / only its negotiate text.
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
ECHO = (
    " When you answer a date the customer named, start your reply with that date as written in FACTS"
    ' (for example "<weekday> <day> <month> <year> is ..."), then say what its line in FACTS says.'
)
OFFER_ANCHOR = "on attempt 1's date)."
OFFER_DATE = (
    " Each offer of yours names its amount and its date as written in FACTS (for example"
    ' "<amount> on <weekday> <day> <month> <year>"); the only "today" question is the opening one.'
)
OLD_DATES = (
    "DATES: when the customer names a date, find it in that product's \"IF THE CUSTOMER NAMES A"
    " DATE\" lines in FACTS and do exactly what they say (they already apply the brief's date"
    " rules). Never offer the latest date unless those lines say so."
)
# Statements as they appear in the generated sandbox code; each variant replaces one with `pass`,
# or with its own replacement (REPLACE).
CODE_PATCHES = {
    "nounused": "parts.append('P' + str(k) + ': not in use (never call ' + unused + ')')",
    "noperiodrows": (
        "lines.append(label + ' (Monday-to-Sunday): ' + ', '.join((_wd(x) for x in days)))"
    ),
    "notoomuch": (
        "lines.append('- IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH before your first offer:"
        " offer' + ' exactly the floor ' + _amount(floor) + ' on ' + _ds(first[1]) + '; this IS"
        " attempt 1 (no other date: not today unless that is this date)')"
    ),
}
CODE_PATCHES["isokey"] = "out.append('  - a date after ' + _ds(high) + ': ' + tail)"
REPLACE = {"isokey": "out.append('  - a date after ' + high.isoformat() + ': ' + tail)"}
COMBOS = {"nofactsdiff": ("nounused", "noperiodrows", "notoomuch")}
CTL_PARTS = {"ctltext": ("sys", "task"), "ctlsys": ("sys",), "ctltask": ("task",)}


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
    if variant == "offerdate":
        if task.count(OFFER_ANCHOR) != 1:
            raise SystemExit("offerdate: ATTEMPTS anchor not found once")
        return task.replace(OFFER_ANCHOR, OFFER_ANCHOR + OFFER_DATE)
    if variant == "echodate":
        anchor = " Never offer the latest date unless those lines say so."
        if anchor not in line:
            raise SystemExit("echodate: anchor sentence not found")
        return task.replace(line, line.replace(anchor, ECHO + anchor))
    return task


def _patch_code(node, old: str, new: str = "pass") -> int:
    """Replace the statement `old` with `new` in every string of the workflow; return the count."""
    n = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and old in value:
                node[key] = value.replace(old, new)
                n += 1
            else:
                n += _patch_code(value, old, new)
    elif isinstance(node, list):
        for value in node:
            n += _patch_code(value, old, new)
    return n


def main() -> int:
    variant, argv = sys.argv[1], sys.argv[2:]
    kind, _, ctl_path = variant.partition(":")
    ctl = json.loads(Path(ctl_path).read_text())["workflow"] if kind in CTL_PARTS else None
    known = (
        "noweekday",
        "noperiod",
        "old",
        "1slot",
        "echodate",
        "offerdate",
        *CODE_PATCHES,
        *COMBOS,
    )
    if not ctl and variant not in known:
        raise SystemExit(f"unknown variant {variant}")
    if variant == "1slot":
        spec_mod.MIN_SLOTS = 1

    def render(spec: dict, tools: list) -> dict:
        wf = pipeline.render(spec, tools)
        node = wf["nodes"]["negotiate"]
        before = node["task_message"]
        node["task_message"] = _edit(before, variant)
        if ctl and "sys" in CTL_PARTS[kind]:
            wf["system_prompt"] = ctl["system_prompt"]
        if ctl and "task" in CTL_PARTS[kind]:
            node["task_message"] = ctl["nodes"]["negotiate"]["task_message"]
        for patch in COMBOS.get(variant, (variant,)):
            new = REPLACE.get(patch, "pass")
            if patch in CODE_PATCHES and _patch_code(wf, CODE_PATCHES[patch], new) == 0:
                raise SystemExit(f"{patch}: statement not found in the generated code")
        changed = before != node["task_message"]
        print(f"exp07 variant={variant} negotiate changed={changed}", file=sys.stderr)
        print(f"exp07 DATES: {_dates_line(node['task_message'])}", file=sys.stderr)
        slots = json.dumps(wf).count('"create_promise_p')
        print(f"exp07 create_promise slot mentions: {slots}", file=sys.stderr)
        return wf

    return cli.run(argv, pipeline.extract, render, pipeline.selftest)


if __name__ == "__main__":
    sys.exit(main())
