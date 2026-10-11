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

## Infrastructure
- Simulation queue runner (only launcher): `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.sh`, queue `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/queue.txt`
  ("name slot casefile reps"), slot table `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/slots.tsv`, output `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.out`. Writes `runs/dev/r4/calls.tsv`
  and a `.meta.json` sidecar per run. `touch /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/STOP` stops it before the next item.
- Precedence worktree: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-wp` (branch cand-wp).
- Derivation scratch: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/derive/` (inputs/, d1.json, d2.json, o1-final.json, report.md).

## Results
(filled in as blocks finish)
