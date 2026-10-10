"""Submission entry point: python3 builder/build.py <brief.md> [...] <tool_api.json>

Thin launcher so the builder runs from a fresh clone with the standard library only
(no install step): it puts src/ on the path and calls freya_builder.cli.main().
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    if sys.version_info < (3, 10):  # noqa: UP036 - guards interpreters older than the project target
        sys.exit(f"builder needs Python 3.10+ (like the kit); this is {sys.version.split()[0]}")
    from freya_builder.cli import main

    sys.exit(main())
