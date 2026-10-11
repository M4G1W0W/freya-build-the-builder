"""Freya platform calls for the builder, through the official kit client (kit/freya.py).

The kit client reads FREYA_API_KEY / FREYA_API_URL at import time; it is imported lazily so
that --dry runs and unit tests need no credentials.

The platform has transient outages (11 Oct 08:40 UTC: 503 "API key validation is temporarily
unavailable", then 504, then 500 on the dry run), so calls are retried on 429/5xx and network
errors, until the 30-minute build limit is near; other 4xx (a rejected workflow) are never retried.
"""

import http.client
import json
import re
import ssl
import sys
import time
import urllib.error
from pathlib import Path

from . import llm
from .trace import Trace

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / ".freya-agents.json"
NETWORK_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
    ssl.SSLError,
)
# Seconds before attempts 2-9: 350 s of waiting per call (outages seen: ~5 min on 11 Oct 08:38-08:43
# UTC, ~10 min on 10 Oct 19:53-20:03). The 30-minute limit, not this list, bounds the total:
# call() stops retrying when the time left would not cover the wait plus one more attempt.
WAITS = (5, 15, 30, 60, 60, 60, 60, 60)
HARD_LIMIT_S = 30 * 60  # the page: 30 min per brief, including self-tests
ATTEMPT_S = 150  # one attempt: the kit's urlopen timeout (120 s, kit/freya.py api()) plus margin


def time_left() -> float:
    """Seconds to the 30-minute limit, from the build's LLM budget start (infinite if none)."""
    return llm.budget_left() + HARD_LIMIT_S - llm.BUILD_BUDGET_S


def kit():
    if str(ROOT / "kit") not in sys.path:
        sys.path.insert(0, str(ROOT / "kit"))
    import freya

    return freya


def status_of(e: Exception) -> int | None:
    """The HTTP status of a kit error ("METHOD path -> CODE: body"); None for a network error."""
    m = re.search(r" -> (\d{3}): ", str(e)) if isinstance(e, RuntimeError) else None
    return int(m.group(1)) if m else None


def transient(e: Exception) -> bool:
    """429, 5xx or a network error: worth repeating an idempotent request."""
    status = status_of(e)
    return isinstance(e, NETWORK_ERRORS) or status == 429 or (status or 0) >= 500


def unprocessed(e: Exception) -> bool:
    """Rejected before the platform did anything: 429, or the API-key check's 503."""
    status = status_of(e)
    text = str(e).lower()
    return status == 429 or (
        status == 503 and "api key validation is temporarily unavailable" in text
    )


def describe(trace: Trace, e: Exception) -> str:
    """The error's first line for the trace: redacted first, then cut to 200 chars."""
    text = str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {e}"
    return (trace.redact(text).splitlines() or [""])[0][:200]


def call(trace: Trace, what: str, fn, retry=transient, waits=WAITS):
    """fn(), repeated after each wait while retry(error) holds and the time limit allows it."""
    for attempt, wait in enumerate((*waits, None), start=1):
        try:
            return fn()
        except (RuntimeError, *NETWORK_ERRORS) as e:
            if wait is None or not retry(e):
                raise
            failed = f"{what}: attempt {attempt} failed ({describe(trace, e)})"
            if time_left() < wait + ATTEMPT_S:
                trace.warn(f"{failed}; giving up: 30-minute build limit near")
                raise
            trace.warn(f"{failed}; retrying in {wait}s")
            time.sleep(wait)


def dry_run(trace: Trace, name: str, workflow: dict) -> None:
    t0 = time.monotonic()
    call(
        trace,
        "POST /api/v2/workflow?dryRun=true",
        lambda: kit().validate_workflow(name, workflow),
    )
    trace.test("platform dry-run validation", True, f"{time.monotonic() - t0:.1f}s")


def _recorded(slot: str) -> bool:
    return STATE_FILE.exists() and slot in json.loads(STATE_FILE.read_text())


def save(trace: Trace, slot: str, workflow: dict) -> dict:
    """Create once, then update in place and publish (freya.save_workflow).

    kit.save_workflow picks its path from the state file on every attempt. Updating a recorded
    slot (PUT full replace, GETs, publish the newest version) converges to the same result when
    repeated. Creating one is a single POST whose id is recorded only after it returns, so a
    5xx or a timeout the platform did process leaves a workflow the state never sees, and a
    repeat creates a second one. Every transient error is retried anyway: refusing does not
    avoid the duplicate (the operator's re-run sends the same POST), and losing the build is
    worse than a few stray workflows out of 200. Such a retry gets a WARN.
    """

    def retry(e: Exception) -> bool:
        if not transient(e):
            return False
        if not unprocessed(e) and not _recorded(slot):
            trace.warn(
                f"slot '{slot}': the failed create may have been processed;"
                " this retry can leave a stray workflow"
            )
        return True

    saved = call(
        trace,
        f"save slot '{slot}' (create POST or update PUT + publish)",
        lambda: kit().save_workflow(slot, workflow, state_file=str(STATE_FILE)),
        retry,
    )
    saved = dict(saved)
    trace.step(f"saved slot '{slot}' (published version {saved.get('version', 1)})")
    return saved


def export(trace: Trace, workflow_id: str, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    call(
        trace,
        f"GET /api/v2/workflow/{workflow_id}",
        lambda: kit().export_workflow(workflow_id, path),
    )
    trace.step(f"exported workflow {workflow_id} to {path}")
