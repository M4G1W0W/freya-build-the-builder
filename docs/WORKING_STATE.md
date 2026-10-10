# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-10 15:55 Istanbul (12:55 UTC). Last commit `6393c16`. Hidden briefs open Sun 11 Oct 17:00 UTC.

## Phase

The phases come from `docs/design.md` §7:
- **Phase 1 (Brief A):** mostly done.
- **Phase 2 (Brief B, multi-product):** started.
- **Phase 3 (robustness):** partly done (sandbox truncation hardening).
- **Phase 4 (submission hardening):** not started (README run command done).

## UNCOMMITTED changes in the working tree (written, NOT yet tested or committed)

The user interrupted this step to save context. These are generic fixes from the latest 3-rep runs:
1. `src/freya_builder/render.py` (`_identity_task`): "Whenever the customer's message contains an answer … CALL
   verify_identity with that answer FIRST, then reply." It fixes PUB-03: a third wrong answer said together with a
   complaint was never verified.
2. `src/freya_builder/sandbox/facts.py` (`_product`): adds the line "after attempt N is refused, make NO further offer for
   this product". It fixes PUB-12: the floor was offered after the last allowed attempt was refused.
3. `tests/test_codegen_integration.py`: adds `test_facts_state_when_offers_must_stop`.

**Next step for these:** run `make verify`. If green, commit. Then redeploy and re-measure (see Next steps).

## Latest measured scores

Official-style scoring counts a case only at 3/3.

| Agent | Spec source | Brief | Code version | Result |
|---|---|---|---|---|
| baseline (kit minimal_builder) | n/a | A / B | n/a | 6/10 (1 rep) / 1/3 |
| dev-a-fixture | `tests/fixtures/spec_a.json` | A | before `6393c16` | 3 reps: **9/10** (PUB-01 2/3, sandbox truncation) |
| dev-a-llm | LLM | A | before `6393c16` | 3 reps: **8/10** (PUB-03 2/3 identity, PUB-09 2/3 sandbox stall) |
| dev-ab-llm | LLM | B (3 cases) | before `6393c16` | 3 reps: **2/3** (PUB-12 1/3 attempt count) |

Commit `6393c16` (compact calendar, no pre-hooks, sandbox-free early closes, retry rule) is **not yet deployed or measured**.

## Deployed agents (slot → ids; the slots file is `.freya-agents.json` in the repo root, gitignored)

| Slot | Workflow | Agent |
|---|---|---|
| dev-a-fixture | 349752be-0764-4025-9e5f-4248a6fe6bff | f0354c17-f459-4d7a-bfef-62acea2e5cd7 |
| dev-a-llm | 81c14d7a-c622-49e2-98fb-8cd347ef4ac2 | c6a57c76-a3ea-42cc-9cfb-7eb8773b9436 |
| dev-ab-llm | f8f9b203-66ae-43e1-9d37-82e76d26b762 | b867b809-5d2b-4e75-935f-1ed6086432c3 |

Also present: the organiser base `2f14ba80-…`, the baseline minimal agents (slots brief-a and brief-a+brief-b), and the
exp01 agent `1ee05139-…`. Saved specs from LLM builds are `runs/dev/spec-a-llm.json` and `runs/dev/spec-ab-llm.json`.
Redeploy them with `--spec` to skip the LLM.

## Next steps (in order)

1. `make verify` → commit the uncommitted fixes above.
2. Redeploy all three dev agents with the current code (the `--spec` builds are quick):
   - `.venv/bin/python builder/build.py kit/briefs/brief-a.md kit/tools/openapi.json --spec tests/fixtures/spec_a.json --slot dev-a-fixture`
   - `... brief-a.md ... --spec runs/dev/spec-a-llm.json --slot dev-a-llm`
   - `... brief-a.md brief-b.md ... --spec runs/dev/spec-ab-llm.json --slot dev-ab-llm`
   - Note: specs saved before `6393c16` already contain the `promise_window.non_business_day/after_max` fields.
3. 3-rep runs: dev-a-fixture `--brief A`, dev-a-llm `--brief A`, dev-ab-llm `--brief B`. Also dev-ab-llm `--brief A` (the
   A+B agent must not regress on A). Log each in the Score log and read every failure transcript (`scripts/show_run.py --calls`).
4. **Phase 3 robustness:**
   - `--style pieces|corrects|talkative|asks_back|in_words` runs on A and B.
   - Build the synthetic variants with `--dry`: `tests/fixtures/briefs/variant-{c,r}.md` + `.openapi.json`.
   - Write a raw-material rewrite of Brief A (`tests/fixtures/briefs/raw-a/`) and score it on the PUB-A cases.
5. **Phase 4 submission hardening:**
   - Fresh-clone timed build. Trace completeness and redaction check.
   - A runbook for Sun 17:00–20:00 UTC: run the builder on each hidden brief with `| tee traces/hidden-N.log`, then
     `--export submission/hidden-N.workflow.json`, then commit, then send the form.
   - **Ask the user:** GitHub repo visibility (public, or private with organiser access) and the team name for the form.
6. Freeze target about Sun 15:30 UTC (tag `freeze-final`). After 17:00 UTC: generic bug fixes only, no hidden-brief content.

## Open questions / risks being tracked

- **Sandbox output truncation.** It is a platform flake that gets worse under load. Watch for `function_call_error`
  "Sandbox did not return a parseable result" in transcripts, and check whether `6393c16` makes it go away.
- **Organiser re-run.** Their run of our builder needs an OpenAI key. The env vars are documented in README. Raise
  this with the user before submission.
- **Untested platform behaviour:** pre-hook `vars` writes reaching the post-hook, and the `_args` persistence used for
  note reasons in finalize. Watch the B runs.
