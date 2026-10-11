# Final-selection evidence: builder candidates (11 Oct, as of 12:50 UTC)

Evidence in this dossier runs up to 12:42 UTC: the checkers' corrections plus `docs/WORKING_STATE.md` entries through the 2nd smoke at 12:40. Nothing is selected or frozen here. The user makes the final selection.

Source shorthand used in brackets:
- `r4/` = `runs/dev/r4/`, `r3/` = `runs/dev/r3/`
- WS = `docs/WORKING_STATE.md`, OR = `docs/plans/2026-10-11-overnight-report.md`, EL = `docs/plans/2026-10-11-engine-fixes-log.md` (line numbers drift between versions), PF = `r4/perturbed-findings.md`
- sim = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/`
- dossier = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/54d12450-d446-4d3a-862a-6541a5ece9bd/scratchpad/dossier/`

## 1. TL;DR

1. **Measured:** G1 (`cand-g1.1`, 83f8263) is the only lineage build with full strict-3/3 case sets:
   - saved-spec A: 10/10 [r4/M3-G1-styledA.json]
   - fresh raw-A: 8/10 [r4/M4-rawW-styledA.json]
   - fresh A+B: 7/13, confounded by latency at concurrency 13 [r4/M5-ab1W-all.json]
   - extra-B: 1/3 [r4/M5-ab1W-xb.json]

   `cand-retry.4` (d53fa0e) is G1 plus the builder platform retries. Its saved-spec renders are byte-identical to G1's measured agent [dossier/vlin/retry4-a.json; readiness check].
