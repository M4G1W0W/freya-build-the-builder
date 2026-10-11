# Overnight v2 execution report (live; morning handoff)

Coordinator session: autonomous under the user's final authorization (00:50 UTC). Plan:
`docs/plans/2026-10-11-overnight-plan-v2.md`. Raw results: `runs/dev/r4/` (gitignored): `<name>.json/.log/.meta.json`,
call ledger `calls.tsv`, exports/renders, provenance.md, precedence-report.md.

## Status (update at every block)

| UTC | Event |
|---|---|
| 00:47 | Restored; tree clean at da000da; worktrees wt-g1/wt-g2/wt-f2 intact (diffs == saved patches) |
| 00:55 | M0.1: G1 = cand-g1 **83f8263** (tag cand-g1.1), G2 = cand-g2 **0bc83c4** (tag cand-g2.1); each lint clean, 769 passed. Tags got a ".1" suffix: a tag named like its branch makes the ref ambiguous |
| 00:58 | M0.2: main **322dfc9**: block-p06.json, styled-ab-all.json, ab-single.md (verbatim; 769 passed) |
| 01:00 | Started: provenance agent (M0.3 exports), precedence agent (worktree wt-wp, branch cand-wp off a01a17c), D1/D2/D3 blind derivation workflow (O1 cases + extra-B re-derivation) |
| 00:59 | M0.3 export verification: **all four MATCH** (dev-a-llm2 v8 = bd4da7c; exp-g1-a v1 = 83f8263; exp-g2-a v1 = 0bc83c4; dev-ab-llm v14 = bd4da7c, briefs a,b). 0 changed / 0 render-only paths; export-only non-empty fields are kit defaults (on_enter llm, truncation keep_all/10) or identical platform fills in every slot (interruptible true, condition.mode exact). `runs/dev/r4/provenance.md` |
| 00:59 | M1 started (queue: G1, G2, F2 x 3 interleaved, block-p06, 4 cases each), then M2 queued. Credits 433.89 |
| 01:12 | Precedence gates 1-3 **PASS** on cand-wp c3102e1 (tag cand-wp.1; 792 passed; variant-c 3/3 exactly one ending_wins; 0/8 negatives). Adversarial review running. `runs/dev/r4/precedence-report.md` |
| 01:14 | D1/D2 blind derivation: **15/15 exact matches**; committed b7fe325 (o1-a.json 9 A, o1-b.json 3 B, extra-b-rederived.json); N4/N8 scripts clarified, blind re-check matched |
| 01:16 | **M1 done (36 calls): W = G1** (cand-g1.1 83f8263). Strict per case, 3 reps each (raw): G1 PUB-06 3/3, PUB-07 3/3, PUB-09 3/3, PUB-03 1/3; G2 2/3, 2/3, 3/3, 3/3; F2 0/3, 3/3, 2/3, 2/3. Newly failing vs F2: G1 none; G2 PUB-07 (rule 21 re-ask after a question back). PUB-03 fails in F2 too (common identity mechanism; see analysis-m1.md, incl. a LEDGER failure G1 r3 d10044ef: a complete wrong DOB in a cut-off message was never submitted). |
| 01:17 | M4/M5 fresh builds of G1 started (exp-raw-w, exp-ab1-w); precedence ported onto G1 as cand-wp-g1 e1a32d4 (clean cherry-pick, 792 passed, gate-1 render diff on G1 for A and A+B = only the 3 ending_wins lines) |
| 01:19 | M4/M5 builds ok=True at 83f8263 clean: exp-raw-w a41f58d9 (27 steps, 8 tools), exp-ab1-w 768e75c2 (32 steps, 12 tools); smoke tests PASS. Queued after M3 |
| 01:21 | Precedence adversarial review: **SHIP-TO-O4** (no FAIL; `runs/dev/r4/precedence-review.md`). Its C1 (ending_wins row must not be the default negotiate row) and C2 (must follow every transferred entry) guards added on cand-wp-g1: **58a7473** (tag cand-wp-g1.1), 794 passed; 19 saved specs: identical (empty) check_spec issues before/after; renders byte-identical |
| 01:24 | O4 fresh builds of cand-wp-g1.1 started (exp-raw-wp, exp-ab1-wp) |
| 01:31 | O4 builds ok=True at 58a7473 clean: exp-raw-wp dafa86d5 (27 steps, 8 tools), exp-ab1-wp c02f4a9f (32 steps, 12 tools); both specs have 0 ending_wins (negative extraction 10/10 overall). Queued after M5 |
| 01:21 | **PLATFORM: M2 rep-2 simulation a36c1d01 stuck in "running"** (all 13 calls ended by 01:21:07, iteration completed, status not updated since 01:21:29). M2 rep 3 waits ("another simulation is running"). Per the user's rule: report only, no PUT/pause/stop; if still blocked at 01:52 UTC (30 min) simulations stop for the night |
| 01:15-01:21 | M2 A+B control (dev-ab-llm v14) styled-ab-all: rep 1 12/13 (PUB-03 identity), rep 2 10/13 (PUB-05 no tool calls, PUB-12 judge, PUB-13 asks_back declined). Analysis running |

## Infrastructure
- Simulation queue runner (only launcher): `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.sh`, queue `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/queue.txt`
  ("name slot casefile reps"), slot table `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/slots.tsv`, output `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.out`. Writes `runs/dev/r4/calls.tsv`
  and a `.meta.json` sidecar per run. `touch /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/STOP` stops it before the next item.
- Precedence worktree: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-wp` (branch cand-wp).
- Derivation scratch: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/derive/` (inputs/, d1.json, d2.json, o1-final.json, report.md).

## Results
(filled in as blocks finish)
