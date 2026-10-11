# Engine-fixes chat: context-save handoff (Sun 11 Oct 2026, 12:05 UTC)

**If you are a restored session of the ENGINE-FIXES chat, read in this order:** `CLAUDE.md` ->
`docs/plans/2026-10-11-engine-fixes-brief.md` (your original brief) -> this file ->
`docs/plans/2026-10-11-engine-fixes-log.md` (its "READ FIRST" section, then the sections you need). Run
`date -u` and `git status` first. This file is the engine-fixes chat's handoff; `docs/WORKING_STATE.md`
belongs to the simulation chat and this chat must not edit it.

## Role and binding rules

- You fix the builder ("the engine"). The **Simulation Developer** (sim chat) owns all simulations,
  `run_cases`, deploys, Freya slots, queue changes, `docs/WORKING_STATE.md` and
  `docs/plans/2026-10-11-overnight-report.md`. The user relays between chats.
- Never run simulations, `run_cases`, deploys or `builder/build.py` without `--dry`. `--dry` builds
  call only the builder LLM; `--dry --spec <saved spec>` calls nothing.
- Work only in your own worktrees and branches. On `main`, commit only engine-fixes docs, by explicit
  path (`git commit -- <path>`); other chats leave uncommitted files on `main` (`dashboard/*`,
  `docs/WORKING_STATE.md`): never stage or touch them.
- Before every commit: `uv run ruff format --check src tests && uv run ruff check src tests &&
  uv run pytest -q` (never `make verify`). Each bug gets a regression test that fails on the old code.
- Generic only (CLAUDE.md rule 11): no Brief A/B values in the builder; never invent bank policy.
- Candidate tags are never moved; adoption or merging needs the user's separate approval.
- Promotion of any candidate needs strict 3/3 on fresh builds; 1 rep is only a smoke test; any
  difference from the base arm is investigated, never dismissed as noise.
- Saved-spec render equivalence proves only that render code is unchanged, never behavioural
  equivalence: an extraction-prompt change reshapes every fresh build (the Fix 1 lesson).
- When a requested fix turns out to be already represented, stop and report the evidence before adding
  anything.

**Standing user instruction (12:05 UTC):** no further implementation or extraction runs. Wait for the
Simulation Developer's validation of cand-eng.6/.7 (as broad behaviour changes: full A and B sets,
PUB-06 speech). Fix 2 stays deferred; Fix 3 is not implemented. The user forwards findings to the
Simulation Developer.

## Deadlines (UTC, Sun 11 Oct)

- Organizer: hidden briefs open 17:00 (`docs/reference/hackathon_page.md:196`); submission closes
  20:00. After 17:00: "you may fix a bug in your builder. You may not write anything from a final brief
  into it: no rule, no value, no name" (`kit/README.md:73`; page `:100`, `:277`).
- Internal (not organizer rules; `docs/plans/2026-10-11-overnight-plan-v2.md:299-303`): 12:00
  candidate-change cutoff (passed: cand-eng.6/.7 tagged 11:46/11:48), 12:30 final validation (sim chat;
  Freya was reported down around 11:30), 14:30 RUNBOOK rehearsal, 15:30 freeze tag `freeze-final`.
  CLAUDE.md adds the stricter "only generic bug fixes" wording after 17:00.

## State at save

`main` HEAD = d38d951 (engine-fixes log commits: 9742fe8 ... d38d951). All engine-fixes worktrees clean.

