"""extract_spec's repair loop, with the LLM stubbed out (no network)."""

import copy
import io
import json
import re
from pathlib import Path

import pytest

from freya_builder import pipeline
from freya_builder.toolapi import load_tool_api
from freya_builder.trace import Trace

ROOT = Path(__file__).resolve().parents[1]
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())
TOOLS = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")


def _stub(monkeypatch, specs):
    calls = []

    def fake_chat_json(trace, purpose, system, user, schema, name):
        calls.append(purpose)
        return copy.deepcopy(specs[min(len(calls), len(specs)) - 1])

    monkeypatch.setattr(pipeline, "chat_json", fake_chat_json)
    return calls


def test_unrepairable_problem_deploys_the_best_spec_with_warnings(monkeypatch):
    # Audit F72: a check_spec problem the LLM cannot repair used to abort the whole build (0/30 on
    # that brief). Now the best schema-valid spec is returned and every problem is in the trace.
    bad = copy.deepcopy(SPEC_A)
    bad["default_rows"]["opening"] = "nope"
    calls = _stub(monkeypatch, [bad])
    out = io.StringIO()
    spec = pipeline.extract_spec(Trace(out), "brief", TOOLS)
    assert spec["default_rows"]["opening"] == "nope"
    assert len(calls) == 1 + pipeline.REPAIR_ROUNDS
    log = out.getvalue()
    assert "UNRESOLVED spec problem (deployed anyway): default row for opening" in log
    assert "deploying the best spec with 1 unresolved problem(s)" in log


def test_best_spec_is_the_one_with_fewest_problems(monkeypatch):
    two = copy.deepcopy(SPEC_A)
    two["default_rows"]["opening"] = "nope"
    two["default_rows"]["identity"] = "nope"
    one = copy.deepcopy(SPEC_A)
    one["default_rows"]["opening"] = "nope"
    _stub(monkeypatch, [two, one, two])
    spec = pipeline.extract_spec(Trace(io.StringIO()), "brief", TOOLS)
    assert spec["default_rows"]["identity"] == SPEC_A["default_rows"]["identity"]


def test_no_schema_valid_spec_still_aborts(monkeypatch):
    broken = copy.deepcopy(SPEC_A)
    del broken["rows"]
    _stub(monkeypatch, [broken])
    with pytest.raises(ValueError, match="no schema-valid spec"):
        pipeline.extract_spec(Trace(io.StringIO()), "brief", TOOLS)


class _FakeFreya:
    def __init__(self, errors):
        self.errors, self.calls = list(errors), []

    def api(self, method, path, body=None, **params):
        self.calls.append(path)
        self.body = body if path.endswith("/chat/message") else getattr(self, "body", None)
        if path.endswith("/chat/message") and self.errors:
            raise RuntimeError(f"POST {path} -> {self.errors.pop(0)}: error")
        return {
            "response": "I am a digital assistant. Am I speaking with Mr Reyes?",
            "callId": "c1",
        }


def test_smoke_test_retries_a_transient_5xx(monkeypatch):
    # 10 Oct 15:55 UTC: one 504 from the chat route made the trace show a failed self-test.
    fake = _FakeFreya([504])
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    out = io.StringIO()
    pipeline.selftest(Trace(out), {"workflow_id": "wf"}, SPEC_A, TOOLS)
    log = out.getvalue()
    assert "POST /api/v2/chat/message -> 504: error); retrying in 5s" in log
    assert "chat smoke test: opening reply: PASS" in log


def test_smoke_test_does_not_retry_a_client_error(monkeypatch):
    fake = _FakeFreya([400, 400])
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    out = io.StringIO()
    assert pipeline.selftest(Trace(out), {"workflow_id": "wf"}, SPEC_A, TOOLS) is False
    assert "chat smoke test: workflow starts: FAIL" in out.getvalue()
    assert fake.calls.count("/api/v2/chat/message") == 1


