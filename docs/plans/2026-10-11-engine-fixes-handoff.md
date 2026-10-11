# Engine-fixes chat: context-save handoff (Sun 11 Oct 2026, 13:45 UTC; previous save 12:05 UTC)

**If you are a restored session of the ENGINE-FIXES chat, read in this order:** `CLAUDE.md` ->
`docs/plans/2026-10-11-engine-fixes-brief.md` (your original brief) -> this file ->
`docs/plans/2026-10-11-engine-fixes-log.md` (its "READ FIRST" section, then the sections you need) ->
`docs/plans/2026-10-11-path-cases-sim-handoff.md` (latest hand-off to the Simulation Developer). Run
`date -u` and `git status` first. This file is the engine-fixes chat's handoff; `docs/WORKING_STATE.md`
belongs to the simulation chat and this chat must not edit it.

## Role and binding rules

- You fix the builder ("the engine"). The **Simulation Developer** (sim chat) owns all simulations,
  `run_cases`, deploys, Freya slots, queue changes, `docs/WORKING_STATE.md` and
  `docs/plans/2026-10-11-overnight-report.md`. The user relays between chats.
- Never run simulations, `run_cases`, deploys or `builder/build.py` without `--dry`. `--dry` builds
  call only the builder LLM; `--dry --spec <saved spec>` calls nothing. No Freya calls of any kind.
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

**Standing user instructions (latest first):**
- ~13:00 UTC: Simulation resumes **eng.4** validation. Keep `cand-eng.8` and all existing tags unchanged;
  **do not create the eng.7-based variant** of the closing fix yet (it cherry-picks cleanly onto a985076,
  checked with merge-tree, nothing made). Regression cases stay isolated from the simulation queue. No
  engine changes, deployments, Freya calls or queue changes.
- 12:05 UTC: Fix 2 stays deferred; Fix 3 is not implemented. The user forwards findings to the
  Simulation Developer.

## Deadlines (UTC, Sun 11 Oct)

- Organizer: hidden briefs open 17:00 (`docs/reference/hackathon_page.md:196`); submission closes
  20:00. After 17:00: "you may fix a bug in your builder. You may not write anything from a final brief
  into it: no rule, no value, no name" (`kit/README.md:73`; page `:100`, `:277`).
- Internal (not organizer rules; `docs/plans/2026-10-11-overnight-plan-v2.md:299-303`): 14:30 RUNBOOK
  rehearsal, 15:30 freeze tag `freeze-final` (sim chat / user). CLAUDE.md adds the stricter "only generic
  bug fixes" wording after 17:00.

## State at save

`main` HEAD = 02fb857 (sim chat commits interleave; this chat's latest on main: ce9e277 hand-off doc, d07fb7f
and 2ec3406 / cf24e17 log sections). All engine-fixes worktrees clean.

