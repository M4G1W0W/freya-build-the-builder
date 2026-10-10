"""Turn a Freya call's `messages` into readable lines (pure functions, no network).

Message shape (kit/docs/api.md, "Get a call with its transcript"): each entry has `role`,
`message`, `nodeId`, `secondsFromStart`. `system` messages carry a JSON event string.
"""

import json
from typing import Any

MAX = 300


def _short(value: Any, limit: int = MAX) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _tool_args(args: Any) -> Any:
    # api_call args are the full request (url, method, headers, body): the body is what matters.
    if isinstance(args, dict) and "body" in args:
        return args["body"]
    return args


def _tool_result(result: Any) -> Any:
    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result


def format_event(event: dict[str, Any], verbose: bool = False) -> str | None:
    kind = event.get("event")
    if kind == "node_enter":
        return f"   == enter {event.get('node')} (from {event.get('from_node')})"
    if kind == "function_call_start":
        return f"   -> {event.get('function')} {_short(_tool_args(event.get('args')))}"
    if kind == "function_call_complete":
        return f"   <- {event.get('function')} {_short(_tool_result(event.get('result')))}"
    if kind == "route_evaluated":
        if not (verbose or event.get("matched")):
            return None
        target = event.get("target") if event.get("matched") else "(stay)"
        reason = _short(event.get("reason"), 160)
        return f"   ~~ route {event.get('from_node')} -> {target}: {reason}"
    if kind == "error":
        return f"   !! error {event.get('message')} {_short(event.get('details'), 200)}"
    return f"   .. {kind} {_short(event, 200)}" if verbose else None


def format_messages(messages: list[dict[str, Any]], verbose: bool = False) -> list[str]:
    lines: list[str] = []
    for m in messages:
        role, text = m.get("role"), m.get("message") or ""
        t = m.get("secondsFromStart")
        stamp = f"[{t:6.1f}s]" if isinstance(t, (int, float)) else "[   -   ]"
        if role == "system":
            try:
                event = json.loads(text)
            except (TypeError, ValueError):
                if verbose:
                    lines.append(f"{stamp}    .. {_short(text, 200)}")
                continue
            line = format_event(event, verbose) if isinstance(event, dict) else None
            if line:
                lines.append(f"{stamp} {line}")
        elif role in ("assistant", "user"):
            who = "AGENT" if role == "assistant" else "CUST "
            lines.append(f"{stamp} {who}: {text}")
        elif verbose:
            lines.append(f"{stamp} {role}: {_short(text, 200)}")
    return lines
