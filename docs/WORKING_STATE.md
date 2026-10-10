# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-10 16:56 Istanbul (13:56 UTC). Last commit `03ee6b0`. Hidden briefs open Sun 11 Oct 17:00 UTC.

## Phase

The phases come from `docs/design.md` §7:
- **Phase 1 (Brief A):** mostly done.
- **Phase 2 (Brief B, multi-product):** started.
- **Phase 3 (robustness):** sandbox hardening done; variant dry builds done; raw-a fixture built (score pending);
  `--style` runs not started.
- **Phase 4 (submission hardening):** `docs/RUNBOOK.md` written; `scripts/check_secrets.py`; Python version guard;
  fresh-clone timed build not done yet.

## Latest work (13:56 UTC)

- **USER DECISIONS (10 Oct):** team **Pistalogic**; the repo stays **private** for now (the user will share it or make
  it public later). The user asked about running the builder LLM on Freya. We recommended staying on OpenAI (no
  completion endpoint, maxTokens 4000 < our 4.2–4.6k outputs, undocumented model strings); see the Decision log. Still
  open: how the organisers get an OpenAI key for their re-run (ask them on the support channel).
- **PLATFORM OUTAGE since about 13:41 UTC:** `/chat/message` returns 503 for every workflow, and simulation agents go
  silent after the first customer turn. Runs llmA@d46b807 rep 3 and extraB@d46b807 are invalid. A background probe
  checks again around 14:04 UTC. When Freya is back, run `bash <scratchpad>/chain.sh` (redeploy at HEAD, then PUB-05 on
  the A+B agent, abB, extraB, llmA, abA, and a 1-rep style sweep). The script is reproduced in the next-steps section.
- Commits this session:
  - `90b737d`: PUB-03 identity + PUB-12 stop line.
  - `fe1d7ef`: Python guard.
  - `9646cdf`: raw-a fixture.
  - `e186247`: ATTEMPTS procedure + read-back honesty.
  - `d46b807`: notes wording (did NOT fix the stall).
  - `031344c`: RUNBOOK + check_secrets.
  - `d33d8a7`: extra-b cases.
  - **`92b83b5`: notes-done route into a speaking passthrough `wrap_up`** (structural fix for the goodbye-with-note
    stall; not yet measured).
  - `03ee6b0`: DATES resolve weekday phrases first.
  - `make verify`: 688 passed.
- Measured (3 reps):
  - fixA@90b737d 10/10, llmA@90b737d 10/10, rawA@fe1d7ef 10/10 (raw-material brief).
  - abB@d46b807 1/3, abA@d46b807 9/10 (the stall, plus attempt variance).
  - The Score log has every run with its reason.
- `9646cdf`'s subject claimed raw-a 10/10 before it was scored; it was later measured at 10/10.
- Phase 4 done: fresh-clone build 110 s, trace clean, stdlib only (`python -S`), RUNBOOK, `scripts/check_secrets.py`.

## Latest measured scores

Official-style scoring counts a case only at 3/3.

| Agent | Spec source | Brief | Code version | Result |
|---|---|---|---|---|
| baseline (kit minimal_builder) | n/a | A / B | n/a | 6/10 (1 rep) / 1/3 |
| dev-a-fixture | `tests/fixtures/spec_a.json` | A | `90b737d` | 3 reps: **10/10** |
| dev-a-llm | LLM | A | `90b737d` | 3 reps: **10/10** |
| dev-ab-llm | LLM | B (3 cases) | `d46b807` | 3 reps: **1/3** (PUB-12 stall + attempts, PUB-11 date mix-up) |
| dev-ab-llm | LLM | A (10 cases) | `d46b807` | 3 reps: **9/10** (PUB-05 0/3 stall) |
| dev-raw-a | LLM from raw-a.md | A | `fe1d7ef` | 3 reps: **10/10** |

## Deployed agents (slot → ids; the slots file is `.freya-agents.json` in the repo root, gitignored)

| Slot | Workflow | Agent |
|---|---|---|
| dev-a-fixture | 349752be-0764-4025-9e5f-4248a6fe6bff | f0354c17-f459-4d7a-bfef-62acea2e5cd7 |
| dev-a-llm | 81c14d7a-c622-49e2-98fb-8cd347ef4ac2 | c6a57c76-a3ea-42cc-9cfb-7eb8773b9436 |
| dev-ab-llm | f8f9b203-66ae-43e1-9d37-82e76d26b762 | b867b809-5d2b-4e75-935f-1ed6086432c3 |
| dev-raw-a | 7286c0bd-223f-4185-a61a-a7fedd43279b | eb321c47-0eb5-4ceb-9624-a3012d3c1957 |

Also present: the organiser base `2f14ba80-…`, the baseline minimal agents (slots brief-a and brief-a+brief-b), and the
exp01 agent `1ee05139-…`. Saved specs from LLM builds are `runs/dev/spec-a-llm.json` and `runs/dev/spec-ab-llm.json`.
Redeploy them with `--spec` to skip the LLM.

## Next steps (in order)

1. When Freya answers again, run the chain (it uses bash; zsh does not word-split `$var`, which broke one sweep):
   `bash /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/b5ac8f2d-13b1-4c15-8c93-74b9dca1b3cf/scratchpad/chain.sh`.
   If the scratchpad is gone, rebuild it from this list:
   - redeploy dev-ab-llm, dev-a-llm and dev-a-fixture with `--spec` at HEAD;
   - then `run_cases` for: A+B agent `--brief A --only PUB-05 --reps 3`; `--brief B --reps 3`;
     `--cases tests/fixtures/cases/extra-b.json --reps 3`; dev-a-llm `--brief A --reps 3`; A+B agent `--brief A --reps 3`;
   - then `--style` in {asks_back, pieces, corrects, talkative, in_words} at 1 rep on dev-a-llm A and the A+B agent B.
   - Watch `wrap_up`: does the passthrough conversation node speak its llm line and then end? Read `route_evaluated`.
2. Log every result in the Score log. Per-rep calls are in the result JSON `all_rows`.
3. Freeze about Sun 15:30 UTC (tag `freeze-final`). From 17:00 UTC follow `docs/RUNBOOK.md`.

## Open questions / risks being tracked

- **Sandbox output truncation.** It is a platform flake that gets worse under load. Watch for `function_call_error`
  "Sandbox did not return a parseable result" in transcripts, and check whether `6393c16` makes it go away.
- **Organiser re-run.** Their run of our builder needs an OpenAI key. The env vars are documented in README. Raise
  this with the user before submission.
- **Untested platform behaviour:** pre-hook `vars` writes reaching the post-hook, and the `_args` persistence used for
  note reasons in finalize. Watch the B runs.
