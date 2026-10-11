"""Unit tests for dashboard/compare.py on synthetic run records (no network, no runs/ data).

uv run pytest dashboard/test_compare.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare as C  # noqa: E402

PUBLIC = "kit/public-test-set.json"
STYLED = "styled-a.json"


def fake_definition(path: str, case_id: str, start: float, end: float) -> dict:
    styled = "styled" in path
    return {
        "file": path,
        "commit": "c0ffee0",
        "hash": f"h{len(path)}{case_id}",
        "case": {
            "id": case_id,
            "brief": "A",
            "family": "Amounts",
            "style": "talkative" if styled else None,
        },
        "flags": [],
    }


def trace(name: str, commit: str, dirty: bool = False) -> dict:
    return {
        "file": f"runs/t/{name}.log",
        "git": commit,
        "label": None,
        "dirty": dirty,
        "mode": "saved-spec",
        "spec": None,
        "slot": name,
        "briefs": ["kit/briefs/brief-a.md"],
        "published_version": 1,
        "created": {
            "ts": 0.0,
            "time": "2026-10-10T00:00:00Z",
            "agent_id": name,
            "workflow_id": "w",
            "version": None,
        },
    }


def run(
    rid,
    deploy,
    reps_by_case,
    end_ts,
    case_file=STYLED,
    reps=3,
    complete=True,
    flags=(),
    failures=None,
):
    failures = failures or {}
    cases = []
    for cid, rr in reps_by_case.items():
        fails = failures.get(cid) or [
            {"rep": i + 1, "call_id": None, "category": "Payment amounts"}
            for i, r in enumerate(rr)
            if r is False
        ]
        cases.append({"id": cid, "family": "Amounts", "reps": rr, "failures": fails})
    return {
        "id": f"runs/{rid}.json",
        "name": rid,
        "agent_id": deploy,
        "slot": deploy,
        "deploy_log": f"runs/t/{deploy}.log",
        "flags": list(flags),
        "commit": None,
        "commit_source": "build trace START git=",
        "case_file": case_file,
        "brief": "A",
        "cases": cases,
        "reps": reps,
        "complete": complete,
        "official_style": complete and reps >= 3,
        "end": C.D.iso(end_ts),
        "end_ts": end_ts,
        "seconds": 60,
        "agent_kind": "A-only",
    }


T0 = 1791600000.0  # 2026-10-10 UTC


def model(runs, traces=None):
    traces = traces or [
        trace("old", "aaaaaaa"),
        trace("new", "bbbbbbb"),
        trace("g", "ccccccc", dirty=True),
    ]
    return C.build(runs, [], traces, [], definition_of=fake_definition)


def diff(base, a="old", b="new", **q):
    query = {k: [v] for k, v in q.items()}
    query.update(a=[f"deploy:runs/t/{a}.log"], b=[f"deploy:runs/t/{b}.log"])
    return C.view(base, query)["comparison"]


def cases_in(cm, bucket):
    return [i["case"] for i in cm[bucket]]


def test_regression_is_newly_failing_and_fix_is_newly_passing():
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True], "PUB-07": [True, False, True]}, T0),
        run("r2", "new", {"PUB-06": [True, False, True], "PUB-07": [True, True, True]}, T0 + 600),
    ])  # fmt: skip
    cm = diff(base)
    assert cases_in(cm, "newly_failing") == ["PUB-06"]
    assert cases_in(cm, "newly_passing") == ["PUB-07"]
    assert cm["counts"]["unchanged_pass"] == 0


def test_runs_are_never_merged_and_disagreeing_runs_are_inconsistent():
    base = model([
        run("r1", "old", {"PUB-06": [False, True, True]}, T0),
        run("r2", "new", {"PUB-06": [True, False, True]}, T0 + 600),
        run("r3", "new", {"PUB-06": [False, True, True]}, T0 + 1200),
    ])  # fmt: skip
    cm = diff(base)
    assert cases_in(cm, "inconsistent") == [] and cases_in(cm, "unchanged_fail") == ["PUB-06"]
    # three passing reps spread over two failing runs never become a pass
    base = model([
        run("r1", "old", {"PUB-06": [False, True, True]}, T0),
        run("r2", "new", {"PUB-06": [True, True, True]}, T0 + 600),
        run("r3", "new", {"PUB-06": [False, True, True]}, T0 + 1200),
    ])  # fmt: skip
    cm = diff(base)
    assert cases_in(cm, "inconsistent") == ["PUB-06"]
    assert cases_in(cm, "newly_passing") == []
    cell = C.view(base, {})["rows"][0]["cells"]["deploy:runs/t/new.log"]
    assert [e["strict"] for e in cell["entries"]] == [True, False] and cell["status"] == "mixed"


def test_one_rep_and_incomplete_runs_have_no_strict_result():
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True], "PUB-07": [True, True, True]}, T0),
        run("r2", "new", {"PUB-06": [True]}, T0 + 600, reps=1),
        run("r3", "new", {"PUB-07": [True, True, None]}, T0 + 900, complete=False),
    ])  # fmt: skip
    cm = diff(base)
    assert sorted(cases_in(cm, "untested")) == ["PUB-06", "PUB-07"]
    entries = [e for e in base["entries"] if e["config"] == "deploy:runs/t/new.log"]
    assert all(e["strict"] is None and not e["comparable"] for e in entries)
    assert "1-rep run" in entries[0]["strict_note"] and "incomplete" in entries[1]["strict_note"]


def test_unknown_style_is_shown_as_unmatched_and_not_counted():
    base = model([
        run("old-p06-talkative", "old", {"PUB-06": [True, True, True]}, T0, case_file=PUBLIC),
        run("new-p06-talkative", "new", {"PUB-06": [False, False, True]}, T0 + 600, case_file=PUBLIC),
    ])  # fmt: skip
    cm = diff(base)
    assert cases_in(cm, "unmatched_coverage") == ["PUB-06"]
    assert cm["counts"]["newly_failing"] == 0
    row = C.view(base, {})["rows"][0]
    assert row["style"] is None  # the run names say "talkative"; that is not evidence


def test_different_definition_or_style_is_unmatched_coverage():
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True]}, T0, case_file=STYLED),
        run("r2", "new", {"PUB-06": [False, True, True]}, T0 + 600, case_file=PUBLIC),
    ])  # fmt: skip
    cm = diff(base)
    assert len(cm["unmatched_coverage"]) == 2 and cm["counts"]["newly_failing"] == 0
    assert "PUB-01" in cm["untested_by_both"] and "PUB-06" not in cm["untested_by_both"]


def test_configuration_uncertainty_excludes_the_run():
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True]}, T0),
        run("r2", "new", {"PUB-06": [False, True, True]}, T0 + 600, flags=["Agent was redeployed DURING this run: x"]),
    ])  # fmt: skip
    cm = diff(base)
    assert cases_in(cm, "untested") == ["PUB-06"] and cm["counts"]["newly_failing"] == 0
    assert "configuration uncertain" in cm["untested"][0]["reason"]


def test_dirty_build_and_platform_interpretation_are_flagged_not_applied():
    platform = [{"rep": 2, "call_id": "c", "category": C.PLATFORM}]
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True]}, T0),
        run("r2", "g", {"PUB-06": [True, False, True]}, T0 + 600, failures={"PUB-06": platform}),
    ])  # fmt: skip
    cm = diff(base, b="g")
    assert cases_in(cm, "newly_failing") == ["PUB-06"]  # the raw result is never forgiven
    interp = cm["newly_failing"][0]["b"]["runs"][0]["platform_interpretation"]
    assert (
        interp["reps_with_platform_evidence"] == [2]
        and "not a strict 3/3" in interp["if_set_aside"]
    )
    assert any("dirty=True" in f for f in cm["provenance_warnings"]["b"])
    assert {"field": "dirty", "a": False, "b": True} in cm["differences"]


def test_filters_and_validation():
    base = model([
        run("r1", "old", {"PUB-06": [True, True, True]}, T0),
        run("r2", "new", {"PUB-06": [True, True, True]}, T0 + 2 * 86400),
    ])  # fmt: skip
    v = C.view(base, {"to": ["2026-10-10"]})
    assert [c["id"] for c in v["configurations"]] == ["deploy:runs/t/old.log"]
    assert C.view(base, {"style": ["unknown"]})["rows"] == []
    for bad in ({"from": ["10/10/2026"]}, {"config": ["nope"]}, {"a": ["deploy:runs/t/old.log"]},
                {"a": ["deploy:runs/t/old.log"], "b": ["deploy:runs/t/old.log"]}, {"brief": ["Z"]},
                {"case": ["PUB-06", "PUB-07"]}):  # fmt: skip
        with pytest.raises(C.QueryError):
            C.view(base, bad)


def test_partial_log_counts_only_finished_reps():
    log = "\n".join([
        "FAIL PUB-11 hard   Multi-product  | (no tool calls)",
        "       - outcome (None, None), expected ('no_promise', 'refused')",
        "PASS PUB-12 hard   Multi-product  | verify > close_call",
        "-- run 1 of 3: 1 / 2 passed, 52 s",
        "PASS PUB-11 hard   Multi-product  | verify > close_call",
        "-- run 2 of 3: 1 / 1 passed, 40 s",
        "FAIL PUB-12 hard   Multi-product  | verify",
    ])  # fmt: skip
    p = C.parse_partial_log(log)
    assert p["reps_planned"] == 3 and p["reps_completed"] == 2 and p["unterminated_case_lines"] == 1
    assert {c["id"]: c["reps"] for c in p["cases"]} == {
        "PUB-11": [False, True],
        "PUB-12": [True, None],
    }


# ---- regression cases for the findings of the 2026-10-11 verification run


def test_style_filter_keeps_other_style_coverage_as_unmatched_not_untested():
    base = model([
        run("x1", "old", {"PUB-06": [True, True, True]}, T0, case_file=STYLED),
        run("x2", "new", {"PUB-06": [True, True, True]}, T0 + 600, case_file=PUBLIC),
    ])  # fmt: skip
    cm = diff(base, style="unknown")
    assert cases_in(cm, "untested") == [] and cases_in(cm, "unmatched_coverage") == ["PUB-06"]
    assert "PUB-06" not in cm["untested_by_both"]


def test_untested_by_both_lists_the_brief_even_when_nothing_ran_in_range():
    base = model([
        run("x1", "old", {"PUB-06": [True, True, True]}, T0),
        run("x2", "new", {"PUB-06": [True, True, True]}, T0 + 600),
    ])  # fmt: skip
    cm = diff(base, brief="A", **{"from": "2026-10-20"})
    assert sum(cm["counts"].values()) == 0
    assert cm["untested_by_both"] == [f"PUB-{i:02d}" for i in range(1, 11)]


def test_differences_include_version_and_unknowns_are_not_equal():
    old, new = trace("old", None), trace("new", None)
    old["created"]["version"], new["created"]["version"] = 3, 4
    base = model(
        [
            run("x1", "old", {"PUB-06": [True] * 3}, T0),
            run("x2", "new", {"PUB-06": [True] * 3}, T0 + 9),
        ],
        traces=[old, new],
    )
    cm = diff(base)
    assert {"field": "version", "a": 3, "b": 4} in cm["differences"]
    assert "commit" in cm["unknown_on_both_sides"] and "dirty" not in cm["unknown_on_both_sides"]


def test_untraced_configuration_never_shows_a_disproved_commit():
    r = run("x1", "nobody", {"PUB-06": [True] * 3}, T0)
    r.update(
        deploy_log=None,
        commit="05eb2db",
        commit_source="Score log 'Git ref'",
        flags=["Commit 05eb2db was made after this run started: it cannot be the tested code"],
    )
    cfg = next(iter(model([r])["configs"].values()))
    assert cfg["commit"] is None and "made after this run started" in cfg["commit_source"]
    assert {"run": r["id"], "commit": "05eb2db", "source": "Score log 'Git ref'"} in cfg[
        "run_commit_claims"
    ]


def test_commit_claims_from_the_file_name_show_for_traced_configurations():
    r = run("zz-unique-name-1234567", "old", {"PUB-06": [True] * 3}, T0)
    r.update(commit="aaaaaaa", label="1234567")
    cfg = model([r])["configs"]["deploy:runs/t/old.log"]
    assert [c["commit"] for c in cfg["run_commit_claims"]] == ["1234567"]


def test_non_historical_definition_is_never_comparable():
    def current_file(path, cid, s, e):
        d = fake_definition(path, cid, s, e)
        return {**d, "source": "CURRENT case file (not historical)", "historical": False}

    base = C.build(
        [run("x1", "old", {"PUB-06": [True] * 3}, T0)],
        [],
        [trace("old", "aaaaaaa")],
        [],
        definition_of=current_file,
    )
    e = base["entries"][0]
    assert not e["comparable"] and "not verifiable" in e["not_comparable_because"][0]
    assert e["row"].split("|")[2].startswith("unverified:")


def test_partial_log_drops_a_discarded_attempt():
    log = "\n".join([
        "FAIL PUB-11 hard   Multi-product  | (no tool calls)",
        "-- run discarded: median slowest turn 30 s. Waiting 5 minutes, then repeating it.",
        "PASS PUB-12 hard   Multi-product  | verify",
        "-- run 1 of 2: 1 / 1 passed, 40 s",
    ])  # fmt: skip
    p = C.parse_partial_log(log)
    assert {c["id"]: c["reps"] for c in p["cases"]} == {"PUB-12": [True]}


def test_redacted_json_stays_parseable():
    import json

    body = C.D.dumps({"error": "unknown case 'password=abcdefgh'", "x": ["Bearer abcdefghijk"]})
    parsed = json.loads(body)  # redacting serialised JSON used to swallow the closing quote
    assert "abcdefgh" not in body and parsed["x"] == ["[REDACTED]"]
