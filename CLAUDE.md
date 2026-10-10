# CLAUDE.md — Freya "Build the Builder" hackathon

## Competition context

Official page: <https://www.freyavoice.ai/hackathon> (snapshot `docs/reference/hackathon_page.md`).
The **kit** (emailed at the start) overrides it. The full digest is in `docs/hackathon_notes.md`.

- **Window.** Sat 10 Oct 10:00 UTC (13:00 Istanbul) → hidden briefs at **Sun 17:00 UTC** (20:00 Istanbul) →
  submission closes **Sun 20:00 UTC** (23:00 Istanbul).
- **The builder.** One command: `python3 builder/build.py <brief> <tool_api.json>` → creates a
  **phone agent = a Freya workflow** (steps, prompts, tools, conditional routes, code nodes), with no
  manual edits. It must finish in **≤30 min per brief, including self-tests**, and print a **trace**: start
  and end time, every model call (model + one-line purpose), the workflow and agent ids it created, steps and
  tools, and self-test results. No API keys in the trace.
- **Scoring.** Simulated customers talk to the phone agent **in text, in English**. A case passes only if
  the **ledger is right** (read from the mock bank) **AND** a judge finds the **policy** was followed **AND** the agent was
  **honest**. 60 hidden cases (2 briefs × 30), **3 reps each, all must pass**. Tie-breaks: total promised
  amount on passed cases → shorter build time → earlier submission.
- **Hidden briefs.** Unseen; one is clean, one is raw material (email, policy extract, an amending memo,
  a code list). Same 7 tool names, but **fields and allowed values can change**. The call's date and time
  arrive as the variable `now`.
- **What matters most.** Maximise hidden-case pass rate, which requires run-to-run consistency. Average quality alone is not enough.

## Hard competition rules (break one and we are disqualified)

- **Nothing from a hidden brief may ever be written into the builder** (no rule, value, name, date or
  outcome) after Sun 17:00 UTC. Only generic bug fixes are allowed then. Never paste hidden-brief text into
  code, prompts, tests or fixtures.
- The phone agent may call **only the kit's tool API**. Any other service fails the case.
- The phone agent runs on the **Freya model set in the kit's `freya.py`. Do not change it.**
- **One Freya key per team. Do not probe or load-test the platform.** At most **200 workflows**
  per workspace (update in place via `freya.save_workflow`). Only **1 practice simulation** can run at a time.
- Submit a builder, not a hand-built agent. Never edit a generated phone agent by hand.

## Freya reference (details: `docs/freya_api_notes.md`; the kit's `docs/` and `freya.py` win)

- The kit's `docs/` (workflow format, tools, code nodes, the API calls a builder needs) and `freya.py`
  are the authority for workflows. The public docs we studied **don't document workflow creation**.
- Public API: base `https://app.freyavoice.ai/api/v2`, `Authorization: Bearer <key>`, responses are wrapped in
  `{success, data: {message, result}}`. The live spec is `docs/reference/freya_openapi_live.json`, and
  `docs.freyavoice.ai/api-reference/openapi.json` is **stale**.
- Practice scoring: `python3 tools/run_cases.py <agent_id> --brief A [--reps 3]` (3–11 min per 10 cases).

## Non-negotiable rules

1. Never invent Freya API functionality. Check the **kit first** (`docs/`, `freya.py`,
   `examples/minimal_builder.py`, the brief's tool API file), then `docs/freya_api_notes.md` and the live spec.
   If something isn't documented, say so.
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
11. Never hard-code Brief A/B specifics (dates, holidays, amounts, codes, identity questions, tool
    enums) into the builder. It must read a brief and a tool API file it has never seen. Test it on
    rewritten or perturbed copies of the public briefs, including a messy "raw material" version.

## Project structure

```
CLAUDE.md, README.md, pyproject.toml, .python-version, uv.lock
.env.example              placeholder env vars → copy to .env (gitignored)
src/freya_builder/        the package (empty until kickoff)
tests/                    pytest; tests/test_smoke.py checks env + repo skeleton
docs/freya_api_notes.md   verified Freya API notes ([C]onfirmed / [I]nferred / [ND] not documented)
docs/freya_api/           detailed verified notes per topic + agent config field tree
docs/hackathon_notes.md   logistics, event page facts, kickoff checklist, decision log, score log
docs/reference/           offline snapshot: public Freya docs, live OpenAPI spec, official hackathon
                          page (hackathon_page.md) + 13 practice cases (hackathon_practice_cases.json)
docs/hackathon_requirements.md  every rule extracted from the official page + open questions
runs/                     (gitignored) per-run artefacts: generated configs, transcripts, results
submission/               (COMMITTED) exported phone agents: hidden-N.workflow.json
traces/                   (COMMITTED) builder traces: hidden-N.log (keys stripped)
```
**Kit: `kit/`**, unmodified, from <https://www.freyavoice.ai/hackathon/build-the-builder.zip> (Data tab,
downloaded 2026-10-10; sha256 0d7e816a…). Read `kit/README.md` and `kit/docs/*.md` before touching workflows.
Don't edit files in `kit/`. Wrap or copy them instead, so it stays diffable against the official zip.

