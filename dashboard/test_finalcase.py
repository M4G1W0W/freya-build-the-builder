"""Unit tests for dashboard/finalcase.py (no network; synthetic files only, nothing from the case).

uv run pytest dashboard/test_finalcase.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import finalcase as F  # noqa: E402

T0 = 1_800_000_000.0


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


@pytest.fixture
def case(tmp_path, monkeypatch):
    folder = tmp_path / "case"
    folder.mkdir()
    monkeypatch.setenv("FREYA_FINAL_CASE_DIR", str(folder))
    monkeypatch.setattr(F, "LEDGER", tmp_path / "ledger.json")
    monkeypatch.setattr(F, "REVIEW_FILE", tmp_path / "review.json")
    chat = tmp_path / "chat.md"
    monkeypatch.setattr(F, "handoff_sources", lambda: [("chat 'Engineer'", chat)])
    monkeypatch.setattr(F, "committed_case_mentions", lambda names: {})
    F._hash_cache.clear()
    F._text_cache.clear()
    return folder, chat, tmp_path


def test_ledger_records_versions_amendments_and_removals(case):
    folder, _, _ = case
    ledger = {"folders": {}}
    _write(folder / "a.md", "one")
    assert F.update_ledger(ledger, folder, F.scan(folder), T0)
    assert not F.update_ledger(ledger, folder, F.scan(folder), T0 + 12)
    _write(folder / "a.md", "two")
    assert F.update_ledger(ledger, folder, F.scan(folder), T0 + 60)
    e = ledger["folders"][str(folder)]["files"]["a.md"]
    assert [v["first_seen"] for v in e["versions"]] == [T0, T0 + 60]
    (folder / "a.md").unlink()
    assert F.update_ledger(ledger, folder, F.scan(folder), T0 + 90)
    assert e["removed_at"] == T0 + 90


def test_scan_skips_hidden_lock_and_os_files(case):
    folder, _, _ = case
    for name in (".DS_Store", "~$draft.docx", "__MACOSX/x.md", "sub/b.md"):
        _write(folder / name, "x")
    assert [x["rel"] for x in F.scan(folder)] == ["sub/b.md"]


def test_snapshot_at_picks_the_versions_present_at_that_time(case):
    folder, _, _ = case
    ledger = {"folders": {}}
    _write(folder / "a.md", "one")
    F.update_ledger(ledger, folder, F.scan(folder), T0)
    _write(folder / "b.md", "late")
    _write(folder / "a.md", "two")
    F.update_ledger(ledger, folder, F.scan(folder), T0 + 100)
    entry = ledger["folders"][str(folder)]
    early, late = F.snapshot_at(entry, T0 + 50), F.snapshot_at(entry, T0 + 150)
    assert [(x["rel"], x["version"]) for x in early["files"]] == [("a.md", 1)]
    assert [(x["rel"], x["version"]) for x in late["files"]] == [("a.md", 2), ("b.md", 1)]
    assert early["id"] != late["id"]
    assert F.snapshot_at(entry, T0 - 100)["basis"].startswith("approximate")


def test_name_versions_siblings_and_kind_guesses():
    assert F.name_version("policy_v2.docx") == "v 2"
    assert F.name_version("policy rev 3.pdf") == "rev 3"
    assert F.name_version("plain.md") is None
    assert F.stem_key("policy_v2.docx") == F.stem_key("policy-v1.docx") == "policy"
    assert F.guess_kind("flow-drawing.pdf", None) == "flow drawing"
    assert F.guess_kind("x.md", "Customer list") == "test customers"
    assert F.guess_kind("notes.md", None) is None


def test_readme_purposes_and_absent_documents(case):
    folder, _, _ = case
    _write(folder / "README.md", "- data.xlsx: the records\n- later.pdf: arrives later\n")
    _write(folder / "data.xlsx", "x")
    readme, purposes, absent = F.readme_purposes(F.scan(folder))
    assert readme == "README.md"
    assert purposes["data.xlsx"] == ["- data.xlsx: the records"]
    assert absent == ["later.pdf"]


def test_documents_flags_review_and_mentions(case):
    folder, chat, tmp = case
    _write(folder / "rules.md", "# Rules\nVersion 1.2\n")
    _write(folder / "copy.md", "# Rules\nVersion 1.2\n")
    _write(folder / "spec_v1.md", "a")
    _write(folder / "spec_v2.md", "b")
    now = 2_000_000_000.0
    stamp = "2033-05-18T03:40:00"  # after `now`
    _write(chat, f"### CLAUDE · {stamp}.000Z\nI read spec_v2.md and it is fine\n")
    (tmp / "review.json").write_text(
        json.dumps({"rules.md": {"status": "reviewed", "sha256": "0"}})
    )
    ledger = {"folders": {}}
    docs = F.documents(now, ledger, write=False)["folders"][0]
    by = {d["rel"]: d for d in docs["documents"]}
    assert by["rules.md"]["purpose"]["title"] == "Rules"
    assert by["rules.md"]["version"]["embedded"]["text_version"] == "Version 1.2"
    assert "STALE" in by["rules.md"]["review"]["status"]
    flags = " | ".join(f["text"] for f in by["rules.md"]["flags"])
    assert "identical content to copy.md" in flags
    assert "other version(s) present: spec_v2.md: which is current?" in " ".join(
        f["text"] for f in by["spec_v1.md"]["flags"]
    )
    assert by["spec_v2.md"]["review"]["status"] == "not reviewed (mentioned in 1 chat line(s))"
    assert by["spec_v2.md"]["review"]["mentions"][0]["speaker"] == "CLAUDE"
    assert by["copy.md"]["review"]["status"] == "not reviewed"
    assert docs["completeness"].startswith("NOT confirmed complete")
    assert not by["copy.md"]["flags"] or all(f["kind"] != "new" for f in by["copy.md"]["flags"])


def test_mentions_before_the_file_arrived_do_not_count(case):
    _, chat, _ = case
    _write(chat, "### YOU · 2020-01-01T00:00:00.000Z\nlook at notes.md\n")
    assert F.mentions(["notes.md"], since=T0) == []


TRACE = """2026-10-11T18:00:00Z START   briefs=['{folder}'] tool_api=https://mock.example.workers.dev/v1 sha256=unreadable,unreadable git=abc1234 dirty=False python=3.12 models=m
2026-10-11T18:00:05Z STEP    read 1 document(s), 10 chars; 3 tools
2026-10-11T18:00:09Z MODEL   model=m purpose=extract took=1s
2026-10-11T18:01:00Z CREATED workflow_id=wf_1 agent_id=ag_1 steps=5 tools=3 version=2
2026-10-11T18:01:05Z TEST    chat smoke test: opening reply: PASS
2026-10-11T18:01:06Z END     ok=True build_seconds=66 model_calls=1
"""


def test_final_builds_link_builder_and_document_snapshot(case, monkeypatch):
    folder, _, tmp = case
    trace = _write(tmp / "final.log", TRACE.format(folder=folder))
    monkeypatch.setattr(F, "_final_trace_paths", lambda: [trace])
    start = F.D.parse_utc("2026-10-11T18:00:00Z")
    ledger = {"folders": {}}
    _write(folder / "a.md", "one")
    F.update_ledger(ledger, folder, F.scan(folder), start - 600)
    _write(folder / "b.md", "after the build")
    F.update_ledger(ledger, folder, F.scan(folder), start + 600)
    (b,) = F.final_builds(ledger, None)
    assert b["mock_url"] == "https://mock.example.workers.dev/v1" and not b["dry"]
    assert b["builder"]["commit"] == "abc1234" and b["documents_read"] == 1
    assert [x["rel"] for x in b["snapshot"]["files"]] == ["a.md"]
    assert b["docs_changed_since"] == ["b.md"]
    assert b["created"]["workflow_id"] == "wf_1"


def test_practice_traces_are_not_final_builds(case, monkeypatch):
    _, _, tmp = case
    trace = _write(
        tmp / "p.log", TRACE.replace("https://mock.example.workers.dev/v1", "kit/x.json")
    )
    monkeypatch.setattr(F, "_final_trace_paths", lambda: [trace])
    assert F.final_builds({"folders": {}}, None) == []


def test_final_tests_separate_final_from_practice():
    build = {"file": "traces/final.log", "start_ts": 10.0, "created": {"workflow_id": "wf_1",
             "agent_id": "ag_1", "ts": 10.0}, "builder": {"commit": "abc"}, "snapshot": {"id": "s1"}}  # fmt: skip
    runs = [
        {
            "id": "a",
            "workflow_id": "wf_1",
            "start": "2026-10-11T18:10:00Z",
            "cases": [{"id": "C1"}],
        },
        {"id": "b", "slot": "final-2", "start": "2026-10-11T18:10:00Z", "cases": [{"id": "C1"}]},
        {"id": "c", "start": "2026-10-11T18:10:00Z", "cases": [{"id": "X-9"}]},
        {"id": "d", "start": "2026-10-11T18:10:00Z", "cases": [{"id": "PUB-01"}]},
        {"id": "e", "start": "2026-10-11T12:00:00Z", "cases": [{"id": "X-9"}]},
    ]
    out = {t["run"]: t for t in F.final_tests(runs, [build])}
    assert set(out) == {"a", "b", "c"}
    assert out["a"]["builder_commit"] == "abc" and out["a"]["snapshot"] == "s1"
    assert out["b"]["build"] is None and out["b"]["why_final"] == "slot named final"


def test_compact_and_markdown_survive_an_error():
    assert F.compact({"error": "boom"}) == {"error": "boom"}
    assert "Not available: boom" in F.summary_markdown(F.compact({"error": "boom"}))


def test_no_case_file_name_is_written_into_dashboard_code():
    """Guard: nothing from the final case may enter the repo. Checks whole file names, folder names
    and two-word fragments of file names (dates removed) against every dashboard file. Words on
    the official page (BRIEF.md, README.md, ...) are public and allowed."""
    page = (F.D.ROOT / "docs/reference/hackathon_page_live_2026-10-11.md").read_text().lower()
    terms = set()
    for d in F.case_dirs():
        for x in F.scan(d):
            rel = Path(x["rel"])
            terms.add(rel.name)
            terms |= {part for part in rel.parts[:-1] if re.search(r"[-_\d]", part)}
            words = [w for w in re.split(r"[\W_]+", F.DATE_IN_NAME.sub("", rel.stem)) if w]
            terms |= {
                f"{a}-{b}" for a, b in zip(words, words[1:], strict=False) if len(a) + len(b) >= 7
            }
    terms = {t for t in terms if t.lower() not in page and t.replace("-", " ").lower() not in page}
    if not terms:
        pytest.skip("no case folder on this machine")
    code = Path(__file__).resolve().parent
    files = [
        *code.glob("*.py"),
        *code.glob("*.json"),
        *code.glob("*.md"),
        code / "static" / "index.html",
    ]
    for f in files:
        text = f.read_text(errors="replace").lower()
        hits = sorted(t for t in terms if t.lower() in text or t.replace("-", " ").lower() in text)
        assert not hits, (f.name, hits)


def test_versions_are_per_folder_and_formats_are_pairs(case):
    folder, _, _ = case
    for rel in ("README.md", "tools/README.md", "data/people.json", "data/people.md",
                "notes/2026-01-02-plan.md", "notes/2026-02-03-plan.md"):  # fmt: skip
        _write(folder / rel, rel)
    docs = F.documents(T0, {"folders": {}}, write=False)["folders"][0]["documents"]
    flags = {d["rel"]: " | ".join(f["text"] for f in d["flags"]) for d in docs}
    assert "README" not in flags["tools/README.md"]
    assert "another format: data/people.md" in flags["data/people.json"]
    assert "other version(s) present: notes/2026-02-03-plan.md" in flags["notes/2026-01-02-plan.md"]


def test_readme_folder_lines_and_phrase_kinds(case):
    folder, _, _ = case
    _write(
        folder / "README.md", "- `src/`: background papers\n- talk.md: two example conversations\n"
    )
    _write(folder / "src/deep/a.md", "x")
    _write(folder / "talk.md", "x")
    _, purposes, _ = F.readme_purposes(F.scan(folder))
    assert purposes["src/deep/a.md"] == ["(folder src/) - `src/`: background papers"]
    assert F.guess_kind("talk.md", None, purposes["talk.md"]) == "example conversations"
    assert (
        F.guess_kind("x.json", None, ["- `x/`: deploy a worker, with a one-endpoint example"])
        is None
    )


def test_only_a_team_record_with_the_current_sha_counts_as_reviewed(case):
    folder, _, tmp = case
    _write(folder / "a.md", "one")
    sha = F.hashlib.sha256(b"one").hexdigest()[:10]
    (tmp / "review.json").write_text(
        json.dumps(
            {"a.md": {"status": "read", "sha256": sha, "kind": "analysis", "purpose": "team words"}}
        )  # fmt: skip
    )
    (d,) = F.documents(T0, {"folders": {}}, write=False)["folders"][0]["documents"]
    assert d["review"]["status"] == "reviewed: read"
    assert d["purpose"]["kind_guess"] == "analysis" and d["purpose"]["basis"] == "team record"


def test_malformed_review_entries_never_break_the_view(case):
    folder, _, tmp = case
    _write(folder / "a.md", "one")
    _write(folder / "b.md", "two")
    (tmp / "review.json").write_text(json.dumps({"a.md": "ok", "b.md": {"contradictions": "x"}}))
    docs = F.documents(T0, {"folders": {}}, write=False)["folders"][0]["documents"]
    assert {d["rel"]: d["review"]["status"] for d in docs} == {
        "a.md": "not reviewed (team record 'ok' has no sha256)",
        "b.md": "not reviewed",
    }


def test_chat_lines_before_an_observed_arrival_do_not_count(case):
    folder, chat, _ = case
    _write(chat, "### YOU · 2033-05-18T03:00:00.000Z\nwaiting for late.md\n")
    _write(folder / "late.md", "x")
    arrival = F.D.parse_utc("2033-05-18T04:00:00Z")
    ledger = {"folders": {str(folder): {"first_watched": arrival - 3600, "files": {}}}}
    (d,) = F.documents(arrival, ledger, write=False)["folders"][0]["documents"]
    assert d["review"]["mentions"] == []


def test_unknown_builder_commit_is_unknown_not_same_code():
    v = F.builder_version("0000000deadbeef", "HEAD")
    assert v["known_to_git"] is False
    assert v["same_code_as_freeze"] is None and v["same_code_as_head"] is None


def test_final_tests_tolerate_string_launch_records():
    runs = [{"id": "x", "slot": None, "launch_record": "runs/x.meta.json",
             "start": "2026-10-11T18:00:00Z", "cases": [{"id": "PUB-01"}]}]  # fmt: skip
    assert F.final_tests(runs, []) == []


def test_scenario_results_are_read_as_final_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(F.D, "RUNS", tmp_path)
    (tmp_path / "s.json").write_text(json.dumps({
        "agent_id": "ag_1", "simulation_id": "sim", "started": "2026-10-11T18:30:00Z",
        "rows": [{"id": "C1", "pass": True}, {"id": "C2", "pass": False}]}))  # fmt: skip
    monkeypatch.setattr(F.D, "rel", lambda p: str(p))
    (r,) = F.scenario_results()
    assert (r["strict_passed"], r["total"], r["agent_id"]) == (1, 2, "ag_1")
    build = {"file": "traces/final.log", "created": {"agent_id": "ag_1", "ts": 0.0},
             "builder": {"commit": "abc"}, "snapshot": {"id": "s1"}}  # fmt: skip
    (t,) = F.final_tests([r], [build])
    assert t["build"] == "traces/final.log" and t["strict"] == "1/2" and not t["all_passed"]
