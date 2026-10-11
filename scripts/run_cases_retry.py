"""Run the kit's run_cases.py unmodified, with bounded retries on idempotent GETs that fail.

    python scripts/run_cases_retry.py <agent_id> --brief A [run_cases.py arguments...]

The kit client has no retry: one 503 while polling a simulation ("API key validation is temporarily
unavailable", 10 Oct 19:53 UTC) ended a 3-rep run after rep 1 and left its simulation running.
Only GETs are retried (POST/PUT are not idempotent), on 5xx and on network errors; 4xx errors never are.
Before starting, it waits (up to 30 min) until the platform answers a GET.

It also frees a simulation stuck in "running". On 10 Oct (21:17-21:55 UTC) and 11 Oct (01:21-08:12 UTC) a
simulation stayed "running" after all its calls had ended and its iteration had completed; it blocked every new
simulation and the kit waits with no timeout. A stuck simulation is paused (PUT status "paused", which keeps its
data; user-approved 11 Oct 08:20 UTC) and an UNSTUCK line is printed. Stuck means: every call ended and the
iteration completed STUCK_AFTER_S ago; or every call ended NO_JUDGE_AFTER_S ago; or the simulation is older than
HARD_AFTER_S (the only case that pauses a simulation with a call still going). Checked while polling our own
simulation and whenever a new one is refused because another is running.

A rep with calls the judge never scored ("analysis never arrived", 11 Oct 08:22 UTC) is not a measurement: it is
discarded and repeated once with fresh bank sessions (printed as "-- run discarded", which the call ledger counts).
Before that, a run still "analyzing" takes the judge verdict already on its call record (successCriteriaResult;
11 Oct 12:15 UTC, user-approved): printed as "VERDICT FROM CALL RECORD" and marked verdict_source "call" in the
rows, so such results stay separable from run verdicts.

Calls per simulation: the kit's FREYA_SIM_CONCURRENCY (default 5). It ran at 13 on 11 Oct 08:30-09:22 UTC; on the
13-case A+B set that made agent turns slow (20-60 s) and simulated customers hung up, so it is back to the default
(user decision 09:25 UTC).
"""

import http.client
import json
import logging
import re
import sys
import time
import urllib.error
from datetime import datetime

from _kit import KIT, freya

log = logging.getLogger("run_cases_retry")
DELAYS = (
    5,
    15,
    30,
    60,
    120,
    180,
    300,
    300,
)  # ~17 min: 11 Oct 09:38-09:50 UTC polls got 504 for >10 min
HEALTH_WAIT_S = 1800  # before starting: wait this long at most for the platform to answer a GET
NETWORK_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
    json.JSONDecodeError,
)
SIM_PATH = re.compile(r"/api/v2/simulations/([0-9a-f-]{36})")
FIRST_CHECK_S = 60  # normal runs end in 1 to 6 minutes
CHECK_EVERY_S = 60
STUCK_AFTER_S = 120  # every call ended and the iteration completed this long ago, still "running"
NO_JUDGE_AFTER_S = 600  # every call ended this long ago, the iteration never completed
HARD_AFTER_S = 2400  # 13 cases at 5 or 13 at a time, 7-min calls: none of ours runs this long
WORKSPACE_CHECK_EVERY_S = 60
MAX_PAUSES = 2  # per simulation; after that print UNSTUCK FAILED and leave it
NO_VERDICT = re.compile(r"analysis never arrived|no verdict", re.IGNORECASE)
_api = freya.api
_watch: dict[str, dict] = {}
_pauses: dict[str, int] = {}
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
        except NETWORK_ERRORS as e:
            if method != "GET" or delay is None:
                raise
            log.warning("GET %s -> %s; retry in %d s", path, type(e).__name__, delay)
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


def pause(sim_id, why, api) -> str | None:
    """Pause a stuck simulation; at most MAX_PAUSES attempts per simulation. Raises if the PUT fails."""
    n = _pauses.get(sim_id, 0)
    if n >= MAX_PAUSES:
        if n == MAX_PAUSES:
            _pauses[sim_id] = n + 1
            print(
                f"UNSTUCK FAILED: simulation {sim_id} is still 'running' after {n} pauses.",
                flush=True,
            )
        return None
    _pauses[sim_id] = n + 1
    api("PUT", f"/api/v2/simulations/{sim_id}", {"status": "paused"})
    msg = f"UNSTUCK: paused simulation {sim_id}: still 'running' although {why}."
    print(msg, flush=True)
    return msg