2. **Not measured:** `cand-final.1`, `cand-eng.4` and `cand-eng.5` have **no valid rep**. eng.4 has three single PUB-01 smoke calls on a degraded platform: two passed at call level, and one failed when the customer hung up after a 54 s model turn [r4/SMOKE-e4a.*, r4/SMOKE2-e4a.*; WS 12:37-12:40]. No candidate's own fresh-build path has been simulated.
3. **Offline:** on the saved specs, eng.4 equals final.1 except in the code nodes, and their FACTS output is identical on every tested state. Both carry about 1,000 words of identity and negotiate prompt that G1 never ran with. Only eng.4 fixes the four rehearsal defects for changed briefs (2 HIGH) that G1 and final.1 still carry [PF; EL variant-e FACTS].
4. **main's builder code is F3** (a01a17c), not any candidate. Every candidate needs main's docs merged in (merge-tree is clean), then `make verify`, then `freeze-final`.
5. **Decision needed:** which commit becomes `freeze-final`. Internal target 15:30 UTC (18:30 Istanbul). Choose before 17:00 UTC (20:00 Istanbul) to avoid the post-brief switching question. Submission closes 20:00 UTC (23:00 Istanbul). The queue has been paused since 11:38 (by the user's decision since 12:45: no simulations or probes without the user), and latency was still flapping at 12:40 (14-54 s model turns).

## 2. Candidates

| Tag | Commit (committed UTC) | Contents (one line) | Tests | Offline checks | Live measurement |
|---|---|---|---|---|---|
| cand-g1.1 | 83f8263 (00:51) | F3 + FACTS change in `sandbox/facts.py` (+17) | 769 (760 + 9 env-only in an archive) | Renders reproducible on py3.12/3.13/3.14. **No platform retry.** Trace does not redact FREYA_WORKSPACE_ID | **Yes**: M1, M3, M4, M5, M5-xb (§3) |
| cand-retry.4 | d53fa0e (09:08) | G1 + builder retries, 30-min stop, export before smoke, workspace-id redaction. No render, extraction or FACTS change | 776 + 9 env-only (archive) | A and A+B `--spec --dry` renders byte-identical to G1's measured renders. merge-tree clean | Not deployed. Measured **by render identity only** |
| cand-final.1 | ca80d52 (10:08) | G1 + identity v2 + offer-wait (WAITING) + retries + precedence `ending_wins` + 2 guards | 820 (re-run) | Fresh-clone `--dry` OK, 97 s. Re-render byte-identical | **None** (never deployed) |
| cand-eng.4 | cfa4d9d (11:07) | final.1 + all-at-once verify_identity, the brief's own too-much rule, `this <weekday>` from the brief, half-up percentage floor, review fixes, variant-e fixtures | 859 (re-run) | Fresh-clone `--dry` OK, 98 s. 3 slots export-MATCH | **No valid rep.** 3 PUB-01 smoke calls (§3.6) |
| cand-eng.5 | 27f5647 (11:07) | eng.4 + the PUB-12 multi-product FACTS paragraph (4006d5c). A **sibling** of eng.4, not a child | 861 (852 + 9 env-only, archive) | Engine renders only. No fresh-clone rehearsal | **None** (no slot) |
| cand-eng.6 / .7 | a170935 / a985076 | eng.4 / eng.5 + Fix 1 (negotiate stage_rules about 4.5x larger on fresh builds) | 861 / 863 (claimed) | Not reviewed here | None. User (12:00): eng.4 stays the comparison candidate |
| main | 198e87a | Builder code = **F3** (a01a17c); later commits change only docs, tests, scripts and dashboard | 872 on the main→eng.4 trial merge | `git diff a01a17c main -- src builder kit` is empty | n/a |

Sources: git merge-base, patch-id and diff checks [lineage L-01..L-10]; `pytest-{final,eng4}.txt` [dossier/lineage]; `r4/fc-eng4-a.trace.log`; `fresh-clone-dry.log` (ababcede scratchpad); readiness checker R-08 and the cand-retry.4 note.

Ancestry: f2 → f3 → g1.1 → id.3 → idw.3 → final.1 → eng.3 → {eng.4, eng.5}; g1.1 → retry.4. cand-wp-g1.1 is **not** an ancestor of final.1: its patches were re-applied as ce9aa68 and ca80d52.

## 3. Measured evidence

Strict means all 3 reps of a case pass. **cand-final.1, cand-eng.4 and cand-eng.5 have no valid measured rep** [r4/calls.tsv; sim/slots.tsv; .freya-agents.json].

### 3.1 Build provenance of the measured agents

| Build | Slot / agent | Spec | Export check | Runs |
|---|---|---|---|---|
| F2 bd4da7c (deployed at 71add36, export = bd4da7c render) | dev-a-llm2 v8 / 2485fc27 | spec-a-llm (saved) | MATCH | M1-F2, r3/styledA-a2-bd4da7c |
| F2 | dev-ab-llm v14 / b867b809 | spec-ab-llm-c45758f (saved) | MATCH | M2, M2-xb |
| G1 83f8263 | exp-g1-a v1 / 31f79439 | spec-a-llm (saved) | MATCH | G1-p06, M1-G1, M3 |
| G1 fresh raw-A | exp-raw-w / a41f58d9 | fresh extraction of raw-a.md | build trace only (dirty=False) | M4 |
| G1 fresh A+B | exp-ab1-w / 768e75c2 | fresh extraction of ab-single.md | build trace only | M5, M5-xb, M5r (1 rep), M5r2 (0 valid) |
| eng.4 cfa4d9d | exp-eng4-a / f166447e; -ab / 0988e6f1; -ve / 7818e5e2 | saved A; saved A+B; fresh variant-e | MATCH (all 3) | smoke calls only |

Sources: `r4/provenance.md`, `r4/exports/`, `r4/build-*.log`, `r4/diff-exp-idw-a.summary.txt`. exp-idw-a also matches; its slots.tsv entry "pending" is stale.

### 3.2 styled-a (Brief A, 10 cases x 3)

| Case [style] | F2 v8 (conc. 5) | **G1 M3** saved spec (conc. 13) | G1 M4 fresh raw-A (conc. 13) |
|---|---|---|---|
| PUB-03 [corrects] | 2/3 (f2ae27dd: simulator/script conflict + minor agent slip) | 3/3 | 2/3 (02018082: simulator + I1 loop, **ledger** declined vs failed) |
| PUB-06 [talkative] | 2/3 (221f1823: agent, ledger: floor offered 4x, closed refused) | 3/3 | 2/3 (3f5a442c: **agent, rule 26 re-offer**) |
| other 8 cases | 3/3 | 3/3 | 3/3 |
| Reps | 10, 8, 10 | 10, 10, 10 | 10, 9, 9 |
| **Strict** | **8/10** | **10/10** | **8/10** |

Sources: `r3/styledA-a2-bd4da7c.json`, `r4/M3-G1-styledA.json`, `r4/M4-rawW-styledA.json`, OR l.94. The F2 control and M3 ran at different concurrency.

### 3.3 block-p06 (M1: 3 interleaved 1-rep runs)

| Case [style] | G1 | G2 0bc83c4 | F2 |
|---|---|---|---|
| PUB-06 [talkative] | 3/3 | 2/3 (0d6d3217: floor re-offered) | 0/3 (e5d24c34 agent; 704c184a agent + simulator; 0608fe3b hang-up after get_account) |
| PUB-07 [asks_back] | 3/3 | 2/3 (f51eb78b: agent rule 21) | 3/3 |
| PUB-09 [talkative] | 3/3 | 3/3 | 2/3 (29041b61: hang-up about 3 s after "Please go on.") |
| PUB-03 [corrects] | **1/3** (d41ea98c loop, ledger; d10044ef **ledger**: promise recorded after wrong DOBs, disclosure) | 3/3 | 2/3 (eabf5674 loop) |
| **Strict** | **3/4** | 2/4 | 1/4 |

Sources: `r4/M1-*-r{1,2,3}.json`, `r4/analysis-m1.md`. The values 3.8 s and 0.3 s in the files are slowest-turn values, not hang-up times.

### 3.4 styled-ab-all (13 cases; A = PUB-01..10, B = PUB-11..13)

| Case [style] | M2 F2 v14 saved spec (c5) | M5 G1 fresh A+B (c13) | M5r r1 only (c5) |
|---|---|---|---|
| PUB-02 [asks_back] | 2/3 (5c049648: no tools, hang-up) | 3/3 | P |
| PUB-03 [in_words] | 1/3 (79778b2e I1, ledger; d6d44675 I1) | 2/3 (7b9a5413 **unexplained**, DOB re-asked; ledger ok) | P |
| PUB-04 [talkative] | 3/3 | 2/3 (1671130d: hang-up after a 19.6 s turn) | P |
| PUB-05 [pieces] | 2/3 (3575e933 silent hang-up) | 2/3 (4bd012b4 **unexplained ledger**: not_verified/failed vs hardship, 3.3 s turns) | P |
| PUB-07 [asks_back] | 3/3 | 3/3 | F (exact day asked twice, rule 21 by signature) |
| PUB-10 [pieces] | 3/3 | 2/3 (bf116d8e: hang-up after a 59.9 s turn) | P |
| PUB-11 [pieces] | 3/3 | 1/3 (cbf5c8c6 51.6 s, 9fbcf306 59.5 s: hang-ups, 2 of 3 promises) | P |
| PUB-12 [corrects] | 1/3 (1794c5e7, b1c26928: corrects artefact) | 2/3 (3c1dfe1c: artefact by signature) | F (**not** the artefact; reason truncated) |
| PUB-13 [asks_back] | 2/3 (68d28036 I2, ledger) | 3/3 | P |
| PUB-01, 06, 08, 09 | 3/3 | 3/3 | P |
| **Strict** | **8/13** (reps 12, 10, 10) | **7/13** (reps 11, 12, 9; 1 slow rep discarded) | 11/13, one rep only |

Sources: `r4/M2-ABv14-all.log`, `r4/M2-ABv14-all-r3.json`, `r4/M5-ab1W-all.json`, `r4/M5r-ab1W-all-c5.log`, `r4/analysis-m2.md`, OR l.97.

Degraded-platform G1 A+B data, which is **not valid as a rep**:
- M5r2 rep 1 (discarded): PUB-02 and PUB-13 unjudged. Judged FAIL on PUB-04, 06 ("rest stays overdue" not said), 08 and 12. The PUB-04 and PUB-08 FAILs carry judge text "All criteria met".
- 6d0c9464 self-restart: 6 pass, 1 fail (PUB-09 talkative a9cea491, untriaged), 5 error, 1 inconclusive at the
  12:28 read; **re-judged after completion with no new calls: pass 8, fail 1, error 4 at 12:51** (Service Check).
  Outcomes read at completion during the outage are provisional [docs/freya_api_notes.md].

Sources: `r4/M5r2-ab1W-all-c5.log`, `r4/6d0c9464-iteration-1228.json`.

### 3.5 styled-extra-b (Brief B, 3 cases x 3)

| Case [style] | F2 M2-xb | G1 M5-xb |
|---|---|---|
| PUB-11 [asks_back] | 1/3 (8bce92a7 identity ledger + unjudged; f5d5e209 unjudged) | 2/3 (1a27c309: I2, **ledger**) |
| PUB-12 [in_words] | 0/3 (17551e65, 0eeb80b7 judge-policy; 248f8231 unjudged) | 0/3 (agent policy: car-loan "today" re-ask or no persuasion; ledger right) |
| PUB-13 [talkative] | 2/3 (5036ca35 unjudged) | 3/3 |
| **Strict** | 0/3 (4 of 6 rep-2/3 calls unjudged) | **1/3** |

PUB-12 extra-B has **never** reached 3/3 on any build (676e9df 0/3, a8b70ea 1/3, 52b947c 1/3, d46b807 0/3, F2 0/3, G1 0/3). Part of this is a fixture artefact: the check text says "asks for no payment on it" where the official wording is "takes no promise" [EL; WS].

Sources: `r4/M2-ABv14-xb.json`, `r4/M5-ab1W-xb.json`, `r3/styledXB-ab-*.json`.

### 3.6 cand-eng.4 live data (exp-eng4-a, PUB-01 talkative, degraded platform)

| Run | Call | Verdict | Notes |
|---|---|---|---|
| E4-A-styledA 11:37 | none | no rep | POST /simulations 504. 10 calls booked conservatively [r4/E4-A-styledA.attempt1-post504.*] |
| SMOKE-e4a 12:00-12:03 | 6af560aa | run: no verdict; **call record success=True** | Tools verify x2, get_account, create_promise, close_call. **DOB asked 3x although given**. Turns 14-37 s [r4/SMOKE-e4a.call.json] |
| platform retry 12:10 | af507b83 | call record success=True | Normal latency (0-1.5 s), DOB asked once [r4/SMOKE-e4a.call-attempt3.json] |
| SMOKE2 12:37-12:40 | 6f4c5503 | **run-level FAIL** (the judge works again) | Customer hung up at 105 s. Model took 54 s to emit a tool call. Setup code node and verify were correct: latency, not logic [r4/SMOKE2-e4a.*; WS 12:37] |

This is the first live run of eng.4's FACTS code nodes, and of the identity-v2 and WAITING text that eng.4 shares with final.1. One case and three calls do not make a strict-3/3 measurement.

### 3.7 Per-case record on G1 code (all valid kept reps)

| Case | Saved A (exp-g1-a) | Fresh raw-A | Fresh A+B |
|---|---|---|---|
| PUB-03 | 4/6 (2 ledger failures) | 2/3 (1 ledger failure) | 3/4 |
| PUB-06 talkative | 8/9 (G1-p06 2/3, M1 3/3, M3 3/3) | 2/3 | n/a (corrects style 4/4) |
| PUB-07 | 6/6 | 3/3 | 3/4 |

G1 PUB-06 talkative across builds is 10/12 calls. The overnight report's "8/9" omits G1-p06 [r3/G1-p06-talkative-bd4da7c.json; OR l.137].

## 4. What transfers to each candidate

| Candidate | Measured results that are valid proxies | Basis | Unmeasured live |
|---|---|---|---|
| cand-retry.4 | All G1 saved-spec results (M1, M3) and, for build logic, G1's fresh builds (M4, M5) | Renders byte-identical to G1 for A and A+B. Extraction prompt, render.py and facts.py unchanged | The retry and 30-min code paths in a hidden build (the same code ran live in eng.4 deploys) |
| cand-final.1 | G1's FACTS, transitions, tools and hooks only | G1 → final.1 differs in 6 of 831 leaves: system_prompt (1 line), identity task (407 → 1071 words), negotiate task (WAITING, 943 → 1244 words), and 3 code nodes (+3 inert `ending_wins` lines). FACTS identical on 13,280 A states and 39,680 A+B states | Identity v2 and offer-wait text (no slot ever simulated: exp-i12-a and exp-idw-a have 0 calls); precedence gate 4; the `ending_wins` extraction wording on fresh builds |
| cand-eng.4 | The same as final.1. Any E4-A or E4-AB result also stands in for **final.1's saved-spec agent** | final.1 → eng.4 differs on saved A, A+B, raw-A and ab1-w specs in the code nodes only; CONFIG and FACTS output identical. The new paths are inert on the measured specs (floor_percent 0, no too_much, no this_weekday) | The extraction-prompt changes (every hidden build is fresh); the separate / next_occurrence / percentage / all-at-once paths (0 live calls; all-at-once **cannot** be simulated on the kit mock); 3 smoke calls only |
| cand-eng.5 | Brief A and raw-A: as eng.4 | The paragraph cannot fire when `first_ask_multi` is empty (A specs) | FACTS differ on **every** two-product state (26,400 / 26,400, 1,512 / 1,512), so no B-case measurement transfers. No slot |

Sources: `dossier/lineage/rdiff.py` outputs, `facts_equiv_renders.py`, `dossier/risks/facts_multi.py` [lineage R-02..R-10, F-01..F-04; risks O-01..O-05].

Fresh-build gap: only G1's fresh builds were ever simulated. G1's 10/10 on the saved spec fell to 8/10 and 7/13 on fresh builds. The organisers re-run the top 10 and remove an entry that "scores clearly below" [docs/reference/hackathon_page.md:241].

## 5. Risks per candidate

Status codes: O = open; C = closed in code, unmeasured; M = measured failure.

| Risk | G1 | retry.4 | final.1 | eng.4 | eng.5 | Hidden-brief severity (inferred) | Evidence kind |
|---|---|---|---|---|---|---|---|
| All-at-once verify_identity mapped to the per-answer path (HIGH in rehearsal) | O | O | O | C (cannot be simulated) | C | If a brief's identity shape changes: possibly every verifiable case of that brief (ledger). Rendered-prompt reading, not an observed call | static + rehearsal [PF:13-14] |
| The brief's own "too much" rule overridden (HIGH) | O | O | O (variant-e FACTS wrong: E1 date, E2 no promise) | C (FACTS right on E1/E2) | C | Ledger date and lost attempt on every too-much case | offline FACTS [EL variant-e] |
| `this <weekday>` hard-coded (MED) | O | O | O (E3 gives a past date, 2026-10-12) | C | C | Ledger date | offline |
| Float floor rounding (LOW) | O | O | O (743.78 vs 743.79) | C | C | Ledger amount ±0.01 | offline Decimal check |
| A too-much date dropped in attempt_1 mode (MED) | O | O | O | O | O | Ledger date | static (Fix 2 deferred) |
| Identity I1/I2 (cut-off answer not submitted; "why do you need that" = decline) | **M** (PUB-03 corrects fails 7/23 ≈30% across builds; 3 G1 ledger failures; PUB-11 I2) | M (same agent) | C (v2) | C (v2; smoke call 1 asked DOB 3x, cause open) | C | Every case passes identity: high leverage either way | measured / unmeasured [r4/analysis-identity-history.md] |
| PUB-06 floor re-offer (rule 26); rule-21 re-ask | **M** (10/12; 3f5a442c agent) | M | C (WAITING) | C | C | Judge fails on "once" rules | measured / unmeasured |
| Ending that overrides a promise (precedence) | O | O | C (gates 1-3 offline; gate 4 never ran; C3/C5 open) | C | C | Ledger outcome on such briefs | offline [r4/precedence-report.md] |
| No builder platform retry | **O** (one 5xx on create/publish/export = exit 1) | closed | closed | closed (ran live: create 504 retried) | closed | Deploy failure on a degraded platform | static + live logs |
| Trace does not redact workspace id | O (check_secrets still flags it) | closed | closed | closed | closed | Leak risk in a committed trace | static |
| PUB-12 extra-B never 3/3 | M | M | O | O | targeted, unmeasured (engine estimate ~55%, not a measurement) | Multi-product judge fails | measured |
| eng.5 paragraph in every multi-product call | - | - | - | - | new regression surface | PUB-11, PUB-13, any 2-3 product customer | offline |
| "One business day" sentence dropped in fresh multi-product extraction (6 of 16 fresh builds) | O | O | O | O | O | Paid-product judge fail | offline (Fix 1 only in eng.6/.7) |
| "Rest stays overdue" not said | O | O | O | O | O | Floor-offer judge fail | measured once |
| Customer-proposed amount/date; non-floor amount and time-of-day rules (gaps 9, 11) | O | O | O | O | O | Ledger amounts (tie-break 1) | static (O1 parked) |
| Platform latency hang-ups | all | all | all, plus larger prompts (inferred) | all (seen in SMOKE2) | all | Any case | measured |
| RUNBOOK says re-run a hidden build on a bare chat-smoke 500 | smoke retries once | yes | yes | yes | yes | Today's 500s were platform-wide (exp-eng4-a ran fine after one): a needless re-run costs build time | static [docs/RUNBOOK.md:112; kit/docs/api.md:252] |
| Extraction prompt changed and never simulated | - | - | ending_wins wording | +3 fields | +3 fields | Fresh hidden builds | static. Fresh-sample false positives 0/23 (too_much), 0/25 (all-at-once) |

## 6. Submission readiness and budget

### 6.1 What is left, per candidate

| Step | G1 | retry.4 | final.1 | eng.4 | eng.5 |
|---|---|---|---|---|---|
| merge-tree with main (now 198e87a) | clean | clean | clean | clean | clean |
| Merge main's docs (RUNBOOK ae484b2: freeze-final block, retry WARN and stray-workflow notes, 503/504 exit-3 rule, outage row) | needed | needed | needed | needed | needed |
| `make verify` (runs `ruff format .` first) → commit → `git tag freeze-final` | needed | needed | needed | needed | needed |
| Fresh-clone `--dry` rehearsal | none (worktree builds 111/121 s OK) | none | done, 97 s | done, 98 s | none |
| RUNBOOK steps 2-5 rehearsal (`--slot rehearsal`) | not done | not done | not done | not done | not done |
| Slot deployed | yes | no | no | yes (3) | no |

Common to all:
- OpenAI key for the organisers' re-run is still open [RUNBOOK:20-21, 116-120].
- 0 git remotes; pushing needs the user's go-ahead.
- 35 of 200 workflow slots used; there are 2 possible stray workflows from retried creates.
- A fresh checkout on system python 3.9.6 stops at the 3.10+ guard. Use `.venv` or uv 3.12.
- All candidate commits were made before 17:00.

### 6.2 Budget and time model

- **Ledger: cum 312** of the runner cap 500 → 188 left [r4/calls.tsv last row 12:40:17]. The cap is internal; the organiser rule is only "do not probe or load-test".
- **Credits:** 391.06 USD at 12:29 [WS]. At 0.21-0.26 USD per call, the 90-call E4 queue costs about 19-23 USD. Credits are not binding.
- **E4 queue** [sim/queue.txt]: E4-A-styledA 30, E4-AB-all 39, E4-AB-xb 9, E4-VE 12 = 90 nominal → cum 402. Worst case is 4 simulations per rep (slow re-run x unjudged repeat), which could exceed 500. The runner checks the cap only at item start.
- **Normal-speed durations** [r4/*.json `seconds`]:
  - styled-a x3: 6-22 min
  - styled-ab-all x3 (c5): 7-13 min
  - extra-b x3: 5-15 min
  - variant-e x3: 3-12 min
  - whole queue: 21-62 min
- **Degraded speed:** about 21-33 min per rep regardless of size, often with no verdict (M5r2, SMOKE-e4a). That is at least about 99 min per x3 set.
- **Builder time per brief:** 91-183 s `--dry`; 111-339 s live on a healthy platform; up to 433 s on `--spec` today. Hard limit 30 min.
- **Hidden-build window:** two builds plus one re-run each is about 120 min worst case, so 17:00 → about 19:00.
- **Prep before freeze:** merge + `make verify` + tag ≈ 10 min; a RUNBOOK rehearsal build ≈ 2-7 min.

## 7. Fallback options by platform scenario

**Nothing runs, not even a bounded smoke or a latency probe, until the user says so** (user, 12:45 UTC; WS). Once the user allows it, the gate is:
- the endpoints recover AND one bounded smoke gives a complete judged result; missing results or platform errors keep the queue paused (user, 12:09);
- added by our own 12:31 plan, not by the user: the smoke must also create a call and show normal latency.

SMOKE2 (12:40) was judged but failed on latency, and the user has kept the queue paused since 12:45.

### Proposed adoption rules (the user may change them)

- **Rep validity:** every call judged (run or call record) and no rep discarded as slow. Degraded reps do not count.
- **Rule A (E4-A-styledA vs M3, G1 10/10, same saved spec):** passes if strict 10/10, or if every failing call is classified non-agent (simulator, platform, or a hang-up after a turn of about 20 s or more) **from its transcript**, with no agent-caused ledger error. Any agent-caused failure on a case G1 passed 3/3 fails the rule.
- **Rule B (E4-AB-all vs M2, F2 8/13, same saved spec):** passes if strict ≥ 8/13 and no case that was 3/3 in M2 fails for an agent cause. PUB-12 corrects-artefact failures are excluded.
- **Rule C (E4-AB-xb, E4-VE):** informative only. No usable control: M2-xb was unjudged and PUB-12 carries a fixture artefact. Variant-e has no control at all.
- **Caveat:** Rules A and B test eng.4's prompts and FACTS on saved specs. They do **not** test its extraction-prompt changes. The engine log's own bar is strict 3/3 on fresh builds. An optional fresh check would deploy a fresh raw-A eng.4 build (new slot, about 2-5 min) and run styled-a x3 (30 calls) against M4 (G1 fresh 8/10). That needs the user's approval for a new deployment.
- **Transfer:** A and B results on eng.4 also hold for final.1's saved-spec agent (§4).

### S1: platform recovers by about 13:30 UTC (16:30 Istanbul)

| Item | Detail |
|---|---|
| Run (after the user's go-ahead, D1) | Bounded smoke → E4-A-styledA (30 calls) → **[stop; report any judged agent failure to the user]** → E4-AB-all (39) → fresh raw-A eng.4 build + styled-a x3 (30 + 1 build) **only if D3 is approved** → E4-AB-xb (9) → E4-VE (12) |
| Calls / time | 90-120 calls (cum 402-432). About 21-62 min normal, plus 15-25 min for the fresh check. Fits before 15:30 |
| Evidence for the user's decision | Rules A + B (+ fresh check if run), reported to the user; passing them selects nothing (D2, D6) |
| If it fails | An agent-caused new failure: read the transcript first (user rule: a judged agent failure is diagnostic), then go to the S3 options with that evidence |
| If it cannot finish | Go to S2 or S3 |
| **Recommendation (labelled, not a selection)** | eng.4 if A + B pass (and the fresh check is at least M4's 8/10 with no new agent cause). Otherwise retry.4. **Would change it:** an agent-caused identity or offer-wait failure, which points at the shared final.1/eng.4 prompt text, so final.1 is no fallback for it |

### S2: platform recovers 13:30-16:00 UTC (16:30-19:00 Istanbul)

| Item | Detail |
|---|---|
| Run (after the user's go-ahead, D1) | Smoke → E4-A-styledA first → [stop; report any judged agent failure]. Then E4-AB-all if at least 35 min remain before about 16:15. Skip xb, VE and the fresh check unless time remains |
| Calls / time | 30-69 calls; 6-35 min normal. Recovery after about 15:45 leaves room for E4-A only |
| Evidence for the user's decision | Rule A alone if E4-AB-all cannot finish. With A only, Brief B behaviour stays unmeasured for every post-G1 candidate |
| If it fails or cannot finish | S3 options |
| **Recommendation (labelled)** | Adopt eng.4 only if A **and** B both pass. If only A ran and passed, the choice is the S3 trade with one more data point. Lean eng.4 only if the user weighs hidden-brief variation highly |

### S3: no recovery before 17:00 UTC (20:00 Istanbul)

No live measurement is possible. Choose on the existing evidence, preferably before 17:00.

| Option | For | Against |
|---|---|---|
| **cand-retry.4** (measured-equivalent G1 + retries) | Saved-spec renders identical to the measured 10/10 agent. Fresh G1 builds measured (8/10, 7/13). Retries ran live today | Carries the measured agent defects (PUB-03 identity ≈30% on corrects style; PUB-06 re-offer) and all 5 hidden-brief gaps (all-at-once identity, too-much rule, weekday, rounding, precedence). Not deployed, no fresh-clone rehearsal |
| cand-g1.1 as-is | The measured commit itself | **No platform retry**: on today's platform a hidden build can end with exit 1. Workspace id not redacted. Dominated by retry.4 |
| cand-eng.4 | Fixes the 2 HIGH + 2 lower rehearsal defects in code (right FACTS on variant-e). Retries. Deployed and export-matched. 3 smoke calls: flow works end to end | Identity v2 + WAITING text and the extraction changes are unmeasured. Smoke call 1 asked the DOB 3x (cause open). No Brief B data |
| cand-final.1 | Smaller extraction change than eng.4 | Same unmeasured prompt text as eng.4, **plus** the rehearsal defects (wrong FACTS on all 4 variant-e cases). Never deployed. Dominated by eng.4 or retry.4 depending on what the user weighs |
| cand-eng.5 | Targets PUB-12 | Everything unmeasured for eng.4, plus a FACTS change on every multi-product call. No slot, no fresh-clone rehearsal |

**The trade, plainly:** retry.4 is the known quantity on briefs shaped like A and B, with known gaps if the hidden briefs change identity shape or the too-much, weekday, rounding or precedence rules. eng.4 is broader and offline-correct on those changes, but its agent text has never passed a judged rep.

**Recommendation (labelled, not a selection):** cand-retry.4, per the project's rule to put test results above intuition (CLAUDE.md rule 5). **Would change it:** if the user judges a changed identity shape or a changed too-much rule likely in the raw brief with its amending memo. Each of those can fail a whole case class on retry.4 (PF), and that would favour eng.4.

### After-17:00 rules

| Kind | Content |
|---|---|
| Facts | After 17:00 only bug fixes may enter, with nothing from a hidden brief; "a reviewer checks the commit"; the final three hours are "for running the builder and fixing bugs, not for tuning it" [kit/README.md:73; hackathon_page.md:88,100,277] |
| Facts | Project rules are stricter: only generic bug fixes [CLAUDE.md:33-34]. Both agents must come from the same commit, and traces must show dirty=False with an empty src diff [RUNBOOK:75-85] |
| Facts | A reviewer agent reads every trace against the submitted code and the agent it claims to have created [hackathon_page.md:241] |
| Judgement | Switching candidates after 17:00 means a new commit that changes builder code, plus rebuilding both briefs. The rules do not say whether choosing another pre-17:00 commit counts as a "bug fix". If the switch is driven by hidden-brief behaviour, it looks like tuning |
| Option | Prepare **both** merged commits (main → eng.4, main → retry.4) **before 17:00, untagged**. A later choice then selects an existing pre-17:00 commit. Whether the reviewer would read that as tuning is still the user's call |
| Judgement | Practice simulations on public cases after 17:00 are not addressed by the rules. They share the platform with the hidden builds, and their only use would be feeding a post-17:00 switch |

## 8. Decisions needed from the user

| # | Decision | Deadline UTC / Istanbul | Default if nothing is decided |
|---|---|---|---|
| D1 | Resume the E4 queue (and latency probes): **user 12:45: keep the queue paused for now; no probes** | User's call | Queue stays paused; no simulation starts |
| D2 | Accept, amend or replace adoption Rules A, B and C (§7) | Before resume | No rule adopted; results are reported raw |
| D3 | Approve a fresh raw-A eng.4 build + styled-a x3 (30 calls, 1 workflow) to meet the engine log's fresh-build bar | Before resume, S1 only | Not deployed |
| D4 | Prepare untagged merged commits now (main → eng.4 and/or main → retry.4) | 15:30 / 18:30 | Not prepared; candidate branches untouched |
| D5 | Run the RUNBOOK steps 2-5 rehearsal (`--slot rehearsal`) on the chosen merge | 16:15 / 19:15 | Not run |
| D6 | **Final selection + `freeze-final` tag** | Target 15:30 / 18:30; before 17:00 / 20:00 to avoid the post-brief question | **Nothing selected or tagged.** Hidden builds wait for the user. main as-is is F3 and must not be built from |
| D7 | Treat a bare chat-smoke 500 with exit 3 as "deployed, do not re-run" (RUNBOOK change) | 17:00 / 20:00 | RUNBOOK unchanged: re-run on 500 |
| D8 | OpenAI key arrangement for the organisers' re-run (organiser email) | 20:00 / 23:00 | Open; nothing goes into the repo |
| D9 | Remote, visibility and push | 20:00 / 23:00 | No remote, no push |
| D10 | eng.6 (and .7, .8) vs eng.4: approve, trim or drop the matched fresh-build comparison in §10 (new deployments: 2-6 workflows for T1-T3, 8 with the optional T4) | Before any deployment; T1 must start by about 14:30 UTC to finish before 15:30 at normal speed | **Not deployed, not adopted.** eng.4 stays the comparison candidate (user 12:00) |
| D11 | Keep or raise the internal 500-call cap, or trim the E4 queue and the §10 tiers to fit (E4 queue 90 → cum 402; + T1 → 468; + T1+T3 → 564) | Before resume | Cap stays 500; the runner stops before any item that would exceed it; nothing is trimmed or added without the user |

## 9. Open gaps and unverified items

- No transcript was read for any M5, M5-xb, M5r or M5r2 call. Their classes come from judge text, `ended` and `slowest_turn_s`. Calls 4bd012b4 (PUB-05 ledger) and 7b9a5413 (PUB-03) are classified nowhere. M5r PUB-12, and the M5r2 PUB-04/08 "criteria met" FAILs, cannot be resolved because the judge text is truncated.
- The 6d0c9464 PUB-09 talkative FAIL (a9cea491, G1 fresh A+B) is untriaged and ran on the degraded platform.
- Cause of the DOB being asked 3x in smoke call 6af560aa: identity v2 prompt or latency? Open. The retry call af507b83 asked once.
- No export check on file for exp-raw-w, exp-ab1-w or exp-f3-a (provenance rests on the build trace).
- Concurrency is not matched: M3, M4, M5 at 13; F2 controls at 5. No complete 3-rep G1 A+B run exists at concurrency 5. Latency persists at 5 (worst turns 34 s and 50 s).
- FACTS equivalence covers setup and account_facts on synthetic grids of 1-3 products. The finalize node is not covered (`ending_wins` is inert only by static reading of the specs).
- cand-retry.4 is not deployed and has no fresh-clone rehearsal. Its equivalence to G1 rests on offline renders and the src diff.
- The degraded-speed model rests on two data points (about 33 min for a 13-call rep, about 21 min for a 1-call rep). Recovery time is unknown.
- Python 3.10 and 3.11 are untested; pyproject says ≥3.12 while the README says 3.10+.
- How likely each hidden-brief change is (identity shape, too-much rule, weekday wording, rounding, precedence) is unknown. The severities in §5 are conditional.
- How the build-time tie-break is computed (sum of both briefs, or which run) is unanswered.
- Possible stray workflows from the 2 retried creates were not checked.
- eng.6/.7: reviewed from the engine log only (§10); no eng.6/.7 build, render or test was run in this review.
- The new runner verdict fallback (4631971, 7bfcf41) means future E4 rows may take verdicts from call records, while the M2 and M3 controls used run-level verdicts only. Agreement on the record so far: 43/43 and 50/50 [WS; commit 198e87a].
## 10. Addendum (12:50 UTC): cand-eng.6 / .7 and the proposed matched comparison

Added after the workflow, on the user's instruction (12:00): incorporate the Methodology hand-off correction, keep
cand-eng.4 as the comparison candidate, include full matched A/B regression coverage and PUB-06 "rest stays
overdue" behaviour, and adopt nothing automatically. **Nothing below has been deployed or run.**

### 10.1 What eng.6 / eng.7 are (engine log, READ FIRST and hand-offs; not re-verified here)

| Tag | Commit | = | Tests (claimed) |
|---|---|---|---|
| cand-eng.6 | a170935 | cand-eng.4 + Fix 1 (`pipeline.py` extraction prompt + `spec.py` check_spec guard) | 861 |
| cand-eng.7 | a985076 | cand-eng.5 + Fix 1 (clean cherry-pick; extraction path identical to eng.6) | 863 |

- **Saved-spec renders are byte-identical** to eng.4 (eng.6) and eng.5 (eng.7) on all 7 saved specs. That proves
  only that the render code is unchanged. **It says nothing about fresh builds**, and every hidden build is fresh.
- **Fix 1 is a broad fresh-build behaviour change.** Its prompt sentence ("a sentence the agent must say belongs
  in a field above") moved most of `unmodeled` into rendered `stage_rules`:
  - median unmodeled lines fell from 19 to 4 (A/raw-A) and from 22.5 to 3.5 (multi-product);
  - the rendered negotiate `stage_rules` grew from 565 to 2,570 chars (A/raw-A) and from 752 to 3,254 (multi).

  A sampled fresh A build's new stage_rules is a faithful summary of rules 17-47 (nothing invented found), but
  it substantially changes Brief A's negotiate guidance on every fresh build.
- **Intended effect, extraction only:** the per-product "paid" sentence sat in its row in 12/12 fresh
  multi-product extractions, against 6 misses in the earlier multi-product extractions before Fix 1 (engine log: "6 of
  16"; its breakdown A+B 1/7, variant-c 4/5, p3b 1/2, variant-r 0/3 sums to 6 of 17).
- **"The rest stays overdue" (Fix 3, not implemented):**
  - Before Fix 1 it sat in `unmodeled` in 18/18 specs and was never rendered; only the raw brief in the system
    prompt carried it.
  - After Fix 1 it is in the rendered `stage_rules.negotiate` in 16/16 fresh builds. It is an LLM paraphrase,
    placed at about 49-60% of the negotiate task, not on the FACTS "too much" line.
  - **Whether the agent says it is unmeasured.** The absence case (a brief without the rule) is **untested**.
- **Measured context:** pre-Fix-1 G1 builds already say the sentence in most PUB-06 calls. G1 PUB-06 talkative
  passed the judge in 10 of 12 calls (§3.7), and that judge check includes the overdue note. Both of its failures
  were the rule-26 re-offer (G1-p06 bfe80eb8, M4 3f5a442c). Two overdue misses are on record: G1-p06 bfe80eb8 (G1
  saved A, talkative; the note was missing on the repeated offer) and M5r2 PUB-06 on G1 fresh A+B (corrects; a
  discarded, degraded rep: "failed to mention that the remaining balance stays overdue"). Fix 1's upside on PUB-06
  is therefore small; its risk is broad and includes one confirmed defect (next bullet).
- **Fix 1 audit (engine log READ FIRST item 5 and its last section, 12:21-12:36 UTC): CONFIRMED defect (high).** In
  6/16 fresh Fix-1 specs (0/13 pre-Fix-1; raw-A 2/2) a closing row's `say_before_end` repeats the mid-call support
  offer question (in one A+B spec also "Can I help you first?"), so the agent asks it again in its goodbye: PUB-05
  fails "support team offered once" / "one sentence of sympathy" with the ledger right. Sympathy-only repeats in 3
  more specs. It is extraction-random: **before reading any eng.6/.7 hardship, support or human-request result,
  check that build's spec rows for a "?" in `say_before_end`.** Not fixed on eng.6/.7 (strict-xfail test on branch
  `audit-fix1-endings`, dcd9749). A second, plausible (medium) risk: the vague-period rule (rule 21) now sits in the
  same negotiate task as the PUB-07 deadline guard.
- **cand-eng.8 = 4267bb0** (eng.6 + dcd9749 + a render change: lines said before the customer answers move from the
  ENDINGS "First say" lists into the step's rules, "never again in the goodbye"). Commit message: renders of 62 of
  71 saved specs byte-identical to eng.6; the 9 that change are the defective fresh extractions. No hand-off in the
  engine log yet; **unmeasured; not reviewed here.**

### 10.2 Why the deployed eng.4 slots are not the control

`exp-eng4-a` and `exp-eng4-ab` were built from **saved** specs (`--spec`). Fix 1 acts only on extraction, so a
matched comparison needs **both arms built fresh**: no `--spec`, the same brief files and tool API, built back to
back, with `--save-spec` for each. One fresh build per arm also mixes the fix's effect with ordinary
extraction-to-extraction variance. The mitigation: diff the two saved specs offline (stage_rules, unmodeled,
too_much, calendar) before simulating, and attribute any behavioural difference by transcript, not by count.
Methodology's own bar: investigate every difference, "do not call it noise".

### 10.3 Proposed matched comparison (eng.4 fresh vs eng.6 fresh), for approval

Shared conditions:
- concurrency 5, `--rerun-if-slow 1`, strict 3/3 per case;
- the runner's verdict fallback stays on, with every `verdict_source: call` row listed;
- arms **interleaved per rep** (1-rep runs alternating eng.4 / eng.6, as in M1), so that latency swings hit
  both arms alike;
- the resume gate (§7) applies first.

| Tier | Brief file(s) | New workflows | Case sets per arm | Calls (both arms) | Normal-speed time |
|---|---|---|---|---|---|
| **T1** Brief A | `kit/briefs/brief-a.md` | 2 (E4-fA, E6-fA) | styled-a x3 (10) + `owa-p06-asks.json` x3 (PUB-06 asks_back) | 60 + 6 = **66** | about 30-50 min incl. builds |
| **T2** raw material | `tests/fixtures/briefs/raw-a.md` | 2 (E4-fR, E6-fR) | styled-a x3 | **60** | about 20-45 min |
| **T3** A+B | `tests/fixtures/briefs/ab-single.md` (as M5) | 2 (E4-fAB, E6-fAB) | styled-ab-all x3 (13) + styled-extra-b x3 (3) | 78 + 18 = **96** | about 25-60 min |
| T4 (optional) | as T3 | 2 (eng.5, eng.7) | styled-extra-b x3 + styled-b x3 | 36 | about 15-30 min |

- **Cost:** T1 66 calls, T1+T2 126, T1+T3 162, T1-T3 **222** (+6 workflows; 35 of 200 slots used now, plus up to 2
  possible stray workflows from retried creates). From the ledger at 312, **after the 90-call E4 queue that runs
  first** (cum 402), these give 468, 528, 564 and 624. **Only T1 fits under the internal 500 cap, and the minimum
  eng.6 bar (T1 + T3) does not** (D11). Without the E4 queue: 378, 438, 474, 534. Credits (about 391 USD; about 50
  USD for T1-T3) do not bind.
- **Full matched regression coverage:** T1-T3 cover Brief A, the raw-material path and the multi-product A+B path,
  with every public style set we hold.
- **Fix 1 changes every brief's extraction, so a T1-only result cannot clear eng.6 for B or multi-product calls.**

**PUB-05 / Fix 1 defect check (eng.6 arms):** before reading results, check each eng.6 build's saved spec for a "?" in
any `say_before_end`; PUB-05 (hardship, declines support) runs in styled-a [in_words] and styled-ab-all [pieces],
so T1-T3 exercise the defect. Not covered by any public fixture: a human-insist case and a Brief B hardship case
(the engine's validation list).

**PUB-06 "rest stays overdue" metric (both arms):** per PUB-06 call,
1. the judge verdict: the check reads "minimum payment offered once, with the note that the rest stays overdue";
2. a transcript search of the agent turns around the floor offer for `(stays|remains|is still|still) overdue`.

Styles covered: talkative (styled-a), asks_back (owa-p06-asks), corrects (styled-ab-all). Report n/N per arm and
style. **Absence check:**
- live, in T3: grep the agent turns of the Brief B calls (PUB-11..13; Brief B has no such rule) for "overdue" and
  flag any hit;
- offline, proposed to the Methodology chat (builder LLM only, no Freya): 2 fresh `--dry` extractions of
  `kit/briefs/brief-b.md` alone at eng.6; the rendered stage_rules must contain no overdue sentence.

**Proposed decision rule (the user may change it):**
- eng.6 replaces eng.4 only if, in every tier that ran (at least T1 + T3; T2 strongly preferred because one
  hidden brief is raw material):
  - strict(eng.6) >= strict(eng.4);
  - no case fails for an agent cause on eng.6 that passed on eng.4 (classified from the transcript);
  - the PUB-06 overdue sentence is said in at least as many calls.
- Otherwise eng.4 stays.
- Before any freeze, eng.6 would also need what eng.4 already has: a fresh-clone `--dry` rehearsal and a
  main-merge trial (about 10 min).
- **No automatic adoption.**

**Ordering (labelled recommendation, the user decides):**
1. The paused E4 queue first: the user preserved it (12:00) and keeps it paused (12:45), so it runs only when the
   user resumes it (D1). E4-A-styledA is the clean saved-spec comparison against M3, 10/10.
2. Then T1. Its eng.4 arm is eng.4's first fresh **Brief A** build (no G1 fresh-A control exists). D3's raw-A fresh
   check is T2's eng.4 arm (E4-fR, against M4); if T2 is approved, D3 needs no separate deployment.
3. Then T3, then T2, as time allows.

At normal speed the E4 queue plus T1 is about 1-2 h. With the 12:40 latency (14-54 s turns) none of it produces
valid reps. Trimming T3 to styled-ab-all only (78 calls) saves 18 calls. Dropping T4 is the default.
