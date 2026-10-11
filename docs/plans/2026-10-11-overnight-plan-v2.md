# Overnight plan v2 (APPROVED), Sun 11 Oct 2026

**Status.** The user approved the plan at about 00:35 UTC, with the conditions below. Execution began and was
stopped at 00:40 UTC for a context save. Pick it up at **"Progress"** and then **M0**.

**Source.** Two read-only review workflows (13 + 5 agents, each fact-checked) and a review by the user's independent
advisor. The decision is in the Decision log of `docs/hackathon_notes.md` (11-10 00:35).

## The user's conditions (binding)

1. **Promotion.** Any newly failing case that is agent-caused or unexplained blocks promotion of a candidate, fresh
   builds included. "Within one passing case" is diagnostic only.
2. **Precedence.** The precedence change stays isolated on its own branch until it passes all three gates:
   - variant-C extraction correct in **3/3** fresh runs;
   - the negative extraction checks;
   - fresh-build regression validation.

   If any gate fails, keep the existing candidate.
3. **Export diffs.** A field that only the platform export has may be ignored only once it is **verified to be a
   harmless platform default**.
4. **B-date.** Probes and implementation are **deferred tonight**.
5. **Call cap.** 340 calls is the **absolute** overnight cap, retries included. Cut optional work to stay under it,
   and keep the Sunday reserve.
6. **Priority when time runs short.** The multi-product baseline (M2) and the fresh raw-A and A+B validations
   (M4, M5) come before any optional work.

## Approach

- **Ship baseline:** F2 plus the PUB-06 winner W (G1, G2 or none), backed by measurement.
- **Not tonight:**
  - full B (code records the confirmed tuple, or code-owned offers);
  - C;
  - B-date.
- **Optional:** the bounded precedence correction, offline and gated.
- **Reasons (evidence in the Decision log):**
  - In 18 of 18 local transcripts the `create_promise` arguments equal the last read-back the customer confirmed.
  - The dominant failure is PUB-06 offer sequencing: 6 of 12 calls passed since F1, and never 3/3.
  - B's per-turn Freya mechanisms are documented but not verified.
  - Code control turns an off-schema rule in a hidden brief into a hard failure of every case in that family.

## Verified provenance (deploy logs, `.freya-agents.json`)

| Slot | Workflow / agent | Version | Build | Spec | Measured |
|---|---|---|---|---|---|
| dev-a-llm2 (A control) | 7cfc34a8-5b97-4bfc-a3a8-b4e884c4dd96 / 2485fc27-f1d4-47e1-ab89-a1a86fd12a87 | v8, 22:25 UTC | 71add36, clean; code identical to F2 bd4da7c | `runs/dev/spec-a-llm.json` (sha256 2ec7073c…) | styled-a 8/10 (`runs/dev/r3/styledA-a2-bd4da7c.json`); raw PUB-03 2/3, PUB-06 2/3 |
| dev-ab-llm (A+B control) | f8f9b203-66ae-43e1-9d37-82e76d26b762 / b867b809-5d2b-4e75-935f-1ed6086432c3 | **v14**, 22:18 UTC | bd4da7c (F2), clean | `runs/dev/spec-ab-llm-c45758f.json` (6346c4e6…) | **never** |
| dev-ab-llm, previous | same | v13 | c45758f, fresh extraction | became spec-ab-llm-c45758f.json | styled-ab-a 6/10. Last measured A+B |
| exp-g1-a | 5f39ed9a-a352-4262-ad8d-25a8d57db99f / 31f79439-bbcd-4088-91fa-8145d2e852e4 | v1 | b86228c **dirty** (G1 patch) | spec-a-llm | PUB-06 talkative 2/3 |
| exp-g2-a | 4d64b871-4db5-4259-ad6e-0b6e884c9b42 / efb690fd-ce90-4cad-8eda-6ca98517b51b | v1 | b86228c clean, plus the exp07 runtime variant `offerdate` | spec-a-llm | never |
| exp-f3-a | c2a1e221-f621-46b0-9870-856f7e0ce464 / 35098a88-caf7-4cbe-9378-0b2cbadeaaae | v1 | a069dd2 | spec-a-llm | PUB-06 1/3; PUB-07 raw 5/6 |
| dev-raw-a | 7286c0bd… / eb321c47… | — | about fe1d7ef (stale) | not saved | 10/10, stale |
| dev-variant-r / dev-variant-c | e33f573b… / 1231d51c…; 8a2cee93… / 1f901a16… | — | dcb3915 | `runs/dev/spec-variant-{r,c}-dcb3915.json` | never. variant-c's API is a fake URL, so it is offline only |

