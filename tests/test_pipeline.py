"""extract_spec's repair loop, with the LLM stubbed out (no network)."""

import copy
import io
import json
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
