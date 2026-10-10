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
