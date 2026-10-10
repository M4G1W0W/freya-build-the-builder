"""Passive, read-only monitor of the Claude Desktop (Code tab) session working on this repo.

Where the data lives (verified on this Mac, Claude Code 2.1.286 inside Claude Desktop):
- Desktop session metadata: ~/Library/Application Support/Claude/claude-code-sessions/<a>/<b>/local_<id>.json
  (title, cwd, model, completedTurns, lastActivityAt, cliSessionId). `local_` = a session run on this machine.
- Transcript: ~/.claude/projects/<repo slug>/<cliSessionId>.jsonl, entries tagged entrypoint=claude-desktop.
- The session's agent is a local `claude --output-format stream-json` process started by the desktop app.
Cloud sessions keep no local data and are not visible to this monitor.

Only files are read (opened read-only); nothing is written, no process is signalled, no message is sent.

Activity feed (sanitised: secrets redacted, e-mails masked, home path and project slug hidden, truncated):
session title and metadata, tool names, Claude's one-line action descriptions (Bash/Monitor/Agent descriptions,
chapter titles, repo-relative file paths, workflow names), outcomes, error KIND from a fixed vocabulary, hook
error counts, open background tasks, background script basenames, Claude's latest text.
Never in the activity feed: user messages, thinking, tool inputs/commands, tool output, attachments.
The separate conversation view (conversation()) adds the user's prompts and Claude's full replies.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

import data as D

HOME = str(Path.home())
APP_SESSIONS = Path(HOME) / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
PROJECTS = Path(HOME) / ".claude" / "projects"
TAIL_BYTES = 4_000_000
RECENT = 25
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
WRAPPER = re.compile(r"^\S*(ba|z)?sh\s+-l?c\b")
AGENT = re.compile(r"/claude(\.app/Contents/MacOS/claude)?\s+--output-format stream-json")
SCRIPT_ARG = re.compile(r"^[^=\s]+\.(sh|py|js|ts|out|log|txt|json)$")
KNOWN_ERRORS = (
    "String to replace not found",
    "File has not been read",
    "File does not exist",
    "InputValidationError",
    "Blocked",
    "timed out",
    "No such file",
    "Permission denied",
    "not found",
)
TERMINAL = re.compile(r"<status>\s*(completed|failed|killed|stopped|error|cancelled)\s*</status>")

_tail_cache: dict[str, tuple[float, int, list[dict]]] = {}
_last_good_meta: dict[str, dict] = {}
_chosen: dict[str, str | None] = {"id": None}


def clean(text: object, limit: int = 240) -> str:
    s = ANSI.sub("", str(text or ""))
    s = D.redact(s).replace(HOME, "~")
    s = EMAIL.sub("[email]", s)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def error_kind(first: str) -> str:
    """A fixed vocabulary only: error text can echo commands, paths or content, which is never shown."""
    first = ANSI.sub("", first or "").strip()
    m = re.match(r"(Exit code \d+)", first)
    if m:
        return m.group(1)
    m = re.search(r"MCP error (-?\d+)", first)
    if m:
        return f"MCP error {m.group(1)}"
    known = next((k for k in KNOWN_ERRORS if k.lower() in first.lower()[:300]), None)
    if first.startswith("<tool_use_error>"):
        return "tool_use_error: " + (known or "details hidden")
    return known or "error (details hidden)"


def iso_ms(ms: object) -> str | None:
    return D.iso(ms / 1000) if isinstance(ms, (int, float)) and ms > 0 else None


def short_transcript(cli: str | None) -> str | None:
    return f"~/.claude/projects/<project>/{cli}.jsonl" if cli else None


# ---------------------------------------------------------------- desktop metadata


def desktop_sessions() -> list[dict]:
    """Desktop Code-tab sessions whose working folder is this repo (metadata only)."""
    out = []
    for path in glob.glob(str(APP_SESSIONS / "*" / "*" / "local_*.json")):
        stale = False
        try:
            meta = json.loads(Path(path).read_text())
            _last_good_meta[path] = meta
        except (OSError, ValueError):
            if path not in _last_good_meta:
                continue
            meta, stale = _last_good_meta[path], True  # mid-write: keep the last good copy
        if str(D.ROOT) not in (meta.get("cwd"), meta.get("originCwd")):
            continue
        cli = meta.get("cliSessionId")
        transcript = (
            next(iter(glob.glob(str(PROJECTS / "*" / f"{cli}.jsonl"))), None) if cli else None
        )
        out.append(
            {
                "desktop_session_id": meta.get("sessionId"),
                "cli_session_id": cli,
                "title": clean(meta.get("title"), 120),
                "title_source": meta.get("titleSource"),
                "model": meta.get("model"),
                "effort": meta.get("effort"),
                "permission_mode": meta.get("permissionMode"),
                "archived": bool(meta.get("isArchived")),
                "completed_turns": meta.get("completedTurns"),
                "created": iso_ms(meta.get("createdAt")),
                "last_activity": iso_ms(meta.get("lastActivityAt")),
                "last_activity_ms": meta.get("lastActivityAt") or 0,
                "metadata_stale": stale,
                "transcript": short_transcript(cli) if transcript else None,
                "_transcript_path": transcript,
            }
        )
    return sorted(out, key=lambda s: -s["last_activity_ms"])


def pick_primary(sessions: list[dict], wanted: str | None) -> tuple[dict | None, str]:
    """Explicit choice (?session= or DASHBOARD_SESSION) wins; otherwise a sticky choice.

    The first pick is the non-archived session with the most completed turns; it is remembered so a
    briefly unreadable or quiet session never silently switches the feed to another one.
    """
    wanted = wanted or os.environ.get("DASHBOARD_SESSION")
    by_id = {s["desktop_session_id"]: s for s in sessions}
    if wanted:
        hit = next(
            (s for s in sessions if wanted in (s["desktop_session_id"], s["cli_session_id"])), None
        )
        return (
            (hit, "explicit")
            if hit
            else (None, f"requested session {wanted} not found for this repo")
        )
    chosen = by_id.get(_chosen["id"]) if _chosen["id"] else None
    if chosen:
        if chosen["archived"]:
            return None, f"the monitored session {chosen['desktop_session_id']} was archived"
        if not chosen["_transcript_path"]:
            return None, f"the transcript of {chosen['desktop_session_id']} is not on this Mac"
        return chosen, "sticky (first pick: most completed turns)"
    if _chosen["id"]:
        return None, f"the monitored session {_chosen['id']} is no longer listed"
    live = [s for s in sessions if not s["archived"] and s["_transcript_path"]]
    if not live:
        return None, "no readable desktop session for this repo"
    pick = max(live, key=lambda s: (s["completed_turns"] or 0, s["last_activity_ms"]))
    _chosen["id"] = pick["desktop_session_id"]
    return pick, "first pick: the non-archived session with the most completed turns (now sticky)"


def public(s: dict) -> dict:
    return {k: v for k, v in s.items() if not k.startswith("_") and k != "last_activity_ms"}


# ---------------------------------------------------------------- transcript (tail only)


def read_tail(path: str) -> list[dict]:
    st = os.stat(path)
    hit = _tail_cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    with open(path, "rb") as f:  # read-only
        if st.st_size > TAIL_BYTES:
            f.seek(st.st_size - TAIL_BYTES)
            f.readline()  # drop the partial first line
        raw = f.read().decode("utf-8", errors="replace")
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue  # the line being written right now
    _tail_cache.clear()
    _tail_cache[path] = (st.st_mtime, st.st_size, events)
    return events


def action_summary(name: str, inp: dict) -> str:
    """An allowlist of fields that hold Claude's own short description, never content."""
    if not isinstance(inp, dict):
        return ""
    if name in ("Bash", "Monitor", "Agent", "Task", "PowerShell") and isinstance(
        inp.get("description"), str
    ):
        return clean(inp["description"], 160)
    if name.endswith(("mark_chapter", "spawn_task")) and isinstance(inp.get("title"), str):
        return clean(inp["title"], 120)
    if name in ("Read", "Edit", "Write", "NotebookEdit") and inp.get("file_path"):
        p = str(inp["file_path"])
        return (
            clean(p[len(str(D.ROOT)) + 1 :], 160)
            if p.startswith(str(D.ROOT) + "/")
            else "(file outside the repo)"
        )
    if name == "Workflow":
        m = re.search(
            r"export\s+const\s+meta\s*=\s*\{.*?\bname\s*:\s*['\"]([\w .:-]{1,60})['\"]",
            str(inp.get("script", "")),
            re.S,
        )
        return clean(m.group(1) if m else inp.get("name") or "workflow", 80)
    return {
        "AskUserQuestion": "asked the user a question (content not shown)",
        "ToolSearch": "loaded tool definitions",
        "TaskStop": "stopped a background task",
    }.get(name, "")


