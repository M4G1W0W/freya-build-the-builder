# Freya Hackathon — YC "Build the Builder"

Private working repo for Y Combinator's **Build the Builder** hackathon on the
[Freya Voice AI](https://docs.freyavoice.ai/) platform (Oct 10 13:00 → Oct 11 23:00, Istanbul time).

> **Challenge (official text):** "A bank wants to phone its customers who are late on a payment.
> You write a builder: a program that reads the bank's collections brief and creates a phone agent
> on Freya. We run that agent against simulated customers. Your score is the share of cases the
> agent handles correctly."

**Status:** environment prepared. The rules are published (`docs/reference/hackathon_page.md`, digest in
`docs/hackathon_notes.md`). The kit arrived by email at the start. No builder code yet. The kit and organiser
emails override this repo.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) (Python 3.12 is pinned in `.python-version`).

```bash
uv sync                      # creates .venv and installs the project + dev tools
cp .env.example .env         # then fill in real values locally (never commit .env)
uv run pytest                # run the test suite
uv run ruff check .          # lint
```

Without `uv`: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e . pytest ruff`.

## Layout

```
CLAUDE.md                 Development rules for this hackathon (read first)
README.md                 This file
.env.example              Placeholder env vars (copy to .env)
pyproject.toml            Project metadata, deps, pytest/ruff config
src/freya_builder/        Python package (empty until kickoff)
tests/                    pytest suite (smoke test for now)
docs/freya_api_notes.md   Verified notes on the Freya API (confirmed vs. inferred) — start here
docs/freya_api/           Detailed per-topic notes + agent config field tree
docs/hackathon_notes.md   Official rules digest, kickoff checklist, decision log, score log
docs/hackathon_requirements.md  Every rule from the official page + open questions
docs/reference/           Offline snapshot: Freya docs, OpenAPI spec, hackathon page + practice cases
submission/               (committed) exported phone agents, hidden-N.workflow.json
traces/                   (committed) builder run traces, hidden-N.log, keys stripped
```

Builder, scoring and submission commands will be added once the kit is integrated. Page shape:
`python3 builder/build.py <brief> <tool_api.json> 2>&1 | tee traces/<name>.log` and
`python3 tools/run_cases.py <agent_id> --brief A --reps 3`.
