"""Bounded retries of Freya platform calls, with the kit client faked (no network).

11 Oct 08:40 UTC: two builds failed on the dry run with 503 "API key validation is temporarily
unavailable", 504 and 500 before a third attempt passed.
"""

import io
import json
import urllib.error

import pytest

from freya_builder import platform
from freya_builder.trace import Trace

UNAVAILABLE = '{"message":"API key validation is temporarily unavailable. Retry shortly."}'


class _FakeKit:
    """Fails with the scripted errors in order, then succeeds."""

    def __init__(self, errors):
        self.errors, self.calls = list(errors), 0

    def _next(self, method, path):
        self.calls += 1
        if self.errors:
            e = self.errors.pop(0)
            if isinstance(e, Exception):
                raise e
            status, body = e if isinstance(e, tuple) else (e, "error")
            raise RuntimeError(f"{method} {path} -> {status}: {body}")

    def validate_workflow(self, name, workflow):
        self._next("POST", "/api/v2/workflow")
        return {"valid": True}

    def save_workflow(self, slot, workflow, state_file):
        self._next("POST", "/api/v2/workflow")
        return {"workflow_id": "wf1", "agent_id": "ag1"}

    def export_workflow(self, workflow_id, path):
        self._next("GET", f"/api/v2/workflow/{workflow_id}")
        return path


@pytest.fixture
def setup(monkeypatch, tmp_path):
    waits = []
    monkeypatch.setattr(platform.time, "sleep", waits.append)
    monkeypatch.setattr(platform, "STATE_FILE", tmp_path / "state.json")
    out = io.StringIO()

    def use(errors):
        fake = _FakeKit(errors)
        monkeypatch.setattr(platform, "kit", lambda: fake)
        return fake

    return use, Trace(out), out, waits


def test_dry_run_retries_503_504_500_then_succeeds(setup):
    use, trace, out, waits = setup
    fake = use([(503, UNAVAILABLE), 504, 500])
    platform.dry_run(trace, "slot", {})
    log = out.getvalue()
    assert fake.calls == 4 and waits == [5, 15, 30]
    assert "POST /api/v2/workflow -> 503: " in log and "retrying in 5s" in log
    assert "POST /api/v2/workflow -> 504: error); retrying in 15s" in log
    assert "POST /api/v2/workflow -> 500: error); retrying in 30s" in log
    assert log.count("WARN") == 3 and "platform dry-run validation: PASS" in log


def test_dry_run_retries_network_errors(setup):
    use, trace, out, waits = setup
    fake = use([urllib.error.URLError("reset"), TimeoutError("read timed out")])
    platform.dry_run(trace, "slot", {})
    assert fake.calls == 3 and waits == [5, 15]
    assert "URLError" in out.getvalue() and "TimeoutError" in out.getvalue()


def test_a_rejected_workflow_is_not_retried(setup):
    use, trace, out, waits = setup
    fake = use([(400, "nodes.x: invalid")])
    with pytest.raises(RuntimeError, match="-> 400"):
        platform.dry_run(trace, "slot", {})
    assert fake.calls == 1 and waits == [] and "WARN" not in out.getvalue()


def test_retries_are_bounded(setup):
    use, trace, out, waits = setup
    fake = use([502] * 10)
    with pytest.raises(RuntimeError, match="-> 502"):
        platform.dry_run(trace, "slot", {})
    assert fake.calls == len(platform.WAITS) + 1 and waits == list(platform.WAITS)
    assert sum(waits) <= 240


def test_export_retries_a_5xx(setup, tmp_path):
    use, trace, out, waits = setup
    fake = use([504])
    platform.export(trace, "wf1", str(tmp_path / "x.json"))
    assert fake.calls == 2 and "GET /api/v2/workflow/wf1 -> 504" in out.getvalue()


def test_save_retries_every_unprocessed_rejection(setup):
    use, trace, out, waits = setup
    fake = use([(503, UNAVAILABLE), 429, (503, UNAVAILABLE)])
    assert platform.save(trace, "slot", {})["workflow_id"] == "wf1"
    assert fake.calls == 4 and "duplicate" not in out.getvalue()


def test_save_retries_another_5xx_only_once_and_warns_of_a_duplicate(setup):
    use, trace, out, waits = setup
    fake = use([500, 500])
    with pytest.raises(RuntimeError, match="-> 500"):
        platform.save(trace, "slot", {})
    log = out.getvalue()
    assert fake.calls == 2 and waits == [5]
    assert "slot 'slot' has no recorded workflow: a duplicate workflow may result" in log


def test_save_update_of_a_recorded_slot_retries_without_a_duplicate_warning(setup):
    use, trace, out, waits = setup
    platform.STATE_FILE.write_text(json.dumps({"slot": {"workflow_id": "wf1"}}))
    fake = use([502])
    platform.save(trace, "slot", {})
    assert fake.calls == 2 and "duplicate" not in out.getvalue()


def test_save_does_not_retry_a_4xx(setup):
    use, trace, out, waits = setup
    fake = use([409])
    with pytest.raises(RuntimeError, match="-> 409"):
        platform.save(trace, "slot", {})
    assert fake.calls == 1 and waits == []