**Code identity:**
- 71add36 = bd4da7c (F2).
- b86228c = a069dd2 (F3) = HEAD's builder code.
- Still to check before the G1/G2 renders: `git diff --stat b86228c a01a17c -- src builder` should be empty.

**Version numbers do not identify content:** the aa94ccb and c45758f deploys both reported v6. Compare content.

## Progress (00:40 UTC)

**Done:**
- M0, part 1:
  - credits read: **433.89** at 00:37 UTC, logged in `runs/credits_log.jsonl`;
  - at HEAD a01a17c: `ruff format --check` and `ruff check` clean, **769 passed**.
- Tags `cand-f2` (bd4da7c) and `cand-f3` (a069dd2).
- Worktrees in the old session's scratchpad. They may be gone after a restart; the branches stay in git.
  - `wt-g1`: branch `cand-g1` at a01a17c.
  - `wt-g2`: branch `cand-g2` at a01a17c.
  - `wt-f2`: detached at cand-f2.
  - Each has `.env` and `.freya-agents.json` symlinked to the main tree.
- G1 and G2 edits made in their worktrees but **not tested and not committed**. Saved as patches:
  - `runs/dev/r4/cand-g1-uncommitted.patch`: the G1 facts.py patch (blob afb8860 verified), plus
    `tests/test_codegen_integration.py`, where the test now asserts the too-much line is present;
  - `runs/dev/r4/cand-g2-uncommitted.patch`: the render.py ATTEMPTS sentence, plus an assertion in
    `tests/test_render.py`.

**Next:** the rest of M0 below.

## Execution mechanics

**Shell and environment:**
- Use bash, not zsh.
- Source `.env` with `set -a; . ./.env; set +a`.
- Never run `make verify`: it runs `ruff format .`, which writes files, including the other session's dashboard
  files. Use `uv run ruff format --check src tests scripts builder experiments && uv run ruff check … && uv run pytest -q`.

**Worktrees:**
- Recreate a missing one with `git worktree add <dir> cand-g1` (or `cand-g2`, `cand-f2`).
- Apply its patch with `git apply runs/dev/r4/cand-gN-uncommitted.patch`.
- Symlink `.env` and `.freya-agents.json` into it. `platform.STATE_FILE` is `<code root>/.freya-agents.json`, so
  without the link a worktree build would create duplicate slots.
- Run tests with `uv run` *inside* the worktree. First check that
  `uv run python -c "import freya_builder;print(freya_builder.__file__)"` points into the worktree; the main
  `.venv` may hold an editable install of the main `src` (unverified).
- Then `git commit`, tagged `cand-g1` / `cand-g2`.

**Git:**
- Don't change `main` overnight except `docs/`, the new case files in `tests/fixtures/cases/` and
  `tests/fixtures/briefs/ab-single.md`.
- Commit with explicit paths. The other session commits `dashboard/` concurrently; on an `index.lock`, wait and retry.

**Simulations:**
- Command: `.venv/bin/python scripts/run_cases_retry.py <agent> --cases <file> --reps 1 --rerun-if-slow 1 --out runs/dev/r4/<name>.json`.
- Never pass `--style` with a styled file: it overrides every per-case style.
- Never pass `--brief` with a file that mixes A and B cases.
- One case per id per simulation; duplicate ids collapse into one call.
- Run arms rep by rep, interleaved: G1 r1, G2 r1, F2 r1, G1 r2, …
- Use a small bash queue runner in the scratchpad: pop "name agent casefile", run, append to the call ledger.
- **Count every call**, discarded slow reps included, in `runs/dev/r4/calls.tsv`.

**Provenance sidecar:** `runs/dev/r4/<name>.meta.json` with slot, agent, workflow version, build sha, spec sha256,
case-file sha256, reps and time. The `--out` JSON records none of these.

**Export verification, before any comparison:**
1. `GET /api/v2/versions/workflow/{id}`: the newest version must equal the trace's version and be published.
2. `freya.export_workflow(id, runs/dev/r4/exports/<slot>.json)`.
3. A local `--dry` render of the claimed commit and spec into `runs/dev/r4/renders/`, run from the matching worktree:
   `python3 builder/build.py <brief(s)> kit/tools/openapi.json --spec <spec> --dry > R.json`.