def test_smoke_test_fails_after_a_short_retry_schedule(monkeypatch):
    fake = _FakeFreya([503] * 10)
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)
    out = io.StringIO()
    assert pipeline.selftest(Trace(out), {"workflow_id": "wf"}, SPEC_A, TOOLS) is False
    assert fake.calls.count("/api/v2/chat/message") == len(pipeline.SMOKE_WAITS) + 1
    assert "chat smoke test: workflow starts: FAIL" in out.getvalue()


def test_smoke_test_does_not_retry_a_bare_500(monkeypatch):
    # kit/docs/api.md: a bare 500 from /chat/message means the workflow cannot start a call.
    fake = _FakeFreya([500, 500])
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    out = io.StringIO()
    assert pipeline.selftest(Trace(out), {"workflow_id": "wf"}, SPEC_A, TOOLS) is False
    assert fake.calls.count("/api/v2/chat/message") == 1
    assert "chat smoke test: workflow starts: FAIL" in out.getvalue()


def test_a_brief_read_as_single_product_is_flagged_in_the_trace(monkeypatch):
    # Review gap 2: the agent gets 3 product slots anyway; the trace says why.
    monkeypatch.setattr(pipeline, "consolidate", lambda trace, text, tools: {"kind": "clean"})
    monkeypatch.setattr(pipeline, "extract_spec", lambda trace, text, tools: copy.deepcopy(SPEC_A))
    out = io.StringIO()
    pipeline.extract(Trace(out), "brief", TOOLS)
    assert "brief read as 1 product(s); rendering 3 product slots" in out.getvalue()


def test_smoke_test_sends_a_real_now_and_reports_its_result(monkeypatch):
    # Review gap 15: `now` used to be "x" when the spec gave no example.
    fake = _FakeFreya([])
    monkeypatch.setattr(pipeline.platform, "kit", lambda: fake)
    spec = copy.deepcopy(SPEC_A)
    for v in spec["meta"]["call_vars"]:
        if v["role"] == "now":
            v["example"] = ""
    assert pipeline.selftest(Trace(io.StringIO()), {"workflow_id": "wf"}, spec, TOOLS) is True
    now = next(v["name"] for v in spec["meta"]["call_vars"] if v["role"] == "now")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", fake.body["customerVariables"][now])


def test_repair_rounds_are_skipped_when_the_build_budget_runs_low(monkeypatch):
    # Review gap 13: the page allows 30 min per brief including self-tests.
    bad = copy.deepcopy(SPEC_A)
    bad["default_rows"]["opening"] = "nope"
    calls = _stub(monkeypatch, [bad])
    monkeypatch.setattr(pipeline, "budget_left", lambda: 60.0)
    out = io.StringIO()
    spec = pipeline.extract_spec(Trace(out), "brief", TOOLS)
    assert len(calls) == 1 and spec["default_rows"]["opening"] == "nope"
    assert "skipping repair round 1" in out.getvalue()


def test_a_failed_repair_call_keeps_the_best_spec(monkeypatch):
    # Diff review 8: a repair call out of budget or models crashed the build with a valid spec.
    bad = copy.deepcopy(SPEC_A)
    bad["default_rows"]["opening"] = "nope"
    calls = []

    def chat(trace, purpose, system, user, schema, name):
        calls.append(purpose)
        if purpose.startswith("repair"):
            raise pipeline.LLMError("repair policy spec (round 1): build time budget used up")
        return copy.deepcopy(bad)

    monkeypatch.setattr(pipeline, "chat_json", chat)
    out = io.StringIO()
    spec = pipeline.extract_spec(Trace(out), "brief", TOOLS)
    assert spec["default_rows"]["opening"] == "nope"
    assert "keeping the best spec" in out.getvalue()


def test_extraction_turns_say_that_rules_into_required_sentences():
    # a8b70ea styled extra-B PUB-12: the A+B spec's paid row had no say_before_end, because the
    # brief says "say that payments can take one business day to appear" rather than quoting it.
    assert 'a rule "say that X" gives the sentence X' in pipeline.SPEC_SYSTEM
