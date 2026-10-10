"""Run the kit's run_cases.py unmodified, with bounded retries on idempotent GETs that return 5xx.

    python scripts/run_cases_retry.py <agent_id> --brief A [run_cases.py arguments...]

The kit client has no retry: one 503 while polling a simulation ("API key validation is temporarily
unavailable", 10 Oct 19:53 UTC) ended a 3-rep run after rep 1 and left its simulation running.
Only GETs are retried (POST/PUT are not idempotent); 4xx errors are never retried.

It also reports (never fixes) a simulation stuck in "running": on 10 Oct a simulation stayed "running" from 21:17
to 21:55 UTC after all its calls had ended, blocked every new simulation, and the kit polls with no timeout. Freeing
it (PUT status "paused") is a platform write and needs the user's OK, so this only logs a STUCK line.
"""

import logging
import re
import runpy
import sys
import time
from datetime import datetime

from _kit import KIT, freya

log = logging.getLogger("run_cases_retry")
DELAYS = (5, 15, 30, 60, 120)
SIM_PATH = re.compile(r"/api/v2/simulations/([0-9a-f-]{36})")
FIRST_CHECK_S = 300  # normal runs end in 1 to 6 minutes; look only at longer ones
CHECK_EVERY_S = 120
STUCK_AFTER_S = 600  # still "running" this long after its last call ended
_api = freya.api
_watch: dict[str, dict] = {}


def api_with_retry(method, path, body=None, **params):
    for delay in (*DELAYS, None):
        try:
            return _api(method, path, body, **params)
        except RuntimeError as e:
            status = re.search(r"-> (\d{3}):", str(e))
            if method != "GET" or delay is None or not status or not status[1].startswith("5"):
                raise
            log.warning("GET %s -> %s; retry in %d s", path, status[1], delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


def last_call_end(sim_id, api) -> float | None:
    """Epoch seconds at which the simulation's last call ended; None while any call is missing or going."""
    its = api("GET", f"/api/v2/simulations/{sim_id}/iterations")
    its = its.get("iterations") or its.get("items") or its
    ends = []
    for it in its:
        runs = api(
            "GET", f"/api/v2/simulations/{sim_id}/iterations/{it['id']}", limit=100, offset=0
        )
        runs = runs.get("runs") or []
        if not runs:
            return None
        for run in runs:
            ended = (
                run.get("callId") and api("GET", f"/api/v2/call/{run['callId']}")["call"]["endedAt"]
            )
            if not ended:
                return None
            ends.append(datetime.fromisoformat(ended).timestamp())
    return max(ends) if ends else None


def check_stuck(sim_id, status, now, api) -> str | None:
    """Called on every poll of one simulation; returns the STUCK message once, when it applies."""
    if status != "running":
        _watch.pop(sim_id, None)
        return None
    w = _watch.setdefault(sim_id, {"first": now, "checked": 0.0, "reported": False})
    if w["reported"] or now - w["first"] < FIRST_CHECK_S or now - w["checked"] < CHECK_EVERY_S:
        return None
    w["checked"] = now
    end = last_call_end(sim_id, api)
    if end is None or now - end < STUCK_AFTER_S:
        return None
    w["reported"] = True
    return (
        f"STUCK: simulation {sim_id} is still 'running' {int((now - end) // 60)} min after its last"
        " call ended; it blocks every new simulation in the workspace. Report only: to free it,"
        f' PUT /api/v2/simulations/{sim_id} {{"status": "paused"}} (needs the user\'s OK).'
    )


def api_watched(method, path, body=None, **params):
    result = api_with_retry(method, path, body, **params)
    sim = SIM_PATH.fullmatch(path)
    if method == "GET" and sim and isinstance(result, dict):
        status = (result.get("simulation") or result).get("status")
        try:
            msg = check_stuck(sim[1], status, time.time(), api_with_retry)
        except Exception as e:  # a report-only watcher must never end the run it watches
            log.warning("stuck check for %s failed: %s", sim[1], e)
            msg = None
        if msg:
            log.warning(msg)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    freya.api = api_watched
    sys.argv = [str(KIT / "tools" / "run_cases.py"), *sys.argv[1:]]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()
