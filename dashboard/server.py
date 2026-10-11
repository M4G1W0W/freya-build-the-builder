"""Read-only testing dashboard: http://127.0.0.1:8765

    .venv/bin/python dashboard/server.py [--port 8765]

GET only. It reads local files and read-only git/ps output, never calls the network, and writes nothing
except reports/latest_snapshot.{json,md}. Data is recomputed every 12 s in a background thread.
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

HERE = Path(__file__).resolve().parent
REPORTS = D.ROOT / "reports"
REFRESH_S = 12
ALLOWED_HOSTS: set[str] = set()
_state: dict = {}
_lock = threading.Lock()


def compute() -> dict:
    git = D.git_state()
    traces = D.all_traces()
    runs, incomplete = D.build_runs(traces, git["commits"])
    state = {"runs": runs, "incomplete": incomplete}
    state["overview"] = A.overview(git, runs, incomplete, D.running_tests(), D.working_state())
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
    state["snapshot"] = A.snapshot(state)
    state["snapshot"]["claude_session"] = CA.summary(state["claude"])
    try:
        state["conversation"] = CA.conversation(limit=300)
    except Exception as exc:
        state["conversation"] = {
            "available": False,
            "reason": f"monitor error: {type(exc).__name__}",
        }
    state["snapshot"]["claude_conversation"] = (
        "reports/latest_conversation.md (and .json): your prompts and Claude's replies"
    )
    state["refreshed"] = D.iso(time.time())
    return state


def write_reports(snap: dict, convo: dict | None = None) -> None:
    REPORTS.mkdir(exist_ok=True)
    files = [
        ("latest_snapshot.json", D.dumps(snap, indent=2)),
        ("latest_snapshot.md", A.snapshot_markdown(snap)),
    ]
    if convo is not None:
        files += [
            ("latest_conversation.json", D.dumps(convo, indent=2)),
            ("latest_conversation.md", D.redact(CA.conversation_markdown(convo))),
        ]
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
            write_reports(state["snapshot"], state.get("conversation"))
        except Exception:  # keep serving the last good state; the error shows in the console
            traceback.print_exc()
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
            return self._json(
                {"refreshed": st["refreshed"], "overview": st["overview"], "panels": st["panels"]}
            )
        if url.path == "/api/builder":
            return self._json({"refreshed": st["refreshed"], **st["builder"]})
        if url.path == "/api/claude-activity":
            wanted = q.get("session", [None])[0]
            if not wanted:
                return self._json(st["claude"])
            try:
                return self._json(CA.activity(wanted))
            except Exception as exc:
                return self._json(
                    {"available": False, "reason": f"monitor error: {type(exc).__name__}"}
                )
        if url.path == "/api/claude-conversation":
            wanted = q.get("session", [None])[0]
            raw = q.get("limit", ["300"])[0]
            limit = int(raw) if raw.isdigit() else 300
            if not wanted and limit == 300:
                return self._json(st["conversation"])
            try:
                return self._json(CA.conversation(wanted, min(limit, 500)))
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--snapshot-only", action="store_true", help="write reports/latest_snapshot.* once and exit"
    )
    a = ap.parse_args()
    if a.snapshot_only:
        st = compute()
        write_reports(st["snapshot"], st.get("conversation"))
        print(f"wrote {REPORTS}/latest_snapshot.json and .md")
        return
    threading.Thread(target=refresh_loop, daemon=True).start()
    ALLOWED_HOSTS.update({f"127.0.0.1:{a.port}", f"localhost:{a.port}"})
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)  # loopback only
    print(f"dashboard on http://127.0.0.1:{a.port} (read-only; Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
