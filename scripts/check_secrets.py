"""Fail if any file contains a secret: the actual values of the secret env vars, or key patterns.

Run before committing traces or exported workflows (values are never printed):
    set -a && source .env && set +a && .venv/bin/python scripts/check_secrets.py traces/*.log submission/*.json
"""

import os
import re
import sys
from pathlib import Path

SECRET_ENV = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "OPENAI_API_KEY", "FREYA_WORKSPACE_ID")
PATTERNS = (r"\bfak_\w{8,}", r"\bsk-[A-Za-z0-9_-]{16,}", r"Bearer \S{8,}")


def main() -> int:
    secrets = {n: os.environ[n] for n in SECRET_ENV if os.environ.get(n)}
    missing = [n for n in SECRET_ENV if n not in secrets]
    if missing:
        print(f"note: not set, so not checked by value: {', '.join(missing)}")
    hits = 0
    for name in sys.argv[1:]:
        text = Path(name).read_text(errors="replace")
        for env, value in secrets.items():
            if value in text:
                hits += 1
                print(f"LEAK {env} value in {name}")
        for pat in PATTERNS:
            if re.search(pat, text):
                hits += 1
                print(f"PATTERN {pat!r} in {name}")
    print(f"checked {len(sys.argv) - 1} file(s): {'CLEAN' if not hits else f'{hits} hit(s)'}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
