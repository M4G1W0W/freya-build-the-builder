"""Run the kit's run_cases.py unmodified, with bounded retries on idempotent GETs that return 5xx.

    python scripts/run_cases_retry.py <agent_id> --brief A [run_cases.py arguments...]

The kit client has no retry: one 503 while polling a simulation ("API key validation is temporarily
unavailable", 10 Oct 19:53 UTC) ended a 3-rep run after rep 1 and left its simulation running.
Only GETs are retried (POST/PUT are not idempotent); 4xx errors are never retried.

It also frees a simulation stuck in "running". On 10 Oct (21:17-21:55 UTC) and 11 Oct (01:21-08:12 UTC) a
simulation stayed "running" after all its calls had ended and its iteration had completed; it blocked every new
simulation and the kit waits with no timeout. A stuck simulation is paused (PUT status "paused", which keeps its
data; user-approved 11 Oct 08:20 UTC) and an UNSTUCK line is printed. Stuck means: every call ended and the
iteration completed STUCK_AFTER_S ago; or every call ended NO_JUDGE_AFTER_S ago; or the simulation is older than
HARD_AFTER_S. A simulation with a call still going is never paused. Checked while polling our own simulation and
whenever a new one is refused because another is running.
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
FIRST_CHECK_S = 60  # normal runs end in 1 to 6 minutes
CHECK_EVERY_S = 60
STUCK_AFTER_S = 120  # every call ended and the iteration completed this long ago, still "running"
NO_JUDGE_AFTER_S = 600  # every call ended this long ago, the iteration never completed
HARD_AFTER_S = 2400  # 13 cases, 5 at a time, 7-min calls: none of ours runs this long
WORKSPACE_CHECK_EVERY_S = 60
_api = freya.api
_watch: dict[str, dict] = {}
_last_workspace_check = 0.0


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


def _items(result, *keys):
    if isinstance(result, list):
        return result
    for k in keys:
        if isinstance(result.get(k), list):
            return result[k]
    return next((v for v in result.values() if isinstance(v, list)), [])


def _epoch(stamp) -> float | None:
    try:
        return datetime.fromisoformat(stamp).timestamp() if stamp else None
    except (TypeError, ValueError):
        return None


def last_call_end(sim_id, api, its=None) -> float | None:
    """Epoch seconds at which the simulation's last call ended; None while any call is missing or going."""
    if its is None:
        its = _items(api("GET", f"/api/v2/simulations/{sim_id}/iterations"), "iterations", "items")
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


def stuck_reason(sim_id, now, api, created=None) -> str | None:
    """Why a simulation reported as "running" is stuck, or None when it may still be working."""
    if created is not None and now - created >= HARD_AFTER_S:
        return f"running {int((now - created) // 60)} min since it was created"
    its = _items(api("GET", f"/api/v2/simulations/{sim_id}/iterations"), "iterations", "items")
    end = last_call_end(sim_id, api, its)
    if end is None:
        return None
    judged = bool(its) and all(it.get("status") == "completed" for it in its)
    if judged and now - end >= STUCK_AFTER_S:
        return f"every call ended {int(now - end)} s ago and its iteration completed"
    if now - end >= NO_JUDGE_AFTER_S:
        return f"every call ended {int(now - end)} s ago; its iteration never completed (verdicts may be missing)"
    return None


def pause(sim_id, why, api) -> str:
    api("PUT", f"/api/v2/simulations/{sim_id}", {"status": "paused"})
    msg = f"UNSTUCK: paused simulation {sim_id}: still 'running' although {why}."
    print(msg, flush=True)
    return msg


def check_stuck(sim_id, status, now, api, created=None) -> str | None:
    """Called on every poll of our own simulation; pauses it once when it is stuck and returns the message."""
    if status != "running":
        _watch.pop(sim_id, None)
        return None
    w = _watch.setdefault(sim_id, {"first": now, "checked": 0.0, "reported": False})
    if w["reported"] or now - w["first"] < FIRST_CHECK_S or now - w["checked"] < CHECK_EVERY_S:
        return None
    w["checked"] = now
    why = stuck_reason(sim_id, now, api, created)
    if why is None:
        return None
    w["reported"] = True
    return pause(sim_id, why, api)


def unstick_workspace(now, api) -> list[str]:
    """When a new simulation is refused: pause any stuck simulation that blocks the workspace."""
    global _last_workspace_check
    if now - _last_workspace_check < WORKSPACE_CHECK_EVERY_S:
        return []
    _last_workspace_check = now
    sims = _items(
        api("GET", "/api/v2/simulations", limit=20, offset=0), "simulations", "items", "data"
    )
    out = []
    for s in sims:
        if s.get("status") != "running":
            continue
        why = stuck_reason(s["id"], now, api, _epoch(s.get("createdAt")))
        if why:
            out.append(pause(s["id"], why, api))
    return out


def api_watched(method, path, body=None, **params):
    try:
        result = api_with_retry(method, path, body, **params)
    except RuntimeError as e:
        if (
            method == "POST"
            and path == "/api/v2/simulations"
            and "concurrent simulations" in str(e)
        ):
            try:
                unstick_workspace(time.time(), api_with_retry)
            except Exception as x:  # the watcher must never end the run it serves
                log.warning("workspace stuck check failed: %s", x)
        raise
    sim = SIM_PATH.fullmatch(path)
    if method == "GET" and sim and isinstance(result, dict):
        s = result.get("simulation") or result
        try:
            check_stuck(
                sim[1], s.get("status"), time.time(), api_with_retry, _epoch(s.get("createdAt"))
            )
        except Exception as e:  # the watcher must never end the run it watches
            log.warning("stuck check for %s failed: %s", sim[1], e)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    freya.api = api_watched
    sys.argv = [str(KIT / "tools" / "run_cases.py"), *sys.argv[1:]]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()
