"""Submission entry point: python3 builder/build.py <brief.md> [...] <tool_api.json>

Thin launcher so the builder runs from a fresh clone with the standard library only
(no install step): it puts src/ on the path and calls freya_builder.cli.main().
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    from freya_builder.cli import main

    sys.exit(main())