4. Diff: every path in the render must exist in the export with an equal value.
   - Ignore the wrapper fields `workflow_id`, `agent_id` and `updated_at` (check them against `.freya-agents.json`).
   - Ignore `agent_config`, but check that `llmConfig` is experimental-5 where the kit sets it.
   - A path only the export has is ignorable **only** if its value is empty, null, false or a known default.
     Earlier export-only names: mode, role_message, truncation_*, interruptible, assertions, extraction_schema,
     response_mapping, suppress_tool_results, return_to_previous_on_interrupt, task_message, on_enter*,
     max_turn_transition, tools, max_node_turns, description, passthrough*, pre_actions,
     disable_inactivity_monitor.
   - Any other name, or any non-default value: investigate.
   - Mismatch: rebuild from committed code into a **new** exp slot and record why.

**Newly failing cases** (control CTL and candidate CAND, both with 3 reps per id):
```
jq -n --slurpfile c CTL.json --slurpfile k CAND.json '($c[0].final|map({key:.id,value:.})|from_entries) as $C
 | $k[0].final[] | select(.pass==false and $C[.id].pass==true) | {id, ctl:"\($C[.id].passes)/\($C[.id].runs)", cand:"\(.passes)/\(.runs)"}'
```
- When the reps ran as separate `--reps 1` files, merge them per id first.
- Read every failing call with `scripts/show_call.py <call_id>`.
- Classify each one as agent / judge-policy / ledger / honesty / simulator / platform / unexplained.

**Scores:** raw strict scores are never edited. Adjusted readings go in their own column, need a read transcript,
and can justify only one matched re-run.

## Must-finish (simulation track, in order). Budget 192 calls (162 if W = F2)

### M0. Preflight (finish it)

1. **G1 and G2 as code.** In each worktree: lint, then pytest; commit; tag `cand-g1` / `cand-g2`.
2. **Case files** (committed on main before their first run; values copied verbatim, styles only added):
   - `tests/fixtures/cases/block-p06.json`: PUB-06 [talkative], PUB-07 [asks_back], PUB-09 [talkative],
     PUB-03 [corrects], each from `kit/public-test-set.json` plus `"style"`.
   - `tests/fixtures/cases/styled-ab-all.json`: `styled-ab-a.json` followed by `styled-b.json` (13 distinct ids).
   - `tests/fixtures/briefs/ab-single.md`: `kit/briefs/brief-a.md`, a blank line, then `brief-b.md`, unchanged.
   - Run pytest; `tests/test_fixtures.py` checks the case files.
3. **Export verification** (above) for dev-a-llm2 v8, dev-ab-llm v14, exp-g1-a and exp-g2-a.
   - Renders: F2 from `wt-f2` (spec-a-llm and brief-a; spec-ab-llm-c45758f and briefs a+b); G1 from `wt-g1`; G2
     from `wt-g2`, all with spec-a-llm.
   - A G1 or G2 render that equals its export means the existing agent equals the committed code.
4. Check that nothing is running: no local run_cases process, and a short first simulation does not print "another
   simulation is running".

### M1. Bounded PUB-06 comparison (36 calls, about 25 min)

**Arms:** exp-g1-a (G1), exp-g2-a (G2) and dev-a-llm2 v8 (F2 control). File `block-p06.json`, `--reps 1` × 3 per
arm, interleaved.

**Rule:**
- An arm qualifies only with PUB-06 at 3/3 **and** no newly failing agent-caused or unexplained case against F2 in
  the same block.
- One arm qualifies: it becomes W.
- Both qualify: run O2 if the budget allows; if still tied, or if O2 is skipped, choose G2 (the smaller change; FACTS
  untouched).
- Neither qualifies: W = F2, and the PUB-06 text line is **closed for the event**. No new PUB-06 variants tonight.

### M2. A+B baseline on F2 v14 (48 calls, about 28 min; may run while W is being finalised)

- `styled-ab-all.json` ×3, then `tests/fixtures/cases/styled-extra-b.json` ×3. No `--brief`.
- Report only. It is the matched control for M5.
- Any wrong-date ledger on A+B goes to the top of the morning list.

### M3. Guard W on A (30 calls; skip if W = F2)

- W's saved-spec agent (exp-g1-a or exp-g2-a) on `styled-a.json` ×3.
- Matched against F2 v8's `runs/dev/r3/styledA-a2-bd4da7c.json` (not concurrent).
- Any newly failing agent-caused or unexplained case: W = F2.

