# CLAUDE.md — Freya "Build the Builder" hackathon

## Competition context

- **Event:** Y Combinator — *Build the Builder*, on the Freya Voice AI platform. Fully online.
- **Window:** 2026-10-10 13:00 → 2026-10-11 23:00 Istanbul time (UTC+3) = 10:00 → 20:00 UTC. ~34 h.
- **Prize:** interview with Y Combinator.
- **Challenge (official text):** "A bank wants to phone its customers who are late on a payment.
  You write a builder: a program that reads the bank's collections brief and creates a phone agent
  on Freya. We run that agent against simulated customers. Your score is the share of cases the
  agent handles correctly."
- **What we build:** the *builder* (brief → configured Freya agent), not a hand-written agent.
- **Scoring objective:** maximise the share of simulated cases the generated agent handles
  correctly. That number is the only metric that matters; optimise for it, measured.
- **Source of truth:** the official instructions + starter kit released at kickoff. They override
  everything in this repo, including this file. Record what they say in `docs/hackathon_notes.md`.

Public event page (<https://events.ycombinator.com/AI-FDE-Build-the-Builder26>, read pre-kickoff):
the builder gets a task description **and the available tools**. It is run on **unseen tasks** with
**no manual edits**, and it must be submitted with its dependencies and **reproducible run instructions**.
Details are in `docs/hackathon_notes.md`.

## Freya quick reference (details: `docs/freya_api_notes.md`)

- Canonical contract: the **live** spec <https://app.freyavoice.ai/api/openapi.json> (snapshot:
  `docs/reference/freya_openapi_live.json`). `docs.freyavoice.ai/api-reference/openapi.json` is **stale**.
- Base `https://app.freyavoice.ai/api/v2`, header `Authorization: Bearer <key>`. Responses are
  wrapped in `{success, data: {message, result}}`.
- Agents are created and updated via `POST /agents` and `PUT /agents/{id}`. Workflows are **read-only** in the API.
- Test surfaces: `POST /chat/message` (text, synchronous), Personas/Simulations (async), Unit Tests, and
  `GET /call/{id}` for transcripts and assertion results.
- Undocumented, so verify by experiment before relying on it: tool `handler` values, PUT merge vs replace, which
  version runs in chat/simulations, and `{{var}}` filling from `customerVariables`.

## Non-negotiable rules

1. Never invent Freya API functionality. Check `docs/freya_api_notes.md`, the live OpenAPI spec,
   or the starter kit before using an endpoint or field. If it isn't documented, say so.
2. Always consult the documentation or starter kit; cite the source when adding API code.
3. Never invent bank policies. Every rule the agent follows must trace back to the bank's brief
   (or official materials). No made-up compliance rules, amounts, deadlines or scripts.
4. A successful deployment is not a correct agent. "Agent created (200 OK)" proves nothing about
   behaviour; only evaluation results do.
5. Prioritise actual test results over intuition, reviews or how a prompt "looks".
6. Preserve working implementations before major changes (commit + tag; see Git workflow).
7. Run the relevant tests after every code change, and report failures verbatim.
8. Keep solutions as simple as possible. No frameworks, no abstractions without a measured need.
9. Explain major architectural decisions (one paragraph in `docs/hackathon_notes.md` → Decision log).
10. Official hackathon instructions override preliminary assumptions — including the pipeline
    hypothesis below.

## Project structure

```
CLAUDE.md, README.md, pyproject.toml, .python-version, uv.lock
.env.example              placeholder env vars → copy to .env (gitignored)
src/freya_builder/        the package (empty until kickoff)
tests/                    pytest; tests/test_smoke.py checks env + repo skeleton
docs/freya_api_notes.md   verified Freya API notes ([C]onfirmed / [I]nferred / [ND] not documented)
docs/freya_api/           detailed verified notes per topic + agent config field tree
docs/hackathon_notes.md   logistics, event page facts, kickoff checklist, decision log, score log
docs/reference/           offline snapshot of public Freya docs + live OpenAPI spec (2026-10-10)
runs/                     (gitignored) per-run artefacts: generated configs, transcripts, results
```

Preliminary pipeline **hypothesis** (not a plan; validate against the official materials first):
brief → requirements extraction → structured policy → agent config → Freya deploy → simulated
conversations → evaluation/failure analysis → improved config.

## Python environment

- Python 3.12 (pinned in `.python-version`), managed by `uv`. Local `.venv/` only — never touch
  the system Python or install global packages.
- `uv sync` installs everything. Run tools via `uv run …` (or `source .venv/bin/activate`).
- Add deps with `uv add <pkg>` (runtime) / `uv add --dev <pkg>` (dev). Justify each new dependency;
  prefer the standard library.

## Coding standards

- Small, typed, pure functions where possible; side effects (HTTP, files) at the edges.
- Plain data (dataclasses / dicts / JSON) between pipeline stages, so every stage's output can be
  saved, diffed and replayed.
- Deterministic code wherever possible; isolate LLM/network calls behind one thin module each.
- `uv run ruff check . && uv run ruff format .` before committing. Line length 100.
- No dead code, no speculative features, no commented-out blocks.

## Testing requirements

- `uv run pytest` must pass before every commit.
- Unit tests for deterministic logic (parsing, validation, config generation) — no network.
- Tests that hit Freya or an LLM are marked (e.g. `@pytest.mark.live`) and skipped by default.
- Every bug found in evaluation becomes a regression case before it is fixed.
- Validate generated agent configs against the documented schema *before* deploying.

## Verification-first engineering

- Define "correct" from the official scoring rules before optimising anything.
- Get the smallest end-to-end path working first (brief in → agent on Freya → one evaluated
  conversation), then iterate.
- After each change: re-run the evaluation set, record the score in `docs/hackathon_notes.md`
  (Score log), and keep the change only if the score holds or improves.
- Read failing transcripts before changing prompts. Fix causes, not symptoms.

## Error handling & logging

- Use `logging` (not `print`) in library code; one logger per module.
- Log every Freya API call: method, path, status, latency, and any request/trace id. **Never**
  log headers, API keys or full credential-bearing URLs.
- Fail loudly with context (endpoint, status, response body excerpt). Don't swallow exceptions.
- Retry only idempotent requests on 429/5xx, bounded with backoff; never retry 4xx validation errors.
- Save raw inputs/outputs of each run under `runs/<timestamp>/` for failure analysis.

## Documentation expectations

- Freya facts go in `docs/freya_api_notes.md` with a source link and a status tag.
- Decisions, scores and official-rule findings go in `docs/hackathon_notes.md`.
- Keep the README's setup commands working.

## Security & credentials

- Secrets live only in `.env` (gitignored) or the shell environment. `.env.example` holds empty
  placeholders only (enforced by `tests/test_smoke.py`).
- Never print, log, commit or paste API keys. Never put secrets in URLs or query strings.
- Use test/hackathon credentials only; never real customer data.
- Do not push this repo to any public remote, and do not publish challenge code before the rules allow it.

## Git workflow

- Branch `main`; small commits with clear messages; commit whenever something works.
- Before a risky change: commit, then `git tag good-<short-name>` (or `score-<value>` once we can
  measure) so we can always return to a known-good builder.
- Never force-push, rewrite history, or change global git config.
- Don't commit `.env`, `.venv/`, `runs/`, logs or other generated artefacts.

## Fast iteration

- Time is the scarcest resource: optimise the edit → run → measure loop first.
- Time-box investigations (~20 min) and then ask or pick the simplest option.
- Prefer measuring over debating. When two approaches are plausible, test both on the eval set.
