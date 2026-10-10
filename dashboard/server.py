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
import data as D  # noqa: E402

HERE = Path(__file__).resolve().parent
REPORTS = D.ROOT / "reports"
REFRESH_S = 12
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
    state["snapshot"] = A.snapshot(state)
    state["refreshed"] = D.iso(time.time())
    return state


def write_reports(snap: dict) -> None:
    REPORTS.mkdir(exist_ok=True)
    for name, text in (
        ("latest_snapshot.json", D.redact(json.dumps(snap, indent=2, default=str))),
        ("latest_snapshot.md", A.snapshot_markdown(snap)),
    ):
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
            write_reports(state["snapshot"])
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
        self._send(200, D.redact(json.dumps(obj, default=str)).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        with _lock:
            st = dict(_state)
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
        write_reports(compute()["snapshot"])
        print(f"wrote {REPORTS}/latest_snapshot.json and .md")
        return
    threading.Thread(target=refresh_loop, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)  # loopback only
    print(f"dashboard on http://127.0.0.1:{a.port} (read-only; Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
