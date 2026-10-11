# Dry-extraction battery: cand-eng.4 vs cand-eng.9 (11 Oct 2026, engine-fixes chat)

Requested by the Simulation Developer for the final comparison (user-approved plan, 14:35 UTC). Every build is
`builder/build.py <brief> <tool api> --dry --save-spec ...`: the builder's own LLM extraction plus a local
render and validation. **No Freya call, no deployment.** Trees: detached worktree of `cand-eng.4` = cfa4d9d and
the tagged `cand-eng.9` = b103e21 (clean, `dirty=False` in every trace). Inputs, 3 builds each per candidate:
`kit/briefs/brief-a.md`, `tests/fixtures/briefs/raw-a.md`, `tests/fixtures/briefs/ab-single.md` (kit tool API)
and `tests/fixtures/briefs/variant-c.md` (with `variant-c.openapi.json`). Python 3.12.13; builder models
gpt-6.1-sol with the usual fallbacks.

## Metric definitions (pre-registered by the Simulation Developer; how this file measures them)

- **(a)** Rendered ENDINGS lines in opening, third_party, identity and negotiate, sentences quoted after
  "First say". *Question*: a quoted sentence ending in "?". *Shared offer/sympathy*: a quoted sentence with
  sorry / connect you / would you like / can I help / help you first / I can offer / offer you that appears
  in two or more endings (the Fix 1 defect shape). Target 0 for both. A sympathy line in a single ending (the
  deceased row's "I am sorry for your loss.", said at the end by the brief's rule) is listed separately, not
  counted. *Fix STEP line*: the trace has at least one `STEP ending ...: said before the customer answers`
  line (cand-eng.8/.9 only; cand-eng.4 has no such step).
- **(b)** The spec's `paid` row(s) hold the "payments can take one business day to appear" sentence in
  `say_before_end` (Fix 1's purpose). Reported for every input; multi-product inputs are marked.
- **(c)** "overdue" appears in the rendered workflow outside the system prompt's embedded brief text (that
  is, in a node's step rules, FACTS code or ENDINGS). No B-only input was in the requested battery; all four
  inputs carry Brief A's rule 26, so "present" is the expected value for all of them.
- **(d)** `local workflow validation: PASS` and `END ok=True`; repair rounds = last `spec check (round N)`
  minus 1.
- **(e)** `build_seconds` from the END line.

## Results (n/3 per candidate per input; all 24 builds END ok=True, rc=0)

### cand-eng.4 (cfa4d9d)

| input | n | (a) question in a First say | (a) shared offer/sympathy in a First say | fix STEP line fired | (b) paid sentence in the paid row | (c) overdue sentence outside the brief | (d) validate pass | (d) repair rounds | (e) build seconds |
|---|---|---|---|---|---|---|---|---|---|
| brief-a | 3 | 0/3 | 0/3 | 0/3 | 3/3 | 0/3 | 3/3 | 0, 0, 0 | 101, 88, 96 (median 96) |
| raw-a | 3 | 0/3 | 0/3 | 0/3 | 3/3 | 1/3 | 3/3 | 1, 1, 1 | 175, 152, 153 (median 153) |
| ab-single (multi-product) | 3 | 0/3 | 0/3 | 0/3 | 1/3 | 0/3 | 3/3 | 0, 0, 0 | 125, 117, 118 (median 118) |
| variant-c (multi-product) | 3 | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 | 0, 0, 0 | 125, 121, 126 (median 125) |

### cand-eng.9 (b103e21)

| input | n | (a) question in a First say | (a) shared offer/sympathy in a First say | fix STEP line fired | (b) paid sentence in the paid row | (c) overdue sentence outside the brief | (d) validate pass | (d) repair rounds | (e) build seconds |
|---|---|---|---|---|---|---|---|---|---|
| brief-a | 3 | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 | 0, 0, 0 | 100, 100, 93 (median 100) |
| raw-a | 3 | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 | 3/3 | 0, 0, 0 | 107, 116, 113 (median 113) |
| ab-single (multi-product) | 3 | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 | 3/3 | 0, 0, 0 | 125, 117, 128 (median 125) |
| variant-c (multi-product) | 3 | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 | 3/3 | 0, 0, 0 | 116, 113, 115 (median 115) |

Total: 24 builds, 535071 model tokens (in + out).

## Reading the results

- **(a) target met on both candidates: 0/24** builds left a question or a shared offer or sympathy line in
  any ending's "First say". On cand-eng.9 the fix step line fired in 5/12 builds (raw-a 2/3, ab-single 2/3,
  variant-c 1/3, brief-a 0/3): those extractions put the support offer or sympathy into two endings, and
  render moved them out. cand-eng.4 never fires: its extraction prompt is pre-Fix-1 and lists no such lines.
- **(a) residual, not counted by the definition:** in cand-eng.9 ab-single r3 the sympathy line "I am sorry
  to hear that." sits in **one** ending only (`no_promise_hardship`, not `transferred_support`). The guard
  moves only shared lines (and questions), so it stays in that goodbye; if the agent also says sympathy mid-call
  (rule 32) the customer hears it twice. 1/12 cand-eng.9 builds; 0/12 cand-eng.4. The deceased condolence
  lines ("I am sorry for your loss." / variant-c "I am very sorry to hear that.") are single-row by design.
- **(b)** cand-eng.9 3/3 on every input; cand-eng.4 misses the paid sentence in the multi-product row in 2/3
  ab-single builds (it went to `unmodeled`, prompt only): the Fix 1 behaviour, now measured.
- **(c)** cand-eng.9 renders the overdue sentence outside the brief in 12/12; cand-eng.4 in 4/12 (brief-a 0/3,
  raw-a 1/3, ab-single 0/3, variant-c 3/3). No B-only input was in the battery, so "absent for B-only" is
  untested here.
- **(d)** validation passed 24/24. cand-eng.4 needed one repair round on every raw-a build (3/3); cand-eng.9 none.
- **(e)** median build seconds: cand-eng.4 96 / 153 / 118 / 125; cand-eng.9 100 / 113 / 125 / 115 (brief-a /
  raw-a / ab-single / variant-c). Every build is far inside the 30-minute limit.
- **Cost:** 535,071 model tokens for 24 builds (about 22k per build); no trace contains an API key or the
  team key (checked against the env values).

## Also run (same session)

- **Fresh-clone `--dry`** of the untagged merge `merge-main-eng9` = c1cbeb7 (main bccf825 into cand-eng.9):
  `git clone` of that branch, no `.env`, keys from the environment, `builder/build.py kit/briefs/brief-a.md
  kit/tools/openapi.json --dry`: `END ok=True build_seconds=101`, trace `git=c1cbeb7 dirty=False`, 27-node
  workflow, no secret in the trace. `make verify` on the merge: 922 passed, no file changed.

Raw files (scratch, not committed): per build `<cand>/<input>-r<n>.{trace.log,wf.json,spec.json}` under the
engine-fixes session scratchpad `dry/runs/`; `dry/metrics.json` (every value above), `dry/metrics.py`,
`dry/report.py`.
