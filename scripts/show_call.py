"""Print one call's transcript with tool calls, results, routing and errors.

python scripts/show_call.py <call_id> [--verbose] [--raw runs/call.json]
"""

import argparse
import json

from _kit import freya
from callview import format_messages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("call_id")
    ap.add_argument("--verbose", action="store_true", help="show every routing check and event")
    ap.add_argument("--raw", help="also save the full call JSON to this path")
    a = ap.parse_args()
    call = freya.get_call(a.call_id)
    if a.raw:
        with open(a.raw, "w") as f:
            json.dump(call, f, indent=1)
    print(f"call {a.call_id} | ended: {call.get('endedReason')} | {call.get('duration')} s")
    scr = call.get("successCriteriaResult") or {}
    if scr:
        print(f"judge: success={scr.get('success')} | {scr.get('reason')}")
    print("\n".join(format_messages(call.get("messages") or [], a.verbose)))


if __name__ == "__main__":
    main()