### M4. Fresh raw-A build of the final W (30 calls)

1. From W's worktree:
   `python3 builder/build.py <R>/tests/fixtures/briefs/raw-a.md <R>/kit/tools/openapi.json --slot exp-raw-w --save-spec <R>/runs/dev/r4/spec-raw-w.json 2>&1 | tee <R>/runs/dev/r4/build-raw-w.log`
2. Then `styled-a.json` ×3, matched against M3 (or v8 when W = F2).
3. Diff the saved spec against spec-a-llm.json to attribute any extraction-caused failure.

### M5. Fresh single-file A+B build of W (48 calls)

1. `build.py <R>/tests/fixtures/briefs/ab-single.md <R>/kit/tools/openapi.json --slot exp-ab1-w --save-spec <R>/runs/dev/r4/spec-ab1-w.json`
2. Then `styled-ab-all.json` ×3 and `styled-extra-b.json` ×3, matched against M2.
3. The W effect and the fresh-extraction effect are confounded here; attribute failures from the transcripts.

**For M4 and M5:** any newly failing agent-caused or unexplained case blocks W's promotion and goes to the top of
the morning list. Count differences are diagnostic only.

**Fallbacks:** candidates go only to new exp slots. dev-a-llm2 v8 and dev-ab-llm v14 are **never** overwritten.
dev-a-llm and voice-test stay untouched.

## Offline (no simulation slot)

**D1/D2 derivation of the O1 cases (must-finish, offline).**
- D1 gets only the brief, the tool API, the case's public account fields, `now` and a scenario intent. It never sees
  `src/`, specs, FACTS, transcripts or the Score log. It writes the script, the expected ledger, checks with concrete
  values, and `derivation{rules, calc}`.
- D2 re-derives blind by another method (plain `datetime` enumeration; never `calendar_core` or `facts.py`).
- Keep only exact matches. Commit the file before its first run. Compare with FACTS only afterwards.
- Ids must be public (they seed the account), and `now` is fixed at Wed 14 Oct 11:00.
- extra-b's checks were edited after results (7d075ac), so re-derive them.

**Precedence correction (optional, isolated), branch `cand-wp` off W.** Review gap 7, variant-c rule 47.
- *The defect:*
  - A promise recorded before an insolvency statement closes `promise_to_pay`; rule 47 requires
    `no_commitment`/`insolvency` (`variant-c.md:105, 126`).
  - The same happens in the refused-then-insolvent mixed case. That is a ledger failure.
  - `spec.py:83` has no "ending wins" condition.
- *The design:*
  - `when: "ending_wins"` in spec.py:83, reusing `row` and `note_reason`.
  - A finalize branch in `facts.py` around :728: `hit = event_row == rule.get("row") or (bool(nr) and any(r == nr for _, r in notes))`.
  - `check_spec` guards:
    - `then` must be `"row"`; the row must exist, include the negotiate phase and have no queue;
    - `note_reason` must be in the note enum and must not be a reason already used by an `all_notes_reason` or
      `first_note_reason_not` entry.
  - One generic sentence in `pipeline.py` around :80: use it ONLY when the specification says a non-transfer ending
    keeps its outcome even after a recorded promise; place it before `promise_recorded`; never for a reason given to
    a single product.
- *Gates* (all required; any failure means revert to W):
  1. `--dry` renders of the saved A and A+B specs, before and after: the only diff is the inlined facts.py text.
  2. Unit tests on finalize (harness at `tests/test_codegen.py:428-453`), with expectations from the variant-c text:
     - rules 33 :85, 47 :105, 49 :110, 50 :111 and the closing :126;
     - scenarios S1 (promise, then insolvency), S2 (P1 promise, P2 open), S2' (the model writes P2's note itself),
       S3 (P1 refused, P2 insolvency), S4 (insolvency before identity), S5/S5b (senior band, without/with a promise),
       S6 (P1 paid, P2 insolvency);
     - unchanged controls: promise + transfer → transferred; promise → promise_to_pay; all paid → already_paid;
       paid + refused → refused;
     - cross-check against `variant-c.answer.json:125`.
  3. Extraction gate (`--dry --save-spec`, builder LLM only):
     - variant-c: **3/3** runs emit exactly the right entry and **no extra** entries (for example none for hardship
       rule 34);
     - A, A+B, raw-A and variant-r: 2 runs each with **zero** `ending_wins`. Hardship wording is the main
       false-positive risk: Brief A rule 32 "still names a date → record the promise", and variant-r.md:290-292.
     - One prompt tightening is allowed, then stop.
  4. Fresh-build regression (O4): repeat M4 and M5 on `cand-wp` into new slots `exp-raw-wp` and `exp-ab1-wp`,
     matched against M4/M5. No newly failing agent-caused or unexplained case.
