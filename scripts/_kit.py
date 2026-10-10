"""Shared setup for dev scripts: load .env, then import the official kit client unmodified.

`kit/freya.py` reads its environment at import time, so `.env` is loaded before the import.
Values already set in the environment win over `.env`.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "kit"
RUNS = ROOT / "runs"


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_env()
sys.path[:0] = [str(KIT), str(KIT / "tools")]

import freya  # noqa: E402
import score  # noqa: E402

__all__ = ["KIT", "ROOT", "RUNS", "freya", "score"]