## Kit facts (verified 2026-10-10)

- **Env:** `source .env` sets `FREYA_API_KEY` (fak_…), `FREYA_API_URL=https://staging-app.freyavoice.ai`,
  `FREYA_BANK_TEAM_KEY` (ours, ≥16 chars, never change it) and `FREYA_WORKSPACE_ID`. **No MCP exists or is needed**:
  everything goes through `kit/freya.py` (REST, stdlib, browser-like User-Agent required).
- **Workflow API:** `POST /api/v2/workflow` (`?dryRun=true` validates), `PUT /api/v2/workflow/{id}` (full replace,
  **unpublished**), publish via `POST /api/v2/versions/workflow/{id}/publish`. Use `freya.save_workflow(slot, wf)`,
  which creates, updates and publishes in one call. A workspace holds **200 workflows**.
- **Phone-agent model:** `freya.AGENT_LLM` = `experimental-5`. Never change it. The simulator and judge use gemini-3-flash-preview.
- **Bank tools:** `api_call` tools posting to `https://freya-bank-mock.freyavoice.workers.dev/v1/<tool>`, with
  `customer_id` baked from `{{customer_id}}`. A result lands as `<tool>_response.data.*` (booleans as "true"/"True").
- **Scoring:** `python3 kit/tools/run_cases.py <agent_id> --brief A|B [--reps 3] [--style pieces|corrects|talkative|asks_back|in_words] [--out results/x.json]`.
  Debug with `freya.get_call(call_id)["messages"]` (system events show `route_evaluated` and tool calls).
- **Fast check without a simulation:** `POST /api/v2/chat/message {workflowId, message, customerVariables}`.

Preliminary pipeline **hypothesis** (not a plan; validate against the kit first):
brief + tool API → requirements extraction → structured policy → workflow config → Freya deploy →
simulated conversations → evaluation/failure analysis → improved config.

## Python environment

- Python 3.12 (pinned in `.python-version`), managed by `uv`. Local `.venv/` only — never touch
  the system Python or install global packages.
- `uv sync` installs everything. Run tools via `uv run …` (or `source .venv/bin/activate`).
- Add deps with `uv add <pkg>` (runtime) / `uv add --dev <pkg>` (dev). Justify each new dependency;
  prefer the standard library.
- **The submitted `run_command` must work from a fresh clone.** It takes `{brief_path} {tool_api_path}`, finishes in
  ≤30 min, and reads secrets from env vars. The organisers re-run the top 10. Either keep the builder stdlib-only
  like `freya.py` (`python3 builder/build.py …`), or document `uv sync && uv run …` in the README.

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
- Validate the generated workflow against the kit's workflow format (kit `docs/`), and its tools
  against the brief's tool API file, *before* calling `freya.py`.

## Verification-first engineering

- "Correct" is defined officially: ledger right **and** policy followed **and** honest, 3/3 reps.
- Get the smallest end-to-end path working first (kit's minimal builder → `run_cases.py`), then iterate.
- Measure with `python3 tools/run_cases.py <agent_id> --brief A --reps 3` (and `--brief B`). Scores
  vary between runs, so trust only rep-3 numbers. Record each run in `docs/hackathon_notes.md` (Score log).
- Only 1 simulation can run per workspace, at 3–11 min per 10 cases, so use cheap local checks first (workflow validation,
  date-arithmetic unit tests) and save simulations for real candidates.
- Read failing transcripts before changing prompts. Fix causes, not symptoms.

## Builder trace (required for submission)

The builder writes its trace to stdout/stderr, and it is run as `<run_command> 2>&1 | tee traces/<name>.log`.
It must always include:
- the run's start and end time in UTC (build time is a tie-break);
- one line per model call: the model id and a one-line purpose;
- what it created on Freya: workflow id, agent id, number of steps and tools;
- every self-test it ran, with the result.

It must never contain API keys or the team key.

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
- Do not push to any remote without the user's explicit go-ahead. Submission needs a GitHub repo URL
  and commit that the organisers can clone. Repo visibility (public, or private with access) is the user's
  decision and must be made before Sun 20:00 UTC.
- Traces get committed: strip API keys and team keys from them before committing.

## Git workflow

- Branch `main`; small commits with clear messages; commit whenever something works.
- Before a risky change: commit, then `git tag good-<short-name>` (or `score-<value>` once we can
  measure) so we can always return to a known-good builder.
- Never force-push, rewrite history, or change global git config.
- Don't commit `.env`, `.venv/`, `runs/` or scratch logs. **Do** commit the submission artefacts:
  `submission/*.workflow.json` (from `freya.export_workflow`) and `traces/*.log` (keys stripped).

## Fast iteration

- Time is the scarcest resource: optimise the edit → run → measure loop first.
- Time-box investigations (~20 min) and then ask or pick the simplest option.
- Prefer measuring over debating. When two approaches are plausible, test both on the eval set.
