"""Freya platform calls for the builder, through the official kit client (kit/freya.py).

The kit client reads FREYA_API_KEY / FREYA_API_URL at import time; it is imported lazily so
that --dry runs and unit tests need no credentials.
"""

import sys
import time
from pathlib import Path

from .trace import Trace

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / ".freya-agents.json"


def kit():
    if str(ROOT / "kit") not in sys.path:
        sys.path.insert(0, str(ROOT / "kit"))
    import freya

    return freya


def dry_run(trace: Trace, name: str, workflow: dict) -> None:
    t0 = time.monotonic()
    kit().validate_workflow(name, workflow)
    trace.test("platform dry-run validation", True, f"{time.monotonic() - t0:.1f}s")


def save(trace: Trace, slot: str, workflow: dict) -> dict:
    """Create once, then update in place and publish (freya.save_workflow)."""
    saved = dict(kit().save_workflow(slot, workflow, state_file=str(STATE_FILE)))
    trace.step(f"saved slot '{slot}' (published version {saved.get('version', 1)})")
    return saved


def export(trace: Trace, workflow_id: str, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    kit().export_workflow(workflow_id, path)
    trace.step(f"exported workflow {workflow_id} to {path}")
