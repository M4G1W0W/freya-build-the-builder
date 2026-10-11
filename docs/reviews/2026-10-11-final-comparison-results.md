# Final comparison results: eng.4 vs eng.9 on fresh builds (11 Oct, 15:49 UTC)

Plan (pre-registered): `docs/plans/2026-10-11-final-comparison-plan.md`. Harness: maxRetries 0, no reruns, every attempt
kept (`runs/dev/r4/C-*.attempts.jsonl`, calls in `runs/dev/r4/final.calls/`). Arms: eng.4 = cand-eng.4 cfa4d9d
(exp-eng4-fr from `raw-a.md`, exp-eng4-fab from `ab-single.md`); eng.9 = cand-eng.9 b103e21 (exp-ch-fr: closing fix
INACTIVE draw; exp-ch-fab: ACTIVE draw). Failure classification: read-only workflow wf_dfefa27b-042 (4 classifiers + 4
skeptics) and transcript reads.

## Platform outage

From about 15:16 UTC the platform's model step stalled every call at the opening (one customer message, then nothing
until the customer hung up at ~62 s). Round 3 of both arms is lost entirely (eng.4 0/28, eng.9 0/28), and so is eng.4's
round 2 path-case item (0/5). Probes: 15:41 stalled; 15:46 one `verify` then a hang-up (not recovery); the first
goodbye item at 15:46-15:48 stalled 0/3. Strict probing (user rule 15:47) continues.

## Raw results (nothing excluded)

| Set | eng.4 per rep (r1, r2, r3) | eng.9 per rep | eng.4 strict r1-2 | eng.9 strict r1-2 | raw strict r1-3 (both) |
|---|---|---|---|---|---|
| A+B styled-ab-all (13) | 10, 13, 0 | 12, 10, 0 | 10/13 (PUB-03, 12, 13) | 10/13 (PUB-01, 07, 12) | 0/13 |
| raw-A styled-a (10) | 10, 8, 0 | 9, 9, 0 | 8/10 (PUB-01, 04) | 9/10 (PUB-03) | 0/10 |
| path cases, A agent (3) | 2, 0, 0 | 2, 3, 0 | 0/3 | 2/3 (HA-A) | 0/3 |
| path cases, A+B agent (2) | 1, 0, 0 | 2, 2, 0 | 0/2 | 2/2 | 0/2 |

## Failure causes (rounds 1-2; separate from the score)

| Arm | Set, rep | Case | Cause | Candidate-specific? |
|---|---|---|---|---|
| eng.4 | A+B r1 | PUB-03 | agent (skeptic-corrected): a complete 3rd DOB "nineteen ninety. Look," treated as unfinished (eng.4 3/3 such misreads; same text in both candidates) | shared code |
| eng.4 | A+B r1 | PUB-12 | mixed: platform "no speakable content" x2, plus simulator and agent details | shared |
| eng.4 | A+B r1 | PUB-13 | simulator: customer hung up 2.2 s after the DOB question | shared |
| eng.4 | raw-A r2 | PUB-01 | platform: `service-failure-llm` (LLM timeouts, Turkish fallback) | - |
| eng.4 | raw-A r2 | PUB-04 | simulator: customer hung up 5.4 s after the DOB question | - |
| eng.4 | path A r1 | HA-A | agent: no thanks/goodbye before the transfer (rule 47) | shared |
| eng.4 | path A r2 | all 3 | platform stall | - |
| eng.4 | path A+B r1 | HU-B | agent: help offered again after the customer insisted | eng.4's extraction draw, not the closing guard |
| eng.4 | path A+B r2 | both | platform stall | - |
| eng.9 | A+B r1, r2 | PUB-12 | mixed: simulator date drift (script "tomorrow" = 15 Oct; customer said 22nd/23rd and confirmed), small agent misses | shared, not an eng.9 regression |
| eng.9 | A+B r2 | PUB-01, PUB-07 | platform: bank returned HTML error pages on create_promise (rule-37 retry then judged "called twice"; PUB-07 service_error) | - |
| eng.9 | raw-A r1, r2 | PUB-03 | simulator: customer turns truncated mid-token (38-39 of 41), 40-turn identity cap; cut-off logic byte-identical in both | shared |
| eng.9 | path A r1 | HA-A | agent: no thanks/goodbye before the transfer (rule 47) | shared |

PUB-06 "the rest will stay overdue": said in 4/4 calls on both arms (all judged pass).
Dry battery (Methodology, 24 builds, `docs/plans/2026-10-11-dry-battery-eng4-vs-eng9.md`): eng.9 meets (a)-(e); (c)
"absent for B-only" untested; eng.9 paid sentence in its row 12/12 vs eng.4 ab-single 1/3; overdue rendered 12/12 vs
4/12.

## Pre-registered decision rule applied to the matched complete rounds (1-2)

1. strict(eng.9) >= strict(eng.4) on both agents: A+B 10/13 = 10/13; raw-A 9/10 > 8/10. **Met.**
2. No case fails for an agent cause on eng.9 that passed on eng.4: eng.9's failures are platform, simulator, or mixed
   and shared (PUB-12: eng.4 did not pass it strictly either). **Met.**
3. PUB-06 overdue sentence at least as often: 4/4 vs 4/4. **Met.**
4. E1 shows no agent-caused regression on eng.9: eng.9 2/3 + 2/2 vs eng.4 0/3 + 0/2 (eng.4's r2 lost to the platform);
   the only eng.9 agent failure (HA-A r1) is shared. **Met.**
5. Dry battery (a)-(e): **met**, with (c)-absence untested.

**By the pre-registered rule, eng.9 qualifies to replace eng.4.** Limits: 2 matched reps, not 3 (round 3 lost to the
platform); one fresh build per arm (eng.9's raw-A build was a fix-inactive draw); eng.4's round 2 path cases were lost
to the platform; the goodbye fix (eng.4g/eng.9g) and the offers fix (eng.4o2/eng.9o2) are **not evaluated** (outage).
No automatic adoption: the user decides (D6). Freeze mechanics: `merge-main-eng9` = c1cbeb7 (Methodology; 922 passed,
fresh-clone `--dry` clean) needs main re-merged (docs/scripts only) before `freeze-final`; `final-eng4` = 924b970 is
the eng.4 equivalent.

## After the decision (D6, user 15:51 UTC: eng.9; eng.9g if it passes by 16:40)

- eng.9g goodbye evaluation, round 1: HA-A PASS and HU-A PASS (farewell spoken), PUB-09 PASS; **HU-PRE FAIL**: the judge
  failed it because `end_call` (the new end node's spoken farewell) ran after `close_call` and repeated the model's own
  "Thank you. Goodbye." HU-PRE passed on eng.9 r1 and r2, so the fix caused a regression: rule (2) fails, eng.9g is not
  adopted. Remaining eng.9g items not run. eng.4g (3 items, 0/3 stalled, 1/1, 1/2) and the offers fix (o2) untested.
- **`freeze-final` = b9756fe** = cand-eng.9 + main (builder code identical to cand-eng.9), 931 passed, fresh-clone `--dry`
  OK (Python 3.12), secrets clean.