- *Timing:* it must be committed by 05:00 UTC to get O4; otherwise it waits for the morning. Tag it separately.

**Optional:** other-calendar-day tests that extend `test_codegen.py` (with independent expectations).

## Optional simulations, in priority order, inside the 340 cap

| # | Item | Calls | Gate |
|---|---|---|---|
| O4 | Precedence fresh-build regression | 78 | Only if gates 1–3 pass by 05:00 |
| O1 | D1/D2-agreed date-trap and interaction cases on W (about 8 A ids, plus PUB-11..13) | ~33 | Diagnostic only; no automatic builder change |
| O2 | PUB-06 round 2 | 24 | Only if M1 is tied |
| O3 | variant-r: a 1-call check that the mock accepts `no_contact`/`service_desk`, then about 5 independent cases ×3 | 16 | Stop if the check fails |
| O5 | F2 v8 styled-a re-run as a concurrent control | 30 | Only if M3 or M4 shows a newly failing case |

## Budget and stop conditions

- **Calls:** absolute overnight cap **340, retries and discarded slow reps included**. Sunday reserve: 155 calls for
  the final validation from 12:30 UTC.
- **Credits:** 433.89 at 00:37 UTC; about 0.07–0.09 credits per call. Below 100: stop optional work. Below 60: stop all
  overnight simulations.
- **Time:**
  - No block starts unless its end, with a +40% allowance, falls before 06:00. M4 not started by 04:30: stop and
    report.
  - Halt and report at 08:00 UTC, on any provenance mismatch, or on a dirty tree.
- **Platform:**
  - A STUCK line, or "another simulation is running" for more than 30 min: report only. **No PUT, pause or stop.** Stop
    simulations for the night; offline work continues.
  - Two blocks in a row with platform-invalid reps: pause 15 min. A third: stop.
- **Iterations:** no new PUB-06 variants. Precedence: 1 prompt tightening. Generic conversation fixes wait for the
  morning: at most one change, 09:00–12:00.

## Approvals

- **Granted:**
  - git tags, branches and worktrees;
  - deploys to **new exp slots only**;
  - read-only GETs (credits, versions, exports);
  - the new case files, the single-file A+B brief, tests and sidecars;
  - the budgets above;
  - the precedence correction on an isolated branch.
- **Not granted:** B-date probes or implementation; any PUT, pause or stop of a simulation; overwriting dev-a-llm2,
  dev-ab-llm, dev-a-llm or voice-test; merging candidate code into `main` (waits for the morning review).

## Sunday (UTC)

| Time | Step |
|---|---|
| 08:00 | Review the overnight results with the user; decide W, precedence, and at most one generic fix |
| 09:00–12:00 | At most one change |
| 12:00 | No more candidate changes |
| 12:30 | Final validation, 155-call reserve: fresh raw-A, fresh single-file A+B, variant-r |
| 14:30 | RUNBOOK rehearsal |
| 15:30 | Freeze, tag `freeze-final` |
| 17:00 | `docs/RUNBOOK.md` |

## Corrections to stale records (raw strict values)

- F2 PUB-06 in styled-a was **2/3**, not 1/3.
- F1 PUB-07 is raw **3/6**; 4/6 was the adjusted figure.
- F3 PUB-07 is raw **5/6**.
- "Pre-F1 8/8" pools several styles.
- dev-ab-llm is **v14 at bd4da7c, unmeasured**.
- The "450.8 credits" reading came from an env check at 19:20 UTC (not logged); the logged reading is now 433.89.
- exp06's drift finding (`say_before_end`) predates 92d91ea, and the spoken sentence was stable, so drift is
  unmeasured, not proven.
- "this Friday" was resolved as Saturday 17 Oct three times (276302f; 676e9df r3; F1 r2, `A06r2-15bcbad.txt:90`).
- Credits cost about 0.07 per call; `hackathon_notes.md:322`'s 0.03 is out of date.
