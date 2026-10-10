"""Local checks on a workflow before it is sent to Freya.

Each rule comes from kit/docs/workflow-format.md and kit/docs/tools-and-code.md ("Checklist").
The platform silently strips misplaced fields, so these catch mistakes the dry run would not.
Returns a list of problems; empty means valid.
"""

from typing import Any

ACTION_TYPES = {"api_request", "code"}
OPEN, CLOSE = "{" * 2, "}" * 2


def _nulls(value: Any, path: str) -> list[str]:
    if value is None:
        return [f"{path}: null value (schema rejects nulls)"]
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _nulls(v, f"{path}.{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _nulls(v, f"{path}[{i}]")]
    return []


def _is_always(t: dict) -> bool:
    return (t.get("condition") or {}).get("operator") == "always"


def _code_sources(node: dict) -> list[str]:
    out = []
    for action in node.get("pre_actions") or []:
        fn = action.get("function") or {}
        if fn.get("handler") == "__function__:code_exec":
            code = ((fn.get("parameters") or {}).get("properties") or {}).get("code") or {}
            out.append(str(code.get("default") or ""))
    return out


def validate(wf: dict) -> list[str]:
    problems = _nulls(wf, "workflow")
    nodes: dict = wf.get("nodes") or {}
    global_nodes: dict = wf.get("global_nodes") or {}
    if wf.get("initial_node") not in nodes:
        problems.append(f"initial_node {wf.get('initial_node')!r} is not a node")
    known = set(nodes) | set(global_nodes) | {"__previous__"}

    for key, node in {**nodes, **global_nodes}.items():
        where = f"node {key}"
        ntype = node.get("node_type")
        if node.get("name") != key:
            problems.append(f"{where}: name {node.get('name')!r} differs from its key")
        if node.get("tools") and ntype != "conversation":
            problems.append(f"{where}: tools only work on conversation nodes (would be stripped)")
        if node.get("pre_actions") and ntype not in ACTION_TYPES:
            problems.append(f"{where}: pre_actions only work on api_request/code nodes")
        for action in node.get("pre_actions") or []:
            if action.get("response_mapping"):
                problems.append(f"{where}: response_mapping inside pre_actions is ignored")
        transitions = node.get("transitions") or []
        for t in transitions:
            if t.get("target_node") not in known:
                problems.append(f"{where}: transition to unknown node {t.get('target_node')!r}")
            cond = t.get("condition") or {}
            if cond.get("logic") == "and":
                problems.append(f"{where}: top-level condition logic must be 'or'")
        if node.get("passthrough"):
            if not transitions or not _is_always(transitions[-1]):
                problems.append(f"{where}: passthrough node must end with an 'always' transition")
            if node.get("passthrough_default_transition") not in known:
                problems.append(f"{where}: passthrough_default_transition missing or unknown")
        if ntype == "end_call":
            if transitions:
                problems.append(f"{where}: end_call node must have no transitions")
            if not (node.get("terminal") or {}).get("function"):
                problems.append(f"{where}: end_call node needs a terminal function")
        for src in _code_sources(node):
            if OPEN in src or CLOSE in src:
                problems.append(f"{where}: code contains double curly braces")
            try:
                compile(src, f"<{key}>", "exec")
            except SyntaxError as e:
                problems.append(f"{where}: code does not compile: {e}")
        if node.get("max_node_turns") and not node.get("max_turn_transition"):
            if ntype == "conversation":
                problems.append(f"{where}: max_node_turns without max_turn_transition does nothing")

    problems += _unreachable_end(nodes)
    return problems


def _ends_call(node: dict) -> bool:
    """An end_call node, or a conversation node with an end_call tool (organiser base pattern)."""
    if node.get("node_type") == "end_call":
        return True
    handlers = {(t.get("function") or {}).get("handler") for t in node.get("tools") or []}
    return "__function__:end_call" in handlers


def _unreachable_end(nodes: dict) -> list[str]:
    """Every node must be able to end the call (kit: 'Every path must reach an end_call node')."""
    edges = {
        k: {t.get("target_node") for t in (n.get("transitions") or [])}
        | {n.get("max_turn_transition")}
        for k, n in nodes.items()
    }
    can_end = {k for k, n in nodes.items() if _ends_call(n)}
    changed = True
    while changed:
        changed = False
        for k, targets in edges.items():
            if k not in can_end and targets & can_end:
                can_end.add(k)
                changed = True
    return [
        f"node {k}: no path from here reaches an end_call node" for k in nodes if k not in can_end
    ]


def unsent_required(wf: dict, tools: list) -> list[str]:
    """Engine-run calls (fixed bodies, nobody fills a field later) that omit a field the tool API
    marks required (audit F57). A warning for the trace, not a validation problem."""
    by_url = {t.url: t for t in tools}
    out = []
    for name, node in (wf.get("nodes") or {}).items():
        for action in node.get("pre_actions") or []:
            params = (action.get("function") or {}).get("parameters", {}).get("properties", {})
            tool = by_url.get((params.get("url") or {}).get("default", ""))
            if not tool:
                continue
            sent = set((params.get("body") or {}).get("properties", {}))
            missing = sorted(f.name for f in tool.request if f.required and f.name not in sent)
            if missing:
                out.append(f"{name}: {tool.name} is sent without required field(s) {missing}")
    return sorted(set(out))
