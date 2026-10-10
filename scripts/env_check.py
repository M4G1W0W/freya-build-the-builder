"""Check that the dev environment can work: Python, env vars, Freya API, workspace, credits.

    python scripts/env_check.py      # exit code 1 if something is missing

Read-only: no workflow, persona, session or simulation is created. Secret values are never printed.
"""

import os
import sys

from _kit import freya

REQUIRED = ["FREYA_API_KEY", "FREYA_API_URL", "FREYA_BANK_TEAM_KEY"]
WORKFLOW_LIMIT = 200  # kit/README.md, "Rules"


def main() -> int:
    problems = []
    ok = sys.version_info >= (3, 10)
    print(f"{'ok ' if ok else 'BAD'} python {sys.version.split()[0]} (kit needs 3.10+)")
    problems += [] if ok else ["python"]
    for name in REQUIRED:
        value = os.environ.get(name, "")
        print(f"{'ok ' if value else 'BAD'} {name} {'set' if value else 'MISSING'}")
        problems += [] if value else [name]
    if len(os.environ.get("FREYA_BANK_TEAM_KEY", "")) < 16:
        problems.append("team key shorter than 16 chars")
    if problems:
        print("stop:", ", ".join(problems))
        return 1
    try:
        ws = freya.workspace_id()
        credits = freya.api("GET", f"/api/v2/workspaces/{ws}/credits")
        wfs = freya.api("GET", "/api/v2/workflow", workspaceId=ws)
        items = wfs.get("workflows") or wfs.get("items") or []
    except RuntimeError as e:
        print("BAD Freya API:", str(e)[:300])
        return 1
    print(f"ok  API {freya.URL} | workspace {ws}")
    print(f"ok  credits left {credits.get('creditsLeft')} ({credits.get('billingUnit')})")
    print(f"ok  workflows {len(items)} / {WORKFLOW_LIMIT}")
    print(f"ok  phone-agent model {freya.AGENT_LLM['model']} (do not change)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