def check_stuck(sim_id, status, now, api, created=None) -> str | None:
    """Called on every poll of our own simulation; pauses it when it is stuck and returns the message."""
    if status != "running":
        _watch.pop(sim_id, None)
        return None
    w = _watch.setdefault(sim_id, {"first": now, "checked": 0.0})
    if now - w["first"] < FIRST_CHECK_S or now - w["checked"] < CHECK_EVERY_S:
        return None
    w["checked"] = now
    why = stuck_reason(sim_id, now, api, created)
    return pause(sim_id, why, api) if why else None


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
        msg = why and pause(s["id"], why, api)
        if msg:
            out.append(msg)
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


def unjudged(rows) -> list[str]:
    """Case ids of scored rows whose call never got a judge verdict."""
    return [r["id"] for r in rows if any(NO_VERDICT.search(f) for f in r.get("failed", []))]


def repeat_unjudged(run_once, seen=frozenset()):
    """Wrap the kit's run_once: a rep with an unjudged call is discarded and repeated once (fresh sessions).
    Every scored row is marked with its verdict source (`seen`: calls judged from their call record)."""

    def checked(agent_id, cases, ids):
        out = run_once(agent_id, cases, ids)
        bad = unjudged(out[0])
        if bad:
            print(
                f"-- run discarded: no judge verdict for {', '.join(bad)}. Repeating it once.\n",
                flush=True,
            )
            out = run_once(agent_id, cases, ids)
        mark_verdict_source(out[0], seen)
        return out

    return checked


def with_call_verdicts(get_iteration, get_call, seen):
    """Wrap the kit's get_iteration: a run still waiting for the judge takes the verdict on its call record.

    11 Oct 12:15 UTC, smoke 94c9e350: the run stayed "analyzing" (attempt 2/4) while its call record already had
    successCriteriaResult.success=True; run_cases scored it "conversation: no verdict". A verdict the run has
    (pass, fail, inconclusive, error) is never replaced. Calls whose verdict came from the record go into `seen`.
    """

    def wrapped(sim_id, it_id):
        iteration = get_iteration(sim_id, it_id)
        for run in iteration.get("runs") or []:
            if run.get("outcome") not in (None, "", "analyzing") or not run.get("callId"):
                continue
            try:
                result = get_call(run["callId"]).get("successCriteriaResult") or {}
            except Exception as e:  # a failed read leaves the run unjudged, as before
                log.warning("call record read for %s failed: %s", run["callId"], e)
                continue
            if not isinstance(result.get("success"), bool):
                continue
            was = run.get("outcome")
            run["outcome"] = "pass" if result["success"] else "fail"
            run["reason"] = f"[verdict from the call record] {result.get('reason') or ''}"
            seen.add(run["callId"])
            print(
                f"VERDICT FROM CALL RECORD: run {run.get('id')} call {run['callId']}: "
                f"{run['outcome']} (the run still said {was!r})",
                flush=True,
            )
        return iteration

    return wrapped


def mark_verdict_source(rows, seen) -> None:
    """Each scored row says whether its conversation verdict came from the run or from the call record."""
    for r in rows:
        r["verdict_source"] = "call" if r.get("call_id") in seen else "run"


def wait_until_healthy(api=None, limit_s=HEALTH_WAIT_S) -> None:
    """Start no simulation into a platform that cannot answer a GET (its results could not be collected)."""
    api = api or api_with_retry
    t0 = time.time()
    while True:
        try:
            api("GET", "/api/v2/simulations", limit=1, offset=0)
            return
        except (RuntimeError, *NETWORK_ERRORS) as e:
            if time.time() - t0 >= limit_s:
                raise
            print(
                f"platform not answering ({str(e)[:80]}); waiting 60 s before starting", flush=True
            )
            time.sleep(60)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    wait_until_healthy()
    freya.api = api_watched
    sys.argv = [str(KIT / "tools" / "run_cases.py"), *sys.argv[1:]]
    import run_cases  # kit/tools is on sys.path (scripts/_kit.py); imported, not run

    seen: set[str] = set()
    freya.get_iteration = with_call_verdicts(freya.get_iteration, freya.get_call, seen)
    run_cases.run_once = repeat_unjudged(run_cases.run_once, seen)
    run_cases.main()


if __name__ == "__main__":
    main()
