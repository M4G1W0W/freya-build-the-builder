"""Make a dashboard-testable COPY of a published workflow: same definition plus `test_variables` from
a fresh practice-bank session. kit/docs/workflow-format.md ("Call variables and test_variables"):
on a web call the workflow's test_variables are merged into the call variables. Without them a
dashboard web call has no customer_id and the agent reads out {{last_name}}.

The source workflow is not touched. The copy lives in its own slot (default `voice-test`) and is
never submitted. Re-run with another --case for a fresh customer (one session = one test call).

    python scripts/voice_test.py <source_workflow_id> --case PUB-01 [--slot voice-test]
"""

import argparse
import json
import sys

from _kit import KIT, ROOT, freya, score


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_workflow_id")
    ap.add_argument(
        "--case", default="PUB-01", help="public practice case whose bank account to use"
    )
    ap.add_argument("--slot", default="voice-test")
    a = ap.parse_args()

    cases = {c["id"]: c for c in json.loads((KIT / "public-test-set.json").read_text())}
    if a.case not in cases:
        sys.exit(f"unknown case {a.case}; one of {sorted(cases)}")
    session = score.http("/v1/practice/sessions", {"case": a.case})
    variables = session.get("variables") or {}
    if not variables.get("customer_id"):
        sys.exit(f"could not open a practice session for {a.case}: {session}")

    src = freya.api(
        "GET", f"/api/v2/workflow/{a.source_workflow_id}", workspaceId=freya.workspace_id()
    )
    definition = dict(src["workflow"]["workflow"])
    definition["test_variables"] = {k: str(v) for k, v in variables.items()}
    saved = freya.save_workflow(a.slot, definition, state_file=str(ROOT / ".freya-agents.json"))

    case = cases[a.case]
    print(
        f"test copy: slot {a.slot} | workflow {saved['workflow_id']} | agent {saved.get('agent_id')}"
    )
    print(f"source: {a.source_workflow_id} (unchanged)")
    print(f"call variables (test_variables): {definition['test_variables']}")
    print(f"\nYOU PLAY: {case['title']}")
    print(f"  identity answers: {case['identity']}")
    print(f"  script: {case['script']}")
    print(f"  expected ledger: {case['expected']}")


if __name__ == "__main__":
    main()
