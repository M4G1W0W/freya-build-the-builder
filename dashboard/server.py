"""Read-only testing dashboard: http://127.0.0.1:8765

    .venv/bin/python dashboard/server.py [--port 8765]

GET only. It reads local files and read-only git/ps output, never calls the network, and writes nothing
except reports/ (latest_snapshot.{json,md}, the conversation exports, and final_case_ledger.json: the
final case folder's document versions). Data is recomputed every 12 s in a background thread.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis as A  # noqa: E402
import claude_activity as CA  # noqa: E402
import compare as C  # noqa: E402
import data as D  # noqa: E402
import evidence as EV  # noqa: E402
import finalcase as FC  # noqa: E402
import rules as RC  # noqa: E402

HERE = Path(__file__).resolve().parent
REPORTS = D.ROOT / "reports"
REFRESH_S = 12
ALLOWED_HOSTS: set[str] = set()
_state: dict = {}
_health: dict = {"last_success": None, "last_error": None, "last_error_at": None}
_lock = threading.Lock()


def compute() -> dict:
    git = D.git_state()
    traces = D.all_traces()
    runs, incomplete = D.build_runs(traces, git["commits"])
    procs = D.running_tests()
    incomplete = A._mark_in_progress(
        incomplete, procs
    )  # a log a live run is writing is in progress
    state = {"runs": runs, "incomplete": incomplete}
    state["overview"] = A.overview(git, runs, incomplete, procs, D.working_state())
    state["panels"] = A.panels(runs)
    state["failures"] = A.failures(runs)
    state["builder"] = A.builder(traces, runs)
    try:
        state["comparison"] = C.build(
            runs, state["overview"]["incomplete_runs"], traces, git["commits"]
        )
    except Exception:  # the comparison view must never break the rest of the dashboard
        traceback.print_exc()
        state["comparison"] = None
    try:
        state["claude"] = CA.activity()
    except Exception as exc:  # the monitor must never break the testing dashboard
        state["claude"] = {"available": False, "reason": f"monitor error: {type(exc).__name__}"}
    try:
        state["final"] = FC.view(runs)
    except Exception as exc:  # the final-case view must never break the rest of the dashboard
        traceback.print_exc()
        state["final"] = {"error": f"final-case view error: {type(exc).__name__}: {exc}"}
    state["snapshot"] = A.snapshot(state)
    state["snapshot"]["claude_session"] = CA.summary(state["claude"])
    state["snapshot"]["final_case"] = FC.compact(state["final"])
    try:
        state["conversation"] = CA.conversation()  # every transcript, nothing cut
    except Exception as exc:
        state["conversation"] = {
            "available": False,
            "reason": f"monitor error: {type(exc).__name__}",
        }
    others_feed, others_convo = {}, {}  # every other non-archived chat of this repo
    primary = (state["claude"].get("session") or {}).get("desktop_session_id")
    try:
        sessions = CA.monitored()
    except Exception:
        traceback.print_exc()
        sessions = []
    for sess in sessions:
        sid = sess["desktop_session_id"]
        if sid == primary:
            continue
        try:
            others_feed[sid], others_convo[sid] = CA.activity(sid), CA.conversation(sid)
        except Exception as exc:
            others_feed[sid] = others_convo[sid] = {
                "available": False,
                "reason": f"monitor error: {type(exc).__name__}",
            }
    state["claude_others"], state["conversations_others"] = others_feed, others_convo
    state["claude_sessions"] = [
        _session_row(state["claude"], state["conversation"], primary, True)
    ] + [_session_row(others_feed[sid], others_convo[sid], sid, False) for sid in others_feed]
    state["snapshot"]["claude_sessions"] = state["claude_sessions"]
    state["snapshot"]["claude_conversation"] = (
        "reports/conversations_index.md lists every monitored chat; reports/latest_conversation.md "
        "is the primary chat, reports/latest_conversation_<id>.md each other chat (and .json): "
        "your prompts and Claude's replies"
    )
    state["refreshed"] = D.iso(time.time())
    return state


def _session_row(feed: dict, convo: dict, sid: str | None, primary: bool) -> dict:
    row = {**CA.summary(feed), "primary": primary}
    sid = row.get("desktop_session_id") or sid
    row["desktop_session_id"] = sid
    row["title"] = row.get("title") or (convo.get("session") or {}).get("title")
    row["prompts"] = convo.get("prompts")
    row["conversation_file"] = (
        f"reports/{CA.report_name(sid, primary)}.md" if sid and convo.get("available") else None
    )
    return row


def write_reports(
    snap: dict,
    convo: dict | None = None,
    others: dict[str, dict] | None = None,
    sessions: list[dict] | None = None,
) -> None:
    REPORTS.mkdir(exist_ok=True)
    files = [
        ("latest_snapshot.json", D.dumps(snap, indent=2)),
        (
            "latest_snapshot.md",
            A.snapshot_markdown(snap) + FC.summary_markdown(snap.get("final_case")),
        ),
    ]
    if convo is not None:
        files += [
            ("latest_conversation.json", D.dumps(convo, indent=2)),
            ("latest_conversation.md", D.redact(CA.conversation_markdown(convo))),
        ]
    for sid, c in (others or {}).items():
        if c.get("available"):
            stem = CA.report_name(sid, primary=False)
            files += [
                (f"{stem}.json", D.dumps(c, indent=2)),
                (f"{stem}.md", D.redact(CA.conversation_markdown(c))),
            ]
    if sessions is not None:
        files.append(("conversations_index.md", D.redact(CA.sessions_index_markdown(sessions))))
    for name, text in files:
        tmp = REPORTS / (name + ".tmp")
        tmp.write_text(text)
        tmp.replace(REPORTS / name)


def refresh_loop() -> None:
    while True:
        try:
            state = compute()
            with _lock:
                _state.clear()
                _state.update(state)
                _health.update(last_success=state["refreshed"], last_error=None)
            write_reports(
                state["snapshot"],
                state.get("conversation"),
                state.get("conversations_others"),
                state.get("claude_sessions"),
            )
        except (
            Exception
        ) as exc:  # keep serving the last good state, and say so (/api/overview health)
            traceback.print_exc()
            with _lock:
                _health.update(
                    last_error=D.redact(f"{type(exc).__name__}: {exc}")[:300],
                    last_error_at=D.iso(time.time()),
                )
        time.sleep(REFRESH_S)


def runs_view(runs: list[dict]) -> list[dict]:
    """Runs without per-rep failure text (that is served per case by /api/case)."""
    out = []
    for r in runs:
        light = {k: v for k, v in r.items() if k not in ("cases", "end_ts")}
        light["cases"] = [
            {k: c[k] for k in ("id", "family", "style", "reps", "strict", "category")}
            for c in r["cases"]
        ]
        out.append(light)
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj) -> None:
        self._send(200, D.dumps(obj).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        with _lock:
            st = dict(_state)
        host = (self.headers.get("Host") or "").lower()
        if host not in ALLOWED_HOSTS:  # DNS-rebinding guard: only the loopback names may read this
            return self._send(403, b'{"error":"forbidden host"}', "application/json")
        if not st:
            return self._send(503, b'{"error":"warming up"}', "application/json")
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            return self._send(
                200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8"
            )
        if url.path == "/api/snapshot":
            return self._json(st["snapshot"])
        if url.path == "/api/runs":
            return self._json(
                {
                    "refreshed": st["refreshed"],
                    "runs": runs_view(st["runs"]),
                    "incomplete": st["incomplete"],
                }
            )
        if url.path == "/api/failures":
            return self._json({"refreshed": st["refreshed"], **st["failures"]})
        if url.path == "/api/overview":
            with _lock:
                health = dict(_health)
            health["data_age_s"] = int(time.time() - D.parse_utc(st["refreshed"]))
            health["refresh_every_s"] = REFRESH_S
            return self._json(
                {
                    "refreshed": st["refreshed"],
                    "health": health,
                    "overview": st["overview"],
                    "panels": st["panels"],
                }
            )
        if url.path == "/api/final-case":
            return self._json({"refreshed": st["refreshed"], **st.get("final", {})})
        if url.path == "/api/builder":
            return self._json({"refreshed": st["refreshed"], **st["builder"]})
        if url.path == "/api/claude-sessions":
            return self._json(
                {"refreshed": st["refreshed"], "sessions": st.get("claude_sessions", [])}
            )
        if url.path == "/api/claude-activity":
            wanted = q.get("session", [None])[0]
            if not wanted:
                return self._json(st["claude"])
            if wanted in st.get("claude_others", {}):
                return self._json(st["claude_others"][wanted])
            try:
                return self._json(CA.activity(wanted))
            except Exception as exc:
                return self._json(
                    {"available": False, "reason": f"monitor error: {type(exc).__name__}"}
                )
        if url.path == "/api/claude-conversation":
            wanted = q.get("session", [None])[0]
            raw = q.get("limit", [""])[0]
            limit = int(raw) if raw.isascii() and raw.isdigit() and int(raw) > 0 else None
            if not wanted and limit is None:
                return self._json(st["conversation"])
            if wanted in st.get("conversations_others", {}) and limit is None:
                return self._json(st["conversations_others"][wanted])
            try:
                return self._json(CA.conversation(wanted, limit))
            except Exception as exc:
                return self._json(
                    {"available": False, "reason": f"monitor error: {type(exc).__name__}"}
                )
        if url.path == "/api/failure-details":
            return self._json(
                {"refreshed": st["refreshed"], **EV.index(st["runs"], st["incomplete"])}
            )
        if url.path == "/api/failure-detail":
            rep = q.get("rep", [""])[0]
            if rep and not (rep.isascii() and rep.isdigit() and len(rep) < 4 and int(rep) > 0):
                return self._send(
                    400, b'{"error":"rep must be a positive integer"}', "application/json"
                )
            try:
                found = EV.detail(
                    st["runs"],
                    q.get("run", [""])[0],
                    q.get("case", [""])[0],
                    int(rep) if rep else None,
                )
            except EV.EvidenceError as exc:
                return self._send(
                    404, json.dumps({"error": f"Not available: {exc}"}).encode(), "application/json"
                )
            except Exception as exc:
                return self._send(
                    500,
                    json.dumps({"error": f"evidence error: {type(exc).__name__}"}).encode(),
                    "application/json",
                )
            return self._json(found)
        if url.path == "/api/comparison":
            if not st.get("comparison"):
                return self._send(
                    500,
                    b'{"error":"comparison unavailable (see server console)"}',
                    "application/json",
                )
            try:
                found = C.view(st["comparison"], q)
            except C.QueryError as exc:
                return self._send(400, D.dumps({"error": str(exc)}).encode(), "application/json")
            return self._json({"refreshed": st["refreshed"], **found})
        if url.path == "/api/rules-and-cases":
            try:
                return self._json(RC.view())
            except Exception as exc:
                traceback.print_exc()
                return self._send(
                    500,
                    json.dumps({"error": f"rules view error: {type(exc).__name__}"}).encode(),
                    "application/json",
                )
        if url.path == "/api/case":
            detail = D.case_detail(st["runs"], q.get("run", [""])[0], q.get("case", [""])[0])
            return (
                self._json(detail)
                if detail
                else self._send(404, b'{"error":"Not available"}', "application/json")
            )
        self._send(404, b'{"error":"not found"}', "application/json")

    def _refuse(self) -> None:
        self._send(405, b'{"error":"read-only dashboard"}', "application/json")

    do_POST = do_PUT = do_DELETE = do_PATCH = _refuse  # noqa: N815

    def log_message(self, fmt: str, *args) -> None:
        pass


class Server(ThreadingHTTPServer):
    # The page fires 8+ requests at once. The default listen backlog (5) overflowed while the refresh
    # thread held the CPU, and the kernel reset the extra connections ("Failed to fetch" in the page).
    request_queue_size = 128
    daemon_threads = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--snapshot-only", action="store_true", help="write reports/latest_snapshot.* once and exit"
    )
    a = ap.parse_args()
    if a.snapshot_only:
        st = compute()
        write_reports(
            st["snapshot"],
            st.get("conversation"),
            st.get("conversations_others"),
            st.get("claude_sessions"),
        )
        print(f"wrote {REPORTS}/latest_snapshot.json and .md")
        return
    threading.Thread(target=refresh_loop, daemon=True).start()
    ALLOWED_HOSTS.update({f"127.0.0.1:{a.port}", f"localhost:{a.port}"})
    server = Server(("127.0.0.1", a.port), Handler)  # loopback only
    print(f"dashboard on http://127.0.0.1:{a.port} (read-only; Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
