"""Builders for workflow JSON pieces, in the shapes documented in kit/docs/workflow-format.md and
verified on the platform (experiments/exp01_mechanics.py). No brief or tool knowledge here."""

from typing import Any


def always(target: str) -> dict:
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def when_equals(target: str, description: str, variable: str, values: list[str]) -> dict:
    """Deterministic transition: OR over `variable == value` (strings; booleans need both spellings)."""
    return {
        "target_node": target,
        "description": description,
        "condition": {
            "logic": "or",
            "conditions": [
                {"variable": variable, "operator": "equals", "operand": v} for v in values
            ],
        },
    }


def when_true(target: str, description: str, variable: str) -> dict:
    return when_equals(target, description, variable, ["true", "True"])


def when_greater(target: str, description: str, variable: str, operand: float) -> dict:
    return {
        "target_node": target,
        "description": description,
        "condition": {
            "logic": "or",
            "conditions": [{"variable": variable, "operator": "greater_than", "operand": operand}],
        },
    }


def tool_transition(target: str, description: str) -> dict:
    """The dialogue model fires it as a tool named transition_to_<target> (verified for closing)."""
    return {
        "target_node": target,
        "description": description,
        "is_tool_call": True,
        "condition": {"operator": "matches_intent", "description": description},
    }


def conversation(
    name: str,
    task_message: str,
    transitions: list[dict],
    tools: list[dict] | None = None,
    on_enter: dict | None = None,
    first_entry_only: bool = False,
    extraction_schema: list[dict] | None = None,
    max_turns: int = 40,
    max_turn_target: str = "",
) -> dict:
    node: dict[str, Any] = {
        "name": name,
        "node_type": "conversation",
        "task_message": task_message,
        "transitions": transitions,
    }
    if max_turn_target:  # a cap without a target does nothing (kit: workflow-format.md, Limits)
        node["max_node_turns"] = max_turns
        node["max_turn_transition"] = max_turn_target
    if tools:
        node["tools"] = tools
    if on_enter:
        node["on_enter"] = on_enter
    if first_entry_only:
        node["on_enter_first_entry_only"] = True
    if extraction_schema:
        node["extraction_schema"] = extraction_schema
    return node


def _passthrough(name: str, node_type: str, actions: list[dict], transitions: list[dict]) -> dict:
    return {
        "name": name,
        "node_type": node_type,
        "passthrough": True,
        "passthrough_default_transition": transitions[-1]["target_node"],
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": actions,
        "transitions": transitions,
    }


def code_node(name: str, source: str, transitions: list[dict], timeout_ms: int = 10000) -> dict:
    """Passthrough code node; `transitions` must end with an always transition."""
    action = {
        "type": "function",
        "function": {
            "name": "code_exec",
            "handler": "__function__:code_exec",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "default": source},
                    "timeout_ms": {"type": "number", "default": timeout_ms},
                },
            },
        },
    }
    return _passthrough(name, "code", [action], transitions)


def api_node(name: str, calls: list[dict], transitions: list[dict]) -> dict:
    """Passthrough api_request node running engine calls; results land in <name>_response.*."""
    return _passthrough(name, "api_request", calls, transitions)


def end_node(name: str, ended_reason: str) -> dict:
    """Silent hang-up; `ended_reason` becomes the call's endedReason."""
    return {
        "name": name,
        "node_type": "end_call",
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "transitions": [],
        "terminal": {
            "type": "function",
            "function": {
                "name": ended_reason,
                "handler": "__function__:end_call",
                "parameters": {
                    "type": "object",
                    "properties": {"message_mode": {"type": "string", "default": "none"}},
                },
            },
        },
    }
