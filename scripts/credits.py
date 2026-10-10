"""Print workspace credits; append them to runs/credits_log.jsonl (cost per simulation).

python scripts/credits.py "after baseline A"
"""

import json
import sys
import time

from _kit import RUNS, freya


def main() -> None:
    label = " ".join(sys.argv[1:]) or "check"
    c = freya.api("GET", f"/api/v2/workspaces/{freya.workspace_id()}/credits")
    RUNS.mkdir(exist_ok=True)
    entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "event": label, "credits": c}
    with open(RUNS / "credits_log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"credits left {c.get('creditsLeft')} ({c.get('billingUnit')}) - logged as '{label}'")


if __name__ == "__main__":
    main()