| Tag / branch | Commit | Branch | Contents | Tests |
|---|---|---|---|---|
| cand-final.1 | ca80d52 | (sim chat's) | base of all work | 820 |
| cand-eng.4 | cfa4d9d | `cand-eng-safe` | items 1, 2, 4, 5 (3 of 6 parts) + both review rounds' fixes + variant-e fixtures | 859 |
| cand-eng.5 | 27f5647 | `cand-eng` | cand-eng.4 + item 3 (PUB-12 multi-product FACTS paragraph) | 861 |
| cand-eng.6 | a170935 | `cand-eng-fix1` | cand-eng.4 + Fix 1 (per-product sentence; extraction prompt + check_spec guard) | 861 |
| cand-eng.7 | a985076 | `cand-eng-fix1-on5` | cand-eng.5 + Fix 1 | 863 |
| **cand-eng.8** | **4267bb0** | `cand-eng-closing` | cand-eng.6 + audit test (dcd9749) + closing-line fix | 869 |
| (branch) | dcd9749 | `audit-fix1-endings` | cand-eng.6 + strict-xfail audit test only | 862 + 1 xfail |
| (branch) | 898223d | `cases-eng8-paths` | off main 2ec3406: transfer-path regression cases v2 (fixtures only) | 807 |

cand-eng.1-.3 are superseded intermediate tags (kept). Worktrees from earlier sessions are under scratchpad
`.../0ff87ea7-15f5-4256-b709-1c128c353294/scratchpad` (`wt-eng`, `wt-safe`, `wt-eng6`, `wt-eng7`, frozen
`wt-eng1/2/3/5/6f`). This session's, under `.../cebcf16d-0321-4181-b559-125cc9c8acdd/scratchpad`: `wt-audit`
(`cand-eng-closing`), `wt-cases` (`cases-eng8-paths`). Scratchpads may be cleaned by the OS; everything
essential is committed.

## What is done (details and evidence in the log)

- Items 1-5 and Fix 1 as before (cand-eng.4-.7; see the log). Fix 1 side effect: `stage_rules.negotiate`
  ~4.5x larger on fresh builds.
- **Fix 1 semantic audit (12:21-12:36):** 10 fresh eng.6 extractions vs briefs, 4 auditors + verifiers.
  Finding 1 CONFIRMED (high): closing rows repeat mid-call lines (support offer question, sympathy,
  "Can I help you first?") because ENDINGS say them in the goodbye; 6/16 fresh with a question, 9/16 incl.
  sympathy-only, 0/13 before Fix 1. Finding 2 plausible (medium, NOT addressed by user instruction): the
  vague-period "propose the deadline" stage_rule next to the PUB-07 DATES guard. 9 candidates refuted.
- **cand-eng.8 (closing-line fix, render-time, extraction prompt unchanged):** `spec.early_lines` (a
  question, or a sentence shared by a transfer and a non-transfer ending that is not common to every ending
  of one step) + `render._split_early_lines` (moves them to the step's rules: "SAID BEFORE THE CUSTOMER
  ANSWERS ... once ... never again in the goodbye"); trace STEP line per affected ending. Evidence: rule
  hits exactly the 9 defective of 66 saved specs; 62/71 saved-spec renders byte-identical to eng.6, the 9
  others differ only in ENDINGS + the block; 5 fresh `--dry` builds rc=0, fix fired in 3/5 (incl. Brief
  A), paid sentence kept 5/5; adversarial review 0 material (2 refuted low).
- **Transfer-path regression cases v2** (`cases-eng8-paths` = 898223d, isolated): HA-A (PUB-05), HA-B
  (PUB-13), HU-A (PUB-01), HU-PRE (PUB-06), HU-B (PUB-12); expected `transferred`/`support` or
  `transferred`/`human`, no promises/notes/callbacks. Brief-only derivation (2 blind derivers +
  reconciler), then false-failure revision (neutral goodbyes, well-wishes, transfer announcements, one
  transfer confirmation allowed; help-first required once; rule 30 vs 42 order unresolved and not
  enforced). Stand-in judges (Claude, not Freya's): 52/52 verdicts as intended. Never run on Freya.
- **Simulation hand-off** `docs/plans/2026-10-11-path-cases-sim-handoff.md` (ce9e277): fixtures, expected
  ledgers, sources, ambiguities; E1 (eng.4 vs eng.8 overall, cannot isolate the fix) vs E2 (same ab4 spec
  via `--spec` on eng.6 and eng.8, isolates it); cost 15 calls per candidate (E1 30, E2 30); always pass
  `--slot` (the default slot can overwrite a workflow under validation).

## Open, deferred, unmeasured

- **Unmeasured until Freya runs:** every cand-eng behaviour incl. cand-eng.8; whether the model says the
  moved lines once at the right moment; the 5 path cases with the real judge; items 1, 2, 4 and floor
  rounding (variant-e cases); identity all-at-once cannot run on the kit mock; paid sentence (PUB-12) and
  "the rest stays overdue" (PUB-06).
- **cand-eng.8 limits:** active only when the extraction has the pattern (12/21 fresh builds); misses a
  repeated line in a single ending or a statement-form help-first (0 seen in 89 specs); optional hardening
  (closing line missing from one all-phase row, 0/89) not done; inherits all eng.6 risks.
- **Finding 2 (PUB-07 vague period)** unchanged by user instruction; validate PUB-07 x3 on fresh .6/.8.
- **Fix 2 (too-much own date) DEFERRED** with 3 unresolved design issues; case inventory (variant-f/g/h,
  F1-F3, G1, H1, H2) is a proposal with unresolved expectations.
- **Fix 3 (overdue sentence) NOT implemented:** present in rendered `stage_rules` in 16/16 fresh builds.
- Item 5 parts not done: identity entry "Please go on." (call 29041b61), pre-question sentence placement,
  first retry after the 30-min guard. Open LOW review findings (all-at-once corner) listed in the log.
- Not done by instruction: eng.7-based variant of the closing fix.

## Next steps after restore

1. Read as above; confirm `git status` shows only other chats' files on `main`; confirm tags
   (`for t in cand-eng.4 cand-eng.5 cand-eng.6 cand-eng.7 cand-eng.8; do git rev-parse --short "${t}^{commit}"; done`,
   expect cfa4d9d 27f5647 a170935 a985076 4267bb0; `git rev-parse --short` takes ONE revision).
2. Do no implementation and no extraction runs until the user relays Simulation Developer results or a
   new instruction.
3. When results arrive: for every case that differs from the base arm, read the call's transcript and
   FACTS before proposing anything; propose fixes as new, separately tagged candidates for approval.
4. After 17:00, follow the organizer rule above for any change.

## Evidence and tools (scratchpads; read-only aids)

Earlier session (`.../0ff87ea7-.../scratchpad`): `scope/*` scripts, `fresh/`, `fresh6/` (eng.6 fresh
extractions), `scope/perturbed/`. This session (`.../cebcf16d-.../scratchpad`): `pack/` (audit evidence
packs), `eng6/` (git-archive of a170935), `fresh8/` (5 eng.8 fresh `--dry` builds), `mkpack.py`,
`rendercmp.py` (eng.6 vs eng.8 render hashes over all saved specs), `dumpwf.py`, `derived.json` /
`revised.json` (case derivations). Workflow journals (under `~/.claude/projects/.../subagents/workflows/`):
audit `wf_edb0677f-810`, eng.8 review `wf_49a2106f-aed`, case derivation `wf_5ca712e9-299`, case v2
review `wf_b3e4f25f-720`; earlier: review 1 `wf_dcf7f97f-cd8`, review 2 `wf_b03ec5b4-51e`, blind
derivation `wf_e03c9060-5bf`.

Shell pitfalls seen this session (zsh): `"$t:src/..."` is parsed as a `:s` modifier, use `"${t}:src/..."`;
an unquoted heredoc runs backticks in Markdown text, use `<<'EOF'`.

## Restart prompt (as the user started this chat)

"You are the ENGINE-FIXES chat for the Freya hackathon builder. Read CLAUDE.md, then
docs/plans/2026-10-11-engine-fixes-brief.md, then the top of docs/plans/2026-10-11-overnight-report.md.
Check `date -u` first. Binding: another chat owns ALL simulations and deploys. You never run simulations,
run_cases or non --dry builds. Work only in your own worktree ... Log your work in
docs/plans/2026-10-11-engine-fixes-log.md, and hand fixes over as tags (cand-eng.N) with a measurement
request." On restore, add: "then read docs/plans/2026-10-11-engine-fixes-handoff.md".
