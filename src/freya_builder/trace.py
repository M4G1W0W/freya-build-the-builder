"""The builder's run trace (required for submission; see CLAUDE.md "Builder trace").

One line per event on stderr, UTC timestamps. The submitted trace is captured with
`... 2>&1 | tee traces/<name>.log`. Secret values from the environment are redacted from
every line as a safety net; code should never pass secrets here in the first place.
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import TextIO

SECRET_ENV = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "OPENAI_API_KEY")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Trace:
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stderr
        self.t0 = time.monotonic()
        self.model_calls = 0
        self.secrets = [v for k in SECRET_ENV if len(v := os.environ.get(k, "")) >= 8]

    def _redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return text

    def line(self, kind: str, message: str) -> None:
        print(self._redact(f"{utc_now()} {kind:<7} {message}"), file=self.stream, flush=True)

    def start(self, brief_paths: list[str], tool_api_path: str) -> None:
        self.line("START", f"briefs={brief_paths} tool_api={tool_api_path}")

    def step(self, message: str) -> None:
        self.line("STEP", message)

    def model_call(self, model: str, purpose: str, seconds: float, usage: dict | None) -> None:
        self.model_calls += 1
        tokens = ""
        if usage:
            tokens = f" tokens_in={usage.get('prompt_tokens')} tokens_out={usage.get('completion_tokens')}"
        self.line(
            "MODEL",
            f"#{self.model_calls} model={model} purpose={purpose} took={seconds:.1f}s{tokens}",
        )

    def created(
        self, workflow_id: str, agent_id: str, steps: int, tools: int, version=None
    ) -> None:
        self.line(
            "CREATED",
            f"workflow_id={workflow_id} agent_id={agent_id} steps={steps} tools={tools} version={version}",
        )

    def test(self, name: str, passed: bool, detail: str = "") -> None:
        self.line("TEST", f"{name}: {'PASS' if passed else 'FAIL'} {detail}".rstrip())

    def warn(self, message: str) -> None:
        self.line("WARN", message)

    def end(self, ok: bool) -> None:
        took = time.monotonic() - self.t0
        self.line("END", f"ok={ok} build_seconds={took:.0f} model_calls={self.model_calls}")