def _result_text(body: object) -> str:
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        return " ".join(x.get("text", "") for x in body if isinstance(x, dict))
    return ""


def parse(events: list[dict]) -> dict:
    tools: dict[str, dict] = {}
    order: list[str] = []
    texts: list[dict] = []
    hook_errors: list[dict] = []
    chapters: list[dict] = []
    todos: list[dict] = []
    open_tasks: dict[str, dict] = {}
    title = None
    last_ts = None
    entrypoints: set[str] = set()
    for e in events:
        if e.get("isSidechain"):
            continue
        ts = e.get("timestamp") or last_ts
        last_ts = ts or last_ts
        if e.get("entrypoint"):
            entrypoints.add(str(e["entrypoint"]))
        kind = e.get("type")
        if kind == "custom-title":
            title = clean(e.get("customTitle"), 120)
        if kind == "system" and e.get("hookErrors"):
            n = len(e["hookErrors"]) if isinstance(e["hookErrors"], list) else 1
            hook_errors.append({"at": ts, "count": n, "error": "hook error (details hidden)"})
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        raw = msg.get("content")
        content = raw if isinstance(raw, list) else []
        notice = raw if kind == "user" and isinstance(raw, str) else None
        att = e.get("attachment") if isinstance(e.get("attachment"), dict) else {}
        if kind == "attachment" and att.get("type") == "queued_command":
            notice = att.get("prompt")
        if isinstance(notice, str) and "<task-notification>" in notice:
            tid = re.search(r"<task-id>\s*([\w-]+)\s*</task-id>", notice)
            if tid and TERMINAL.search(notice):
                open_tasks.pop(tid.group(1), None)
        if kind == "assistant":
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    name, inp = b.get("name") or "?", b.get("input") or {}
                    tools[b.get("id")] = {
                        "at": ts,
                        "tool": name,
                        "action": action_summary(name, inp),
                        "outcome": "pending",
                        "error": None,
                    }
                    order.append(b.get("id"))
                    if name == "TaskStop":
                        for key in ("task_id", "shell_id", "taskId"):
                            open_tasks.pop(str(inp.get(key)), None)
                    if name.endswith("mark_chapter"):
                        chapters.append({"at": ts, "title": clean(inp.get("title"), 80)})
                    if name == "TodoWrite" and isinstance(inp.get("todos"), list):
                        todos = [
                            {
                                "status": t.get("status"),
                                "task": clean(t.get("activeForm") or t.get("content"), 120),
                            }
                            for t in inp["todos"]
                            if isinstance(t, dict)
                        ]
                elif b.get("type") == "text" and str(b.get("text", "")).strip():
                    texts.append({"at": ts, "text": clean(b["text"], 900)})
        elif kind == "user":
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                t = tools.get(b.get("tool_use_id"))
                if not t:
                    continue
                first = (_result_text(b.get("content")).strip().splitlines() or [""])[0]
                result = e.get("toolUseResult") if isinstance(e.get("toolUseResult"), dict) else {}
                if b.get("is_error"):
                    declined = re.search(
                        r"doesn't want to proceed|rejected|denied by the user", first, re.I
                    )
                    t["outcome"] = "declined" if declined else "error"
                    t["error"] = (
                        "declined by the user or the permission system"
                        if declined
                        else error_kind(first)
                    )
                elif result.get("interrupted"):
                    t["outcome"] = "interrupted"
                else:
                    task_id = result.get("backgroundTaskId") or result.get("taskId")
                    t["outcome"] = "background started" if task_id else "ok"
                    if task_id:
                        open_tasks[str(task_id)] = {
                            "id": str(task_id),
                            "tool": t["tool"],
                            "action": t["action"],
                            "since": ts,
                            "timeout_ms": None
                            if result.get("persistent")
                            else result.get("timeoutMs"),
                        }
                t["done_at"] = ts
    recent = [tools[i] for i in order[-RECENT:]][::-1]
    errors = [
        {k: t[k] for k in ("at", "tool", "action", "outcome", "error")}
        for t in (tools[i] for i in order)
        if t["outcome"] in ("error", "declined")
    ][-10:][::-1]
    counts: dict[str, int] = {}
    for i in order[-100:]:
        counts[tools[i]["outcome"]] = counts.get(tools[i]["outcome"], 0) + 1
    return {
        "title": title,
        "recent_actions": recent,
        "errors": errors,
        "hook_errors": hook_errors[-5:][::-1],
        "latest_conclusions": texts[-3:][::-1],
        "chapters": chapters[-5:][::-1],
        "todos": todos,
        "open_tasks": list(open_tasks.values()),
        "outcome_counts_last_100": counts,
        "last_event_at": last_ts,
        "entrypoints": sorted(entrypoints),
        "pending_tool": next((t for t in recent if t["outcome"] == "pending"), None),
    }