| Tag | Commit | Branch | Contents | Tests |
|---|---|---|---|---|
| cand-final.1 | ca80d52 | (sim chat's) | base of all work | 820 |
| cand-eng.4 | cfa4d9d | `cand-eng-safe` | items 1, 2, 4, 5 (3 of 6 parts) + both review rounds' fixes + variant-e fixtures | 859 |
| cand-eng.5 | 27f5647 | `cand-eng` | cand-eng.4 + item 3 (PUB-12 multi-product FACTS paragraph) | 861 |
| cand-eng.6 | a170935 | `cand-eng-fix1` | cand-eng.4 + Fix 1 (per-product sentence; extraction prompt + check_spec guard) | 861 |
| cand-eng.7 | a985076 | `cand-eng-fix1-on5` | cand-eng.5 + Fix 1 | 863 |

cand-eng.1-.3 are superseded intermediate tags (kept). Worktrees (all under the scratchpad
`/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/0ff87ea7-15f5-4256-b709-1c128c353294/scratchpad`;
may be cleaned by the OS, everything essential is committed): `wt-eng` (cand-eng), `wt-safe`
(cand-eng-safe), `wt-eng6` (cand-eng-fix1), `wt-eng7` (cand-eng-fix1-on5); frozen detached copies used for
fresh builds: `wt-eng1` (.1), `wt-eng2` (0267b60), `wt-eng3` (d54a850), `wt-eng5` (.5), `wt-eng6f` (.6).

## What is done (details and evidence in the log)

- Item 1 (HIGH) all-at-once `verify_identity`: shape decided by question keys being request fields;
  checks and post-hook for that shape; 2 review rounds' fixes.
- Item 2 (HIGH) a brief's own "too much" rule: spec `too_much {offer: attempt_1|separate, date_expr}`.
- Item 3 (Brief B PUB-12): FACTS paragraph after the opening question (cand-eng.5/.7 only).
- Item 4 (MED) "this <weekday>": spec `calendar.this_weekday`.
- Item 5 (LOW), 3 of 6 parts: percentage floor in whole cents half-up; no hint read when the brief
  lists none; stdout flush before END.
- Fix 1: a per-product sentence (already paid) in its row, not `unmodeled`; fresh extractions 12/12
  multi-product (baseline 10/16). Side effect: `stage_rules.negotiate` ~4.5x larger on fresh builds.
- Fixtures: `tests/fixtures/briefs/variant-e.md` + `tests/fixtures/cases/eng-variant-e.json` (4 cases,
  expectations blind-derived 2/2 + author).
- For A, A+B and raw-A on saved specs: prompts byte-identical to cand-final.1 and FACTS output
  identical over 8000 states. This says nothing about fresh-build behaviour for cand-eng.6/.7.

## Open, deferred, unmeasured

- **Unmeasured until Freya runs:** every cand-eng behaviour; items 1, 2, 4 and floor rounding (variant-e
  cases); identity all-at-once cannot run on the kit mock at all; whether the agent says the paid
  sentence (PUB-12) and "the rest stays overdue" (PUB-06); absence case for the overdue sentence.
- **Fix 2 (too-much own date) DEFERRED** with 3 unresolved design issues (fallback to attempt 1's date
  is unsafe; sentence proximity is not semantic scope; counting cases need exact expectations). Do not
  add provenance fields or fallback without a separate review. Case inventory (variant-f/g/h, F1-F3, G1,
  H1, H2) is a proposal with unresolved expectations.
- **Fix 3 (overdue sentence) NOT implemented:** present in rendered `stage_rules` in 16/16 cand-eng.6/.7
  fresh extractions; a FACTS-line placement change is ready to design only if Freya shows misses.
- Item 5 parts not done: identity entry "Please go on." (call 29041b61), pre-question sentence placement,
  first retry after the 30-min guard.
- Open LOW review findings (all-at-once corner): listed in the log tables.

## Next steps after restore

1. Read as above; confirm `git status` shows only other chats' files on `main`; confirm tags as in the
   table (`git rev-parse --short cand-eng.4` ... `.7`).
2. Do no implementation and no extraction runs until the user relays Simulation Developer results or a
   new instruction.
3. When results arrive: for every case that differs from the base arm, read the call's transcript and
   FACTS before proposing anything; propose fixes as new, separately tagged candidates for approval.
4. After 17:00, follow the organizer rule above for any change.

## Evidence and tools (scratchpad; read-only aids)

`scope/render_all.sh <worktree> <outdir>` (7 `--dry --spec` renders), `scope/diffpaths.py`,
`scope/facts_equiv.py <worktree> <spec>` (8000-state FACTS hash), `scope/checks2.py` (check_spec on all
saved specs with their own APIs), `scope/case_facts.py`, `scope/guard_fp2.py`, `scope/score_fresh6.py`;
fresh extractions in `fresh/` and `fresh6/`; perturbed briefs and saved specs in `scope/perturbed/`.
Workflow journals: review 1 `wf_dcf7f97f-cd8`, review 2 `wf_b03ec5b4-51e`, blind derivation
`wf_e03c9060-5bf` (under `~/.claude/projects/.../subagents/workflows/`).

## Restart prompt (as the user started this chat)

"You are the ENGINE-FIXES chat for the Freya hackathon builder. Read CLAUDE.md, then
docs/plans/2026-10-11-engine-fixes-brief.md, then the top of docs/plans/2026-10-11-overnight-report.md.
Check `date -u` first. Binding: another chat owns ALL simulations and deploys. You never run simulations,
run_cases or non --dry builds. Work only in your own worktree ... Log your work in
docs/plans/2026-10-11-engine-fixes-log.md, and hand fixes over as tags (cand-eng.N) with a measurement
request." On restore, add: "then read docs/plans/2026-10-11-engine-fixes-handoff.md".
