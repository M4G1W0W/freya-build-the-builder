"""Freya platform calls for the builder, through the official kit client (kit/freya.py).

The kit client reads FREYA_API_KEY / FREYA_API_URL at import time; it is imported lazily so
that --dry runs and unit tests need no credentials.

The platform has transient outages (11 Oct 08:40 UTC: 503 "API key validation is temporarily
unavailable", then 504, then 500 on the dry run), so calls are retried, bounded, on 429/5xx and
network errors; other 4xx (a rejected workflow) are never retried.
"""

import http.client
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

from .trace import Trace

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / ".freya-agents.json"
NETWORK_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
)
WAITS = (5, 15, 30)  # seconds before attempts 2, 3 and 4: at most 50 s of extra wait per call


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
    return status == 429 or (status == 503 and "temporarily unavailable" in str(e).lower())


def _describe(e: Exception) -> str:
    text = str(e) if isinstance(e, RuntimeError) else f"{type(e).__name__}: {e}"
    return (text.splitlines() or [""])[0][:200]


def call(trace: Trace, what: str, fn, retry=transient):
    """fn(), repeated after each wait in WAITS while retry(error) holds; a WARN line per retry."""
    for attempt, wait in enumerate((*WAITS, None), start=1):
        try:
            return fn()
        except (RuntimeError, *NETWORK_ERRORS) as e:
            if wait is None or not retry(e):
                raise
            trace.warn(f"{what}: attempt {attempt} failed ({_describe(e)}); retrying in {wait}s")
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
    repeat creates a second one. Losing the build is worse than one stray workflow out of 200,
    so such an error gets one retry, with a WARN when it may duplicate. Only an error that was
    certainly not processed (unprocessed()) uses every retry.
    """
    ambiguous_retried = False

    def retry(e: Exception) -> bool:
        nonlocal ambiguous_retried
        if unprocessed(e):
            return True
        if ambiguous_retried or not transient(e):
            return False
        ambiguous_retried = True
        if not _recorded(slot):
            trace.warn(f"slot '{slot}' has no recorded workflow: a duplicate workflow may result")
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
