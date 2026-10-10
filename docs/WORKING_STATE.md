# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-10 16:25 Istanbul (13:25 UTC). Last commit `031344c`. Hidden briefs open Sun 11 Oct 17:00 UTC.

## Phase

The phases come from `docs/design.md` §7:
- **Phase 1 (Brief A):** mostly done.
- **Phase 2 (Brief B, multi-product):** started.
- **Phase 3 (robustness):** sandbox hardening done; variant dry builds done; raw-a fixture built (score pending);
  `--style` runs not started.
- **Phase 4 (submission hardening):** `docs/RUNBOOK.md` written; `scripts/check_secrets.py`; Python version guard;
  fresh-clone timed build not done yet.

## Latest work (13:00 UTC)

- `90b737d` commits the PUB-03 fix (identity: verify an answer inside a mixed message first) and the PUB-12 fix (facts:
  "after attempt N is refused, make NO further offer", only when N > 0). `make verify`: 678 passed.
- All 3 dev agents were redeployed from saved specs with `90b737d` (now version 3, same ids). Validation, dry run and
  smoke test PASS.
- **3-rep results with `90b737d`:** fixA **10/10**, llmA **10/10**, abB **2/3** (PUB-12 0/3), abA **8/10** (PUB-05 0/3
  no close_call after the note, PUB-06 2/3). All are logged in the Score log.
- `e186247` adds an explicit per-product ATTEMPTS procedure and read-back honesty (PUB-12). `d46b807` puts notes before
  the goodbye and makes the reply after a note re-say goodbye with the ending, never empty (PUB-05). `make verify`: 682
  passed. dev-ab-llm and dev-a-llm were redeployed with `d46b807` (version 4).
- **Running (background):** rawA (dev-raw-a, built at `fe1d7ef`), then abB, abA and llmA at `d46b807`. Results go to
  `runs/dev/rawA-r3-fe1d7ef.*` and `runs/dev/{abB,abA,llmA}-r3-d46b807.*`.
- **Correction:** the subject of commit `9646cdf` says raw-a scored 10/10. It had not been scored yet; see the Score log.
- `fe1d7ef`: `build.py` exits with a clear message on Python < 3.10. The kit needs 3.10+, and the system `python3`
  here is 3.9.
- Trace redaction check: the actual secret values from `.env` and key patterns appear in none of the builder logs
  (deploy + dry, LLM runs included). `FREYA_BANK_TEAM_KEY` is used only by `run_cases.py` and never goes into workflows.
- Phase 3, variants: fresh `--dry` LLM builds of variant-c and variant-r give exp05 "OK" on every check.
- **NEW raw-material fixture `tests/fixtures/briefs/raw-a.md`:** Brief A told as an e-mail, a policy extract with CRM
  codes, a memo with 5 amendments (callback window, holidays, early deadline, "next <weekday>", the SMS sentence) and a
  code list, keeping the same meaning. Consolidation applied all amendments. Against the clean extraction, 8 of 182
  typed leaves differ, all harmless: prose inside lists, an unused precedence `outcome`, and wrong_number/deceased
  rows only in third_party (the opening routes them there anyway). It is deployed as slot **dev-raw-a** (workflow
  `7286c0bd-223f-4185-a61a-a7fedd43279b`, agent `eb321c47-0eb5-4ceb-9624-a3012d3c1957`, build 109 s, 2 model calls).

## Latest measured scores

Official-style scoring counts a case only at 3/3.

| Agent | Spec source | Brief | Code version | Result |
|---|---|---|---|---|
| baseline (kit minimal_builder) | n/a | A / B | n/a | 6/10 (1 rep) / 1/3 |
| dev-a-fixture | `tests/fixtures/spec_a.json` | A | `90b737d` | 3 reps: **10/10** |
| dev-a-llm | LLM | A | `90b737d` | 3 reps: **10/10** |
| dev-ab-llm | LLM | B (3 cases) | `90b737d` | 3 reps: **2/3** (PUB-12 0/3); re-run at `d46b807` queued |
| dev-ab-llm | LLM | A (10 cases) | `90b737d` | 3 reps: **8/10** (PUB-05 0/3, PUB-06 2/3); re-run at `d46b807` queued |
| dev-raw-a | LLM from raw-a.md | A | `fe1d7ef` | running |

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

1. Read the rawA, abB, abA and llmA results as they land. Log each in the Score log and read every failure transcript.
   Per-rep calls are in the result JSON `all_rows` (show_run shows only one call per case). To redeploy (`--spec`,
   about 5 s, 0 model calls):
   - `.venv/bin/python builder/build.py kit/briefs/brief-a.md kit/tools/openapi.json --spec tests/fixtures/spec_a.json --slot dev-a-fixture`
   - `... brief-a.md ... --spec runs/dev/spec-a-llm.json --slot dev-a-llm`
   - `... brief-a.md brief-b.md ... --spec runs/dev/spec-ab-llm.json --slot dev-ab-llm`
   - Note: dev-a-fixture is still at `90b737d` (version 3).
2. **Phase 3 robustness:** `--style pieces|corrects|talkative|asks_back|in_words` runs on A and B.
3. **Phase 4:** a fresh-clone timed build (`git clone` to scratch, then the RUNBOOK command, then a check of the trace).
4. **Ask the user** (RUNBOOK → Open questions): repo visibility, team name, and the OpenAI key for the organisers' re-run.
5. Freeze target about Sun 15:30 UTC (tag `freeze-final`). After 17:00 UTC: generic bug fixes only, no hidden-brief
   content. Follow `docs/RUNBOOK.md`.

## Open questions / risks being tracked

- **Sandbox output truncation.** It is a platform flake that gets worse under load. Watch for `function_call_error`
  "Sandbox did not return a parseable result" in transcripts, and check whether `6393c16` makes it go away.
- **Organiser re-run.** Their run of our builder needs an OpenAI key. The env vars are documented in README. Raise
  this with the user before submission.
- **Untested platform behaviour:** pre-hook `vars` writes reaching the post-hook, and the `_args` persistence used for
  note reasons in finalize. Watch the B runs.
