import json
from pathlib import Path

import pytest

from freya_builder import cli, nodes

KIT = Path(__file__).resolve().parents[1] / "kit"
BRIEF = str(KIT / "briefs" / "brief-a.md")
API = str(KIT / "tools" / "openapi.json")


def fake_extract(trace, brief_text, tools):
    trace.model_call("fake-model", "extract policy", 0.0, None)
    return {"briefs_chars": len(brief_text), "tools": [t.name for t in tools]}


def fake_render(spec, tools):
    return {
        "initial_node": "talk",
        "nodes": {
            "talk": nodes.conversation("talk", "Hi.", [nodes.tool_transition("bye", "done")]),
            "bye": nodes.end_node("bye", "call_closed"),
        },
        "global_nodes": {},
    }


def test_dry_run_end_to_end(capsys):
    assert cli.run([BRIEF, API, "--dry"], fake_extract, fake_render) == 0
    out, err = capsys.readouterr()
    assert json.loads(out)["initial_node"] == "talk"
    for needle in ("START", "MODEL", "purpose=extract policy", "TEST", "END", "ok=True"):
        assert needle in err


def test_start_line_ties_the_trace_to_the_code_and_inputs(capsys, monkeypatch):
    # Review gap 10: the organisers' reviewer compares the trace with the submitted commit.
    monkeypatch.setattr(cli, "code_version", lambda: ("abc1234", True))
    cli.run([BRIEF, API, "--dry"], fake_extract, fake_render)
    err = capsys.readouterr().err
    start = next(line for line in err.splitlines() if " START " in line)
    for needle in ("git=abc1234", "dirty=True", "python=", "models=gpt-6.1-sol", "sha256="):
        assert needle in start
    assert "uncommitted changes" in err


def test_code_version_reads_this_checkout():
    commit, dirty = cli.code_version()
    assert commit != "unknown" and isinstance(dirty, bool)


def test_invalid_workflow_stops_before_platform(capsys):
    def broken(spec, tools):
        wf = fake_render(spec, tools)
        wf["initial_node"] = "ghost"
        return wf

    assert cli.run([BRIEF, API, "--dry"], fake_extract, broken) == 2
    assert "local workflow validation: FAIL" in capsys.readouterr().err


def test_needs_brief_and_tool_api():
    with pytest.raises(SystemExit):
        cli.parse_args([API])


def test_multiple_briefs_are_concatenated_in_order():
    text = cli.read_briefs([BRIEF, str(KIT / "briefs" / "brief-b.md")])
    assert text.index("brief-a.md") < text.index("brief-b.md")


def test_brief_in_cp1252_is_read(tmp_path):
    # audit F79: a pasted e-mail saved as cp1252 crashed the strict UTF-8 read.
    brief = tmp_path / "raw.md"
    brief.write_bytes("Kunde schuldet 420 € – bitte prüfen".encode("cp1252"))
    assert "420 € – bitte prüfen" in cli.read_briefs([str(brief)])


def test_a_failing_build_exits_1_with_a_redacted_traceback(capsys, monkeypatch):
    # audit F80: the re-raised traceback bypassed the trace's secret redaction.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET-abcdef")

    def boom(trace, brief_text, tools):
        raise RuntimeError("upstream said: key sk-test-SECRET-abcdef invalid")

    assert cli.run([BRIEF, API, "--dry"], boom, fake_render) == 1
    err = capsys.readouterr().err
    assert "ERROR" in err and "RuntimeError" in err and "Traceback" in err
    assert "sk-test-SECRET-abcdef" not in err


def test_a_failed_smoke_test_ends_not_ok_with_exit_3(capsys, monkeypatch):
    # Review gap 15: a failed self-test used to end with ok=True.
    monkeypatch.setattr(cli.platform, "dry_run", lambda trace, slot, wf: None)
    monkeypatch.setattr(
        cli.platform, "save", lambda trace, slot, wf: {"workflow_id": "w", "agent_id": "a"}
    )
    assert cli.run([BRIEF, API], fake_extract, fake_render, lambda *args: False) == 3
    err = capsys.readouterr().err
    assert "ok=False" in err
