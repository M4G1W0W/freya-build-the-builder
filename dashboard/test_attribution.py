"""Regression tests for the attribution bugs found by the 2026-10-11 dashboard audit (no network).

uv run pytest dashboard/test_attribution.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as D  # noqa: E402

FIX = "tests/fixtures/cases/"


def test_launch_meta_names_the_case_file(tmp_path):
    (tmp_path / "M3-G1-styledA.json").write_text("{}")
    meta = {"cases": FIX + "styled-a.json", "cases_sha256": "x", "slot": "exp-g1-a"}
    (tmp_path / "M3-G1-styledA.meta.json").write_text(json.dumps(meta))
    rec = D.launch_record(tmp_path / "M3-G1-styledA.json")
    assert rec["cases"] == FIX + "styled-a.json" and rec["source"].endswith(".meta.json")
    assert D.case_ref(rec["cases"]) == "styled-a.json"  # same name as name-convention runs


def test_calls_tsv_row_when_there_is_no_meta(tmp_path):
    (tmp_path / "calls.tsv").write_text(
        "end_utc\tname\tslot\tcasefile\tcases\treps\tdiscarded\texit\tcalls\tcumulative\n"
        "# a comment line\n"
        "t\tSMOKE-e4a\texp-eng4-a\truns/dev/r4/smoke-pub01.json\t1\t1\t0\t0\t2\t287\n"
        "t\tSMOKE-e4a-platform-retry\texp-eng4-a\t(platform retry)\t1\t0\t0\t-\t2\t289\n"
    )
    rec = D.launch_record(tmp_path / "SMOKE-e4a.json")
    assert rec["cases"] == "runs/dev/r4/smoke-pub01.json" and "calls.tsv" in rec["source"]
    assert D.case_ref(rec["cases"]) == "runs/dev/r4/smoke-pub01.json"
    assert D.launch_record(tmp_path / "SMOKE-e4a-platform-retry.json") is None  # not a case file


def test_case_sets_extra_b_by_file_and_a_plus_b_by_ids():
    a = [f"PUB-{i:02d}" for i in range(1, 11)]
    b = ["PUB-11", "PUB-12", "PUB-13"]
    assert D.case_set_for("styled-extra-b.json", b)[0] == "extra-B"  # same ids as Brief B
    assert D.case_set_for("extra-b-rederived.json", b)[0] == "extra-B"
    assert D.case_set_for("styled-b.json", b)[0] == "B"
    assert D.case_set_for("styled-ab-all.json", a + b)[0] == "A+B"
    assert D.case_set_for("block-p06.json", ["PUB-03", "PUB-06"])[0] == "A"
    assert D.EXPECTED_TOTAL["A+B"] == 13


def test_agent_kind_from_a_verified_spec(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"meta": {"max_products": 3}}))
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()
    assert D.spec_products(spec, sha, None) == (
        3,
        "spec content verified by the launch record's sha256",
    )
    assert D.spec_products(spec, "0" * 64, None)[0] is None  # changed since the launch
    assert D.spec_products(spec, None, None)[0] is None  # nothing proves it is the deployed spec


def test_trace_spec_path_with_spaces(tmp_path):
    log = tmp_path / "build.log"
    log.write_text(
        "2026-10-11T12:00:00Z START   briefs=['kit/briefs/brief-a.md'] git=cfa4d9d dirty=False\n"
        f"2026-10-11T12:00:01Z WARN    DEV: using provided spec {D.ROOT}/runs/dev/spec-a-llm.json; "
        "the brief was not read by the LLM\n"
        "exp07 variant=offerdate negotiate changed=True\n"
    )
    t = D.parse_trace(log)
    assert t["spec"] == "runs/dev/spec-a-llm.json" and t["mode"] == "saved-spec"
    assert t["variants"] == ["exp07 variant=offerdate negotiate changed=True"]


def test_missing_verdict_never_hides_a_bank_record_failure():
    ledger = {
        "failed": [
            "outcome (not_verified, declined), expected (no_promise, refused)",
            "conversation: no verdict",
        ],
        "tools": ["verify"],
        "slowest_turn_s": 3,
    }
    primary, tags = D.classify(ledger)
    assert primary != "Platform errors" and any("No judge verdict" in t for t in tags)
    only = {
        "failed": ["conversation: analysis never arrived (300s)"],
        "tools": ["verify"],
        "slowest_turn_s": 3,
    }
    assert D.classify(only)[0] == "Platform errors"


def test_promise_categories():
    one = "[('p1', 220.0, '2026-10-16')]"
    two = "[('p1', 220.0, '2026-10-16'), ('p2', 640.0, '2026-10-16')]"
    assert D._ledger_category([f"promises {one}, expected {two}"]) == "Promises missing or extra"
    later = "[('p1', 220.0, '2026-10-20')]"
    assert D._ledger_category([f"promises {later}, expected {one}"]) == "Date calculations"
    other = "[('p1', 200.0, '2026-10-16')]"
    assert D._ledger_category([f"promises {other}, expected {one}"]) == "Payment amounts"


def test_running_pattern_catches_system_python_and_smoke_scripts():
    for cmd in (
        "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python -u scripts/run_cases_retry.py 768e75c2 --out runs/dev/r4/x.json",
        "python3 scripts/smoke_once.py 4c2a --out runs/dev/r4/SMOKE.json",
        ".venv/bin/python -u kit/tools/run_cases.py abc --out runs/x.json",
    ):
        assert D.EXECUTES.search(cmd), cmd
    assert not D.EXECUTES.search("vim scripts/run_cases_retry.py")
