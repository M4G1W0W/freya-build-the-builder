"""Unit tests for the agent-process matching in dashboard/claude_activity.py (synthetic ps rows).

uv run pytest dashboard/test_claude_activity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_activity as CA  # noqa: E402

A = "0ff87ea7-15f5-4256-b709-1c128c353294"  # the session we look for
B = "54d12450-d446-4d3a-862a-6541a5ece9bd"  # another session
APP = "/Applications/Claude.app/Contents/Helpers/disclaimer --pgroup -- "
AGENT = "/x/claude.app/Contents/MacOS/claude --output-format stream-json --verbose"
NOW = 1_000_000.0


def agent(pid: str, age: str, extra: str = "") -> list[list[str]]:
    """The app's launcher plus the real agent under it (both match the agent pattern)."""
    launcher = str(int(pid) - 1)
    return [[launcher, "1", age, APP + AGENT + extra], [pid, launcher, age, AGENT + extra]]


def shell(pid: str, parent: str, text: str) -> list[str]:
    return [pid, parent, "00:05", f"/bin/zsh -c source snap.sh && {text}"]


def test_resume_argument_names_the_transcript():
    rows = agent("31", "20:00", f" --resume={A}") + agent("41", "20:00")
    assert CA.match_agent(rows, A, None, NOW) == ("31", "its command line resumes this transcript")


def test_shells_count_by_exported_owner_not_by_mention():
    rows = (
        agent("11", "1:00:00")
        + agent("21", "1:00:00")
        # session B's shells mention A (e.g. grepping A's transcript): never A's
        + [shell(f"5{i}", "11", f"export CODEX_COMPANION_SESSION_ID='{B}' && grep {A} x") for i in range(3)]
        + [shell("61", "21", f"export CODEX_COMPANION_SESSION_ID='{A}' && ls")]
    )  # fmt: skip
    pid, note = CA.match_agent(rows, A, None, NOW)
    assert pid == "21" and "1 shell" in note


def test_start_time_match_when_no_shell_is_open():
    rows = agent("81", "1:27:03") + agent("91", "12:16:41")
    start = NOW - (1 * 3600 + 27 * 60 + 3) + 1.2  # transcript began 1.2 s after the process
    pid, note = CA.match_agent(rows, A, start, NOW)
    assert pid == "81" and "start-time match" in note  # the launcher (80) is never picked


def test_start_time_skips_agents_that_serve_another_session():
    rows = (
        agent("81", "10:00", f" --resume={B}")
        + agent("91", "10:00")
        + [shell("95", "91", f"export CODEX_COMPANION_SESSION_ID='{B}' && ls")]
    )
    assert CA.match_agent(rows, A, NOW - 600, NOW)[0] is None


def test_two_agents_started_together_are_ambiguous():
    rows = agent("81", "10:00") + agent("91", "10:02")
    pid, note = CA.match_agent(rows, A, NOW - 601, NOW)
    assert pid is None and note.startswith("ambiguous")


def test_no_evidence_is_reported_as_not_identifiable():
    rows = agent("81", "2:00:00")
    pid, note = CA.match_agent(rows, A, NOW - 60, NOW)
    assert pid is None and note.startswith("not identifiable")


def test_etime_parsing():
    assert CA.etime_s("05") is None
    assert CA.etime_s("01:02") == 62
    assert CA.etime_s("1:00:00") == 3600
    assert CA.etime_s("2-03:04:05") == 2 * 86400 + 3 * 3600 + 4 * 60 + 5


def test_mention_only_shell_never_outranks_a_start_time_match():
    # verification finding: without the export, B's shell grepping A's id once won over A's own agent
    rows = agent("81", "10:00") + agent("91", "30:00") + [shell("95", "91", f"grep {A} x.jsonl")]
    pid, note = CA.match_agent(rows, A, NOW - 600, NOW)
    assert pid == "81" and "start-time match" in note


def test_mention_only_shell_is_a_labelled_last_resort():
    rows = agent("81", "2:00:00") + [shell("85", "81", f"cat ~/.claude/projects/p/{A}.jsonl")]
    pid, note = CA.match_agent(rows, A, NOW - 60, NOW)
    assert pid == "81" and note.startswith("weak:")


def test_two_agents_resuming_the_same_transcript_are_reported_as_such():
    rows = agent("31", "20:00", f" --resume={A}") + agent("41", "20:00", f" --resume={A}")
    pid, note = CA.match_agent(rows, A, None, NOW)
    assert pid is None and "resume this transcript" in note
