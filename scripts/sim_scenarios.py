"""Run simulated customers against one phone agent and print the judge's verdicts (no bank ledger needed).

    .venv/bin/python scripts/sim_scenarios.py <agent_id> --cases runs/cases/<file>.json --out runs/<name>.json

Cases file: [{"id", "title", "prompt", "checks": [...], "variables": {...}}]. `prompt` is the simulated customer's
script, `checks` the success criteria the judge applies, `variables` the call's variables (as the platform passes
them). One simulation, every case once, POST maxRetries 0 (one attempt, nothing replaced silently). Personas are
created fresh for each run. With MOCK_ADMIN_TOKEN and --mock set, the mock's request log is saved next to --out.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from _kit import freya

PERSONA_RULES = """OUTPUT RULE: Write only the words you say on the phone. No stage directions, no brackets. One or two
short sentences per turn, then wait for the other side. Do not invent facts that are not written above. When the other
side says goodbye, say goodbye and nothing more."""


def one_attempt(api):
    def wrapped(method, path, body=None, **params):
        if method == "POST" and path == "/api/v2/simulations" and isinstance(body, dict):
            body = {**body, "maxRetries": 0}
        return api(method, path, body, **params)

    return wrapped


def mock_log(mock: str) -> list:
    req = urllib.request.Request(
        mock.rstrip("/") + "/__admin/log",
        headers={
            "x-admin-token": os.environ["MOCK_ADMIN_TOKEN"],
            "user-agent": "sim-scenarios/0.1",
        },
    )
    return json.load(urllib.request.urlopen(req, timeout=20)).get("log", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_id")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--mock", help="mock origin, to save its request log after the run")
    a = ap.parse_args()

    cases = json.load(open(a.cases))
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    if not cases:
        sys.exit("no cases")
    personas = [
        {
            "name": f"{c['id']} {c['title']}",
            "prompt": c["prompt"].strip() + "\n\n" + PERSONA_RULES,
            "successCriteria": "All of these are true:\n- " + "\n- ".join(c["checks"]),
            "tags": ["final-scenarios"],
        }
        for c in cases
    ]
    made = freya.create_personas(personas)["personas"]
    ids = {c["id"]: p["id"] for c, p in zip(cases, made, strict=True)}
    freya.api = one_attempt(freya.api)
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sim_id, it_id, status = freya.run_simulation(
        a.agent_id,
        f"scenarios {time.strftime('%H:%M:%S')}",
        {ids[c["id"]]: c["variables"] for c in cases},
    )
    runs = {r["personaId"]: r for r in freya.get_iteration(sim_id, it_id)["runs"]}
    rows = []
    for c in cases:
        r = runs.get(ids[c["id"]], {})
        ok = r.get("outcome") == "pass"
        reason = " ".join(str(r.get("reason") or "no verdict").split())
        rows.append(
            {
                "id": c["id"],
                "pass": ok,
                "outcome": r.get("outcome"),
                "reason": reason,
                "call_id": r.get("callId"),
            }
        )
        print(("PASS" if ok else "FAIL"), c["id"], c["title"], "| call", r.get("callId"))
        if not ok:
            print("       -", reason[:400])
    n = sum(r["pass"] for r in rows)
    print(
        f"{n} / {len(rows)} passed. Simulation {sim_id}, status {status}, {round(time.time() - t0)} s."
    )
    out = {
        "agent_id": a.agent_id,
        "simulation_id": sim_id,
        "iteration_id": it_id,
        "started": started,
        "rows": rows,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1, ensure_ascii=False)
    if a.mock and os.environ.get("MOCK_ADMIN_TOKEN"):
        log = [e for e in mock_log(a.mock) if e.get("at", "") >= started]
        Path(a.out).with_suffix(".mocklog.json").write_text(
            json.dumps(log, indent=1, ensure_ascii=False)
        )
        print(f"mock requests during the run: {len(log)} (saved next to --out)")
    return 0 if n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
