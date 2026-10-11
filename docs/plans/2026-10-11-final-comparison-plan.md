# Final comparison plan: eng.4 vs challenger on fresh builds (PRE-REGISTERED 11 Oct 14:40 UTC, before any run)

User decisions (14:35 UTC): A arm = `raw-a.md`; challenger = Methodology's tagged narrow closing protection if tagged
with green tests by 15:00 UTC, otherwise **eng.8 (4267bb0)**; on a stop-gate halt: keep the rep as raw, health-check,
continue (never repeat or add reps); D8 replaced by the dry-extraction goodbye metric + live path cases. E2 (eng.6
isolation), D8 variants, styled-extra-b, owa-p06-asks, T2-clean and the E4 queue remainder are deferred.
Background and rationale: dossier `docs/reviews/2026-10-11-final-selection-evidence.md` §11; Decision log 14:40 UTC.

## Arms and builds (first live build per arm is the measured build; no rebuilds)

| Arm | Code | A agent (slot) | A+B agent (slot) |
|---|---|---|---|
| eng.4 | cand-eng.4 cfa4d9d (detached worktree, clean) | `tests/fixtures/briefs/raw-a.md` -> exp-eng4-fr | `tests/fixtures/briefs/ab-single.md` -> exp-eng4-fab |
| challenger | **cand-eng.9 = b103e21** (Methodology, tagged 14:37 UTC inside the 15:00 gate: eng.8 + one-condition closing guard in `spec.early_lines`, 875 tests; detached worktree of the explicit sha) | raw-a.md -> exp-ch-fr | ab-single.md -> exp-ch-fab |

Tool API `kit/tools/openapi.json`; `--save-spec runs/dev/r4/spec-<slot>.json`, `--export runs/dev/r4/exports/<slot>.json`.
eng.4 builds 14:34-14:38 UTC: exp-eng4-fr 114 s, exp-eng4-fab 118 s, `git=cfa4d9d dirty=False`, spec check, validation
and smoke PASS, export MATCH (0 changed, 0 render-only, 0 needs-review). eng.9 builds 14:39-14:43 UTC: exp-ch-fr 112 s,
exp-ch-fab 113 s, `git=b103e21 dirty=False`, all checks PASS, export MATCH. **Closing fix: exp-ch-fr INACTIVE draw (no STEP
line); exp-ch-fab ACTIVE draw** (STEP: "I am sorry to hear that." moved out of the transferred_support and
no_promise_hardship goodbyes into the negotiate rules). Record per build: trace `git=<sha> dirty=False`, build seconds, and whether the trace has a STEP line "said before the
customer answers" (the closing fix active in that extraction or not).

## Case sets per arm and round (harness: `run_one.sh` + `suite_once.py` via `plan_run.sh`; `qrun4.sh` not used)

- A+B agent: `tests/fixtures/cases/styled-ab-all.json` (13 cases)
- A agent: `tests/fixtures/cases/styled-a.json` (10)
- A agent: `runs/cases/e1-a.json` = HA-A (PUB-05), HU-A (PUB-01), HU-PRE (PUB-06) from `cases-eng8-paths` 898223d (3)
- A+B agent: `runs/cases/e1-ab.json` = HA-B (PUB-13), HU-B (PUB-12) from 898223d (2), **every round** (amended 14:37
  UTC by the user, before any run: 3 reps per candidate, +8 calls approved)

Each item is one simulation (`--reps 1`): POST maxRetries 0, no reruns because of latency, every attempt recorded
(`runs/dev/r4/<name>.attempts.jsonl`), corrected stop gate (every platform error event; only PUB-10's injected
create_promise failure excused). Path-case ids collide with the styled sets (seed accounts), so they cannot share a
simulation.

## Order (arm order alternates per round to balance platform swings)

eng.4 r1 -> challenger r1 -> challenger r2 -> eng.4 r2 -> eng.4 r3 -> challenger r3; within a round: styled-ab-all,
styled-a, E1-A, E1-AB.
While the challenger is not built, eng.4 r1 runs first. Cut lines: if more than 10 min behind at 16:05 UTC, round 3 of
**both** arms drops the E1-A and E1-AB items (path-case coverage then reported as INCOMPLETE: 2 of 3 reps); never cut
one arm only. No new simulation starts after 16:40 UTC. Decision 16:40-16:55.
Calls: 2 arms x 3 rounds x 28 = 168 (ledger 343 -> 511 of 789).

## Offline, in parallel (Methodology, `--dry`, no Freya): repeated extractions

eng.4 cfa4d9d and the final challenger; raw-a, ab-single, brief-a, variant-c; 3 each per candidate (24 builds); stop by
16:30; keep >= 5 builds' worth of GPT credit. Thresholds for the challenger (eng.4 values recorded alongside):
(a) no question, offer or sympathy line left in any goodbye / ENDINGS "First say": **0 of 12**; (b) paid sentence in its
row in every multi-product render; (c) overdue sentence present for A-derived inputs, absent for B-only; (d) every
build passes validation; (e) build seconds well under 30 min. Fix-fired (STEP line) rate reported.

## Reporting and decision rule

1. Raw strict 3/3 per arm and per case set, nothing excluded (rounds hit by a gate stop stay in).
2. A separate transcript-classified cause table per failure: platform / simulator / agent / mixed (as in
   `docs/reviews/2026-10-11-e4a-styledA-analysis.md`).
3. Only completed, matched rounds are compared; no extra rounds for one arm.
4. The challenger replaces eng.4 only if, on the matched rounds: strict(challenger) >= strict(eng.4) on both agents; no
   case fails for an agent cause on the challenger that passed on eng.4; the PUB-06 overdue sentence is said in at least
   as many calls; E1 shows no agent-caused regression; and the dry battery meets (a)-(e). State whether the live
   challenger builds were "fix active" or "fix inactive" draws.
5. Otherwise eng.4 stays. No automatic adoption: the user decides (D6) and tags `freeze-final`; merged, verified
   commits (main -> eng.4, main -> challenger) are prepared by 16:30 so only `git tag` remains.