# ---------------------------------------------------------------- processes (names only)


def _label(cmd: str) -> str:
    """Interpreter plus script basename; inline code (-c) and anything else is never shown."""
    parts = cmd.split()
    exe = Path(parts[0]).name if parts else "?"
    if exe == "tail":
        last = parts[-1] if len(parts) > 1 else ""
        return f"tail {Path(last).name}" if SCRIPT_ARG.match(Path(last).name) else "tail"
    if "-c" in parts[1:3]:
        return f"{exe} (inline command)"
    script = next((Path(a).name for a in parts[1:] if SCRIPT_ARG.match(Path(a).name)), None)
    return clean(f"{exe} {script}" if script else f"{exe} (command hidden)", 80)


def session_processes(cli_id: str) -> dict:
    try:
        out = subprocess.run(
            ["ps", "-Ao", "pid,ppid,etime,command"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {"agent_process": None, "agent_note": "ps unavailable", "background_scripts": []}
    rows = [p for p in (ln.strip().split(None, 3) for ln in out.splitlines()[1:]) if len(p) == 4]
    children: dict[str, list] = {}
    for pid, ppid, etime, cmd in rows:
        children.setdefault(ppid, []).append((pid, etime, cmd))
    agents = [pid for pid, _, _, cmd in rows if AGENT.search(cmd)]
    # an agent is linked by its wrapper shells (the Bash tool's `zsh -c`), whose argv carries the session id
    score = {
        a: sum(1 for _, _, c in children.get(a, []) if WRAPPER.match(c) and cli_id in c)
        for a in agents
    }
    linked = sorted((a for a in agents if score[a]), key=lambda a: -score[a])
    agent, note = None, "not identifiable right now (no Bash shells of this session are open)"
    if len(linked) == 1 or (len(linked) > 1 and score[linked[0]] > score[linked[1]]):
        agent, note = linked[0], f"parent of {score[linked[0]]} shell(s) of this session"
    elif len(linked) > 1:
        note = f"ambiguous: {len(linked)} agent processes have shells mentioning this session"
    scripts = []
    if agent:
        stack = [p for p, _, c in children.get(agent, []) if WRAPPER.match(c) and cli_id in c]
        seen = set()
        while stack:
            p = stack.pop()
            for cpid, etime, cmd in children.get(p, []):
                if cpid in seen:
                    continue
                seen.add(cpid)
                stack.append(cpid)
                if not WRAPPER.match(cmd):
                    scripts.append({"pid": cpid, "elapsed": etime, "what": _label(cmd)})
    return {
        "agent_process": {"pid": agent, "evidence": note} if agent else None,
        "agent_note": note,
        "background_scripts": scripts,
    }


# ---------------------------------------------------------------- feed


def activity(wanted: str | None = None) -> dict:
    now = time.time()
    if not APP_SESSIONS.exists():
        return {
            "available": False,
            "reason": "Claude Desktop session metadata folder not found on this Mac",
        }
    sessions = desktop_sessions()
    primary, how_picked = pick_primary(sessions, wanted)
    base = {
        "available": bool(primary),
        "generated_at": D.iso(now),
        "how": "read-only: desktop metadata (claude-code-sessions/local_*.json) + the session's local transcript tail + ps",
        "exposed": "session titles, tool names, Claude's action descriptions (Bash/Monitor/Agent descriptions, chapter titles, repo-relative paths, workflow names), outcomes, error kinds, open background tasks, script basenames, Claude's latest text (truncated, redacted)",
        "never_exposed": "user messages, thinking, tool inputs/commands, tool output, attachments (the conversation view adds prompts and replies)",
        "cloud_sessions": "not visible: they keep no data on this Mac",
        "sessions_for_this_repo": [public(s) for s in sessions],
        "selection": how_picked,
    }
    if not primary:
        return {**base, "reason": how_picked}
    path = primary["_transcript_path"]
    parsed = parse(read_tail(path))
    age = now - os.stat(path).st_mtime
    procs = session_processes(primary["cli_session_id"])
    pending = parsed["pending_tool"]
    open_tasks = [  # a Monitor with a timeout has ended once the timeout ran out
        o
        for o in parsed["open_tasks"]
        if not (
            o.get("timeout_ms")
            and o.get("since")
            and D.parse_utc(o["since"][:19] + "Z") + o["timeout_ms"] / 1000 < now
        )
    ]
    if pending:
        state = (
            f"tool call without a result for {int(age // 60)} min: {pending['tool']}"
            + (f" ({pending['action']})" if pending["action"] else "")
            + (" (possibly waiting on a permission prompt or interrupted)" if age > 300 else "")
        )
    elif age < 120:
        state = "active (transcript written in the last 2 min)"
    elif procs["background_scripts"]:
        state = f"turn finished {int(age // 60)} min ago; background processes still running"
    else:
        state = (
            f"idle for {int(age // 60)} min (turn finished; waiting for the user or a notification)"
        )
    helpers = ("tail", "sleep", "ugrep", "grep")  # Monitor plumbing, not work
    n_bg = len([b for b in procs["background_scripts"] if not b["what"].startswith(helpers)])
    if n_bg:
        state += f"; {n_bg} background process(es) running"
    local = "claude-desktop" in parsed["entrypoints"]
    runs = (
        "local (desktop metadata, transcript written by claude-desktop, live agent process)"
        if local and procs["agent_process"]
        else "local transcript; agent process not identified right now"
        if local
        else "unknown (no claude-desktop entries in the transcript tail)"
    )
    sel = public(primary)
    sel["runs"] = runs
    return {
        **base,
        "session": sel,
        "state": state,
        "transcript_last_write": D.iso(os.stat(path).st_mtime),
        "seconds_since_last_write": int(age),
        "current_task": {
            "session_title": parsed["title"] or sel["title"],
            "latest_chapter": parsed["chapters"][0] if parsed["chapters"] else None,
            "todos_in_progress": [t for t in parsed["todos"] if t["status"] == "in_progress"],
            "note": "derived from the session title, chapter titles and todo items Claude set",
        },
        "processes": procs,
        "open_tasks": open_tasks,
        "open_tasks_note": "launched in the transcript with no completion recorded there; many end silently, "
        "so only the live processes are proof that work is running",
        **{
            k: parsed[k]
            for k in (
                "recent_actions",
                "errors",
                "hook_errors",
                "latest_conclusions",
                "chapters",
                "outcome_counts_last_100",
            )
        },
    }


def summary(feed: dict) -> dict:
    """The small, content-free part that goes into reports/latest_snapshot.*"""
    if not feed.get("available"):
        return {"available": False, "reason": feed.get("reason")}
    s = feed["session"]
    return {
        "available": True,
        "title": feed["current_task"]["session_title"],
        "state": feed["state"],
        "desktop_session_id": s["desktop_session_id"],
        "runs": s["runs"],
        "completed_turns": s["completed_turns"],
        "last_write": feed["transcript_last_write"],
        "recent_errors": len(feed["errors"]),
        "tasks_without_recorded_completion": len(feed["open_tasks"]),
        "background_processes": [b["what"] for b in feed["processes"]["background_scripts"]],
    }


# ---------------------------------------------------------------- conversation (prompts and replies)

REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
PASTE_TAG = re.compile(r"</?pasted_content[^>]*>")
COMMAND = re.compile(
    r"^\s*(?:<command-message>.*?</command-message>\s*)?<command-name>\s*/?([^<\s]+)\s*</command-name>"
    r"(?:\s*<command-args>(.*?)</command-args>)?",
    re.S,
)
NOTIFY = re.compile(r"<summary>(.*?)</summary>", re.S)
NOT_HUMAN = re.compile(
    r"\s*(<task-notification>|\[Request interrupted|<local-command-std(out|err)>|<bash-std(out|err)>)"
)
MSG_LIMIT = 8000


def _clean_message(text: str) -> str:
    s = REMINDER.sub("", text)
    s = PASTE_TAG.sub("", s)
    s = ANSI.sub("", s)
    s = D.redact(s).replace(HOME, "~")
    s = EMAIL.sub("[email]", s).strip()
    return (
        s
        if len(s) <= MSG_LIMIT
        else s[:MSG_LIMIT] + f"\n… [truncated, {len(s) - MSG_LIMIT} more characters]"
    )


def _human_text(e: dict) -> str | None:
    """What the person typed, or None for notifications, meta entries and tool results."""
    if e.get("isMeta") or e.get("isSidechain"):
        return None
    origin = e.get("origin") if isinstance(e.get("origin"), dict) else {}
    content = (e.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    if not isinstance(content, str) or not content.strip():
        return None
    if origin:
        if origin.get("kind") != "human":
            return None
    elif e.get("promptSource") == "system" or NOT_HUMAN.match(content):
        return (
            None  # older transcripts carry no origin field: drop harness markers and command output
        )
    cmd = COMMAND.match(
        content
    )  # a slash command is the whole message, never a tag inside a prompt
    if cmd:
        return f"/{cmd.group(1)} {(cmd.group(2) or '').strip()}".strip()
    return content


def _items(events: list[dict]) -> list[dict]:
    items: list[dict] = []
    for e in events:
        if e.get("isSidechain"):
            continue
        ts = e.get("timestamp")
        kind = e.get("type")
        if kind == "user":
            text = _human_text(e)
            if text:
                items.append({"at": ts, "role": "you", "text": _clean_message(text)})
            else:
                content = (e.get("message") or {}).get("content")
                if isinstance(content, str) and "<task-notification>" in content:
                    m = NOTIFY.search(content)
                    note = m.group(1) if m else "background task notification"
                    items.append({"at": ts, "role": "event", "text": clean(note, 200)})
        elif kind == "attachment":
            a = e.get("attachment") if isinstance(e.get("attachment"), dict) else {}
            origin = a.get("origin") if isinstance(a.get("origin"), dict) else {}
            if (
                a.get("type") == "queued_command"
                and origin.get("kind") == "human"
                and isinstance(a.get("prompt"), str)
            ):
                items.append(
                    {"at": ts, "role": "you", "text": _clean_message(a["prompt"]), "queued": True}
                )
        elif kind == "assistant":
            content = (e.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if (
                    isinstance(b, dict)
                    and b.get("type") == "text"
                    and str(b.get("text", "")).strip()
                ):
                    items.append({"at": ts, "role": "claude", "text": _clean_message(b["text"])})
    return items


def _dedupe(items: list[dict]) -> list[dict]:
    """Drop only the user entry that repeats a queued prompt; identical prompts typed twice both stay."""
    out: list[dict] = []
    for it in items:
        prev_you = next((d for d in reversed(out) if d["role"] == "you"), None)
        if (
            it["role"] == "you"
            and not it.get("queued")
            and prev_you
            and prev_you.get("queued")
            and prev_you["text"] == it["text"]
            and not prev_you.get("_paired")
        ):
            prev_you["_paired"] = True
            continue
        out.append(it)
    return [{k: v for k, v in i.items() if k != "_paired"} for i in out]


def _human_events(path: str) -> list[dict]:
    """Only the human-prompt entries of the whole transcript (cheap: filtered before JSON parsing)."""
    events = []
    with open(path, "rb") as f:  # read-only
        for line in f:
            if b'"human"' not in line and b"queued_command" not in line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return [e for e in events if e.get("type") in ("user", "attachment")]


def _keep_prompts(items: list[dict], limit: int) -> list[dict]:
    """The last `limit` items, plus every prompt of yours before them (prompts are never cut)."""
    if len(items) <= limit:
        return items
    cut = len(items) - limit
    return [i for i in items[:cut] if i["role"] == "you"] + items[cut:]


def conversation(wanted: str | None = None, limit: int = 80) -> dict:
    sessions = desktop_sessions() if APP_SESSIONS.exists() else []
    primary, how_picked = pick_primary(sessions, wanted)
    if not primary:
        return {"available": False, "reason": how_picked}
    path = primary["_transcript_path"]
    tail_only = os.stat(path).st_size > TAIL_BYTES
    items = _dedupe(_items(read_tail(path)))
    if tail_only:  # prompts are few: take them from the whole file so none is ever lost
        first = items[0]["at"] if items else None
        early = [
            i
            for i in _dedupe(_items(_human_events(path)))
            if first is None or (i["at"] or "") < first
        ]
        items = early + items
    deduped = _keep_prompts(items, limit)
    return {
        "available": True,
        "session": public(primary),
        "selection": how_picked,
        "generated_at": D.iso(time.time()),
        "items": deduped,
        "total_items": len(items),
        "prompts": sum(1 for i in items if i["role"] == "you"),
        "note": "Your prompts and Claude's replies, for review (also written to reports/latest_conversation.*); "
        "system reminders, thinking, tool calls and tool output are left out; secrets redacted, e-mails masked. "
        "Only the current transcript of the session is read: prompts from before a context save live in older "
        "transcripts."
        + (
            " Claude's replies and events come from the last 4 MB of the transcript; all your prompts are read from the whole file."
            if tail_only
            else ""
        ),
    }


def conversation_markdown(c: dict) -> str:
    if not c.get("available"):
        return f"# Claude session conversation\n\nNot available: {c.get('reason')}\n"
    s = c["session"]
    lines = [
        f"# Claude session conversation ({c['generated_at']})",
        "",
        f"Session: **{s['title']}** ({s['desktop_session_id']}, {s['model']}, {s['completed_turns']} turns)",
        "",
        c["note"],
        "",
        f"Showing {len(c['items'])} of {c['total_items']} items; all {c['prompts']} of your prompts are kept. "
        "Roles: YOU = the human engineer, "
        "CLAUDE = the agent, EVENT = a background-task notification.",
        "",
    ]
    for it in c["items"]:
        if it["role"] == "event":
            lines.append(f"- `{it['at']}` EVENT: {it['text']}")
            continue
        who = "YOU" if it["role"] == "you" else "CLAUDE"
        queued = " (queued while Claude was busy)" if it.get("queued") else ""
        lines += ["", f"### {who} · {it['at']}{queued}", "", it["text"], ""]
    return "\n".join(lines) + "\n"
