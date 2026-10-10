"""Talk to a published workflow over text, turn by turn, against a fresh practice-bank session.

    python scripts/chat.py <workflow_id> --case PUB-01 --say "Yes, speaking." --say "14 March 1988"
    python scripts/chat.py <workflow_id> --case PUB-01    # interactive; an empty line ends

Uses POST /api/v2/chat/message (kit/docs/api.md). Faster than a simulation; no judge, no score.
The chat route may skip a first code step (kit docs), so values it computes can be empty here.
"""

import argparse
import sys

from _kit import freya, score


def send(workflow_id: str, message: str, call_id: str | None, variables: dict) -> dict:
    body = {"message": message}
    if call_id:
        body["callId"] = call_id
    else:
        body |= {"workflowId": workflow_id, "customerVariables": variables}
    return freya.api("POST", "/api/v2/chat/message", body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow_id")
    ap.add_argument("--case", default="PUB-01", help="practice case whose bank session to use")
    ap.add_argument("--say", action="append", default=[], help="customer turn (repeatable)")
    ap.add_argument("--first", default="Hello?", help="first customer turn (opens the call)")
    a = ap.parse_args()

    session = score.http("/v1/practice/sessions", {"case": a.case})
    variables = session.get("variables") or {}
    if not variables:
        sys.exit(f"could not open a practice session for {a.case}: {session}")
    print(f"case {a.case} | variables: {sorted(variables)}")

    turns = [a.first, *a.say]
    interactive = not a.say and sys.stdin.isatty()
    call_id = None
    i = 0
    while True:
        if i < len(turns):
            msg = turns[i]
        elif interactive:
            msg = input("CUST > ").strip()
            if not msg:
                break
        else:
            break
        if i < len(turns):
            print(f"CUST : {msg}")
        r = send(a.workflow_id, msg, call_id, variables)
        call_id = r.get("callId") or call_id
        print(f"AGENT: {r.get('response')}")
        if r.get("endedByAgent"):
            print("(agent ended the call)")
            break
        i += 1
    if call_id:
        freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        print(f"call {call_id} closed. Inspect: python scripts/show_call.py {call_id}")
        ledger = score.http("/v1/practice/ledger/" + variables.get("customer_id", ""))
        print(f"bank ledger: {ledger}")


if __name__ == "__main__":
    main()
