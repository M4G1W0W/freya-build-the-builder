"""Write the styled case files for 3-rep measurement (review gap 4).

The final's customers talk "like people" (official page, Evaluation tab), and every case must pass 3
reps. These files give every practice case one of the kit's five speech styles, by rotation, so one
run covers all styles. run_cases.py reads a per-case `style` (kit/tools/run_cases.py, persona_for).

    python scripts/make_style_cases.py   ->  tests/fixtures/cases/styled-*.json

- styled-a:      Brief A cases, Brief A ledgers (for an A-only agent).
- styled-ab-a:   Brief A cases, ledgers under Brief A + B: rule 8 adds a note for every product
                 without a promise, "also when no product gets a promise" (PUB-05 hardship, PUB-08
                 paid). Another rotation, so each case meets a second style.
- styled-b:      Brief B cases.
- styled-extra-b: tests/fixtures/cases/extra-b.json with styles.
"""

import copy
import json

from _kit import KIT, ROOT

STYLES = ["talkative", "pieces", "corrects", "asks_back", "in_words"]
OUT = ROOT / "tests" / "fixtures" / "cases"
AB_NOTES = {"PUB-05": "hardship", "PUB-08": "paid"}


def styled(cases: list[dict], offset: int) -> list[dict]:
    out = []
    for i, case in enumerate(cases):
        c = copy.deepcopy(case)
        c["style"] = STYLES[(i + offset) % len(STYLES)]
        out.append(c)
    return out


def main() -> None:
    public = json.loads((KIT / "public-test-set.json").read_text())
    brief_a = [c for c in public if c["brief"] == "A"]
    brief_b = [c for c in public if c["brief"] == "B"]
    ab_a = copy.deepcopy(brief_a)
    for c in ab_a:
        if c["id"] in AB_NOTES:
            c["expected"]["notes"] = [{"product_id": "p1", "reason": AB_NOTES[c["id"]]}]
            c["note"] = (
                "expected notes per Brief B rule 8 (an A+B agent notes a product without a promise)"
            )
    extra_b = json.loads((OUT / "extra-b.json").read_text())
    files = {
        "styled-a.json": styled(brief_a, 0),
        "styled-ab-a.json": styled(ab_a, 2),
        "styled-b.json": styled(brief_b, 1),
        "styled-extra-b.json": styled(extra_b, 3),
    }
    for name, cases in files.items():
        (OUT / name).write_text(json.dumps(cases, indent=1) + "\n")
        print(name, ", ".join(f"{c['id']}:{c['style']}" for c in cases))


if __name__ == "__main__":
    main()
