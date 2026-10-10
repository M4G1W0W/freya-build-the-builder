import copy
import json
import sys
from pathlib import Path

from freya_builder.validate import validate

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "reference" / "workflows"
KIT = ROOT / "kit"


def end_node(name="bye"):
    return {
        "name": name,
        "node_type": "end_call",
        "transitions": [],
        "terminal": {
            "type": "function",
            "function": {"name": "x", "handler": "__function__:end_call"},
        },
    }


def good():
    return {
        "initial_node": "talk",
        "nodes": {
            "talk": {
                "name": "talk",
                "node_type": "conversation",
                "tools": [{"type": "function"}],
                "transitions": [
                    {"target_node": "calc", "description": "d", "condition": {"operator": "always"}}
                ],
            },
            "calc": {
                "name": "calc",
                "node_type": "code",
                "passthrough": True,
                "passthrough_default_transition": "bye",
                "pre_actions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "code_exec",
                            "handler": "__function__:code_exec",
                            "parameters": {
                                "properties": {"code": {"type": "string", "default": "x = 1\n"}}
                            },
                        },
                    }
                ],
                "transitions": [
                    {
                        "target_node": "bye",
                        "description": "always",
                        "condition": {"operator": "always"},
                    }
                ],
            },
            "bye": end_node(),
        },
        "global_nodes": {},
    }


def test_good_workflow_passes():
    assert validate(good()) == []


def test_kit_minimal_builder_output_passes():
    # What the kit's working example SENDS (stored copies carry platform-filled nulls).
    sys.path.insert(0, str(KIT))
    import examples.minimal_builder as mb

    wf = mb.build((KIT / "briefs" / "brief-a.md").read_text())
    problems = [p for p in validate(wf) if "max_node_turns" not in p]
    assert problems == []


def test_organiser_base_structure_passes():
    # Stored copy: ignore platform-filled nulls; the graph rules must hold.
    wf = json.loads((REF / "organiser_base_2node.json").read_text())["workflow"]
    problems = [p for p in validate(wf) if "null value" not in p and "max_node_turns" not in p]
    assert problems == []


def test_detects_each_mistake():
    cases = {
        "null value": lambda w: w["nodes"]["talk"].update(role_message=None),
        "tools only work": lambda w: w["nodes"]["calc"].update(tools=[{}]),
        "pre_actions only": lambda w: w["nodes"]["talk"].update(pre_actions=[{}]),
        "unknown node": lambda w: w["nodes"]["talk"]["transitions"].append(
            {"target_node": "nope", "condition": {"operator": "always"}}
        ),
        "end with an 'always'": lambda w: w["nodes"]["calc"].update(transitions=[]),
        "double curly": lambda w: w["nodes"]["calc"]["pre_actions"][0]["function"]["parameters"][
            "properties"
        ]["code"].update(default="x = {'a': {'b': 1}}"),
        "does not compile": lambda w: w["nodes"]["calc"]["pre_actions"][0]["function"][
            "parameters"
        ]["properties"]["code"].update(default="def ("),
        "reaches an end_call": lambda w: w["nodes"]["talk"].update(
            transitions=[{"target_node": "talk", "condition": {"operator": "always"}}]
        ),
        "initial_node": lambda w: w.update(initial_node="ghost"),
        "differs from its key": lambda w: w["nodes"]["talk"].update(name="other"),
    }
    for needle, mutate in cases.items():
        wf = copy.deepcopy(good())
        mutate(wf)
        problems = validate(wf)
        assert any(needle in p for p in problems), (needle, problems)
