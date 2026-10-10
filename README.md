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

## Dev loop

`kit/` is the official kit, unmodified. Our dev tools are in `scripts/`, wrapped by `make` (`make help`).

```bash
make check                                   # env vars, Freya API, workspace, credits (read-only)
make baseline                                # kit's minimal builder on brief A -> prints workflow_id, agent_id
make cases AGENT=<agent_id> BRIEF=A REPS=3   # practice run (also STYLE=talkative, ONLY=PUB-04)
make show RUN=runs/<timestamp>-A.json        # summary + transcripts of failed cases
make call ID=<call_id>                       # one transcript: speech, tool calls, results, routes
make chat WF=<workflow_id> CASE=PUB-01       # talk to a workflow over text (no judge)
make credits LABEL="after X"                 # log credit use
```

Builder (to be written): `python3 builder/build.py <brief> <tool_api.json> 2>&1 | tee traces/<name>.log`.
