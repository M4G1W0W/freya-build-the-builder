# Overnight v2 execution report (live; morning handoff)

## MORNING HANDOFF (read this first; final state at 02:30 UTC)

**Highest-value decision for you:** the Freya simulation `a36c1d01-1003-4b83-8d5e-b5121a82bc39` (M2 rep 2, A+B control)
has been stuck in "running" since 01:21:29 UTC although all 13 of its calls ended by 01:21:07. It blocks every
simulation in the workspace. Per your rule I did not PUT/pause/stop it, and simulations stopped for the night at 01:53
after 30 min. **Until it is freed (PUT status "paused", as on 10 Oct 21:55) no measurement can run, including the
Sunday 12:30 final validation.** It does not block the submission itself: the builder's self-test uses the chat API,
not simulations. Everything for the remaining blocks is built and queued-ready (see "Resume").

**Recommended candidate: W = G1** = branch `cand-g1`, commit **83f8263** (tag `cand-g1.1`) = F3 a069dd2 + the restored
too-much FACTS line. Not merged to main (merging waits for you). Deployed as exp-g1-a (workflow 5f39ed9a…, agent
31f79439…; export verified identical to the committed render). Caveats: see "Candidate review" (unmeasured: PUB-07
pieces, customer-proposed date/amount, Brief B on G1).

**Before/after, matched strict 3/3 (M1, block-p06, 3 reps per arm, interleaved, same session, raw):**

| Case [style] | F2 control (dev-a-llm2 v8) | G1 (exp-g1-a) | G2 (exp-g2-a) |
|---|---|---|---|
| PUB-06 [talkative] | 0/3 | **3/3** | 2/3 |
| PUB-07 [asks_back] | 3/3 | 3/3 | 2/3 (newly failing: rule 21 re-ask) |
| PUB-09 [talkative] | 2/3 | 3/3 | 3/3 |
| PUB-03 [corrects] | 2/3 | 1/3 (both failures LEDGER: d41ea98c declined vs failed after the 40-turn loop; d10044ef promise recorded; common identity defect) | 3/3 |
| cases at 3/3 | 1/4 | **3/4** | 2/4 |

A+B control (dev-ab-llm v14 = F2, styled-ab-all, 13 cases): rep 1 12/13, rep 2 10/13; rep 3 never ran (stuck sim).
Rep-3 PUB-06 calls (classified by the fact-checker, not by a transcript analyst): G2 r3 0d6d3217 floor re-offered (judge);
F2 r3 0608fe3b customer hung up after get_account, no promise (ledger; simulator-side), so F2's 0/3 includes one
hang-up; F2 r1/r2 are agent failures (floor offered "today"/twice).
Failures classified in `runs/dev/r4/analysis-m2.md`.

**Done overnight:** M0 (G1/G2 committed; case files; all 4 exports MATCH their claimed code), M1 (W = G1), M2 2 of 3
reps; fresh builds of W: exp-raw-w (raw-A) and exp-ab1-w (single-file A+B), both ok=True, not yet simulated;
precedence correction gates 1-3 PASS + adversarial review SHIP-TO-O4 + 2 guards (cand-wp-g1.1 58a7473), fresh builds
exp-raw-wp / exp-ab1-wp ok=True, not yet simulated; D1/D2 blind derivations: 12 O1 cases + 3 extra-B re-derivations
(15/15 exact) and 4 identity regression cases (4/4 exact); failure analyses of the failing M1 (reps 1-2, G1 r3) and M2 calls (two rep-3 PUB-06 calls only fact-checked); identity-gap
sizing over all 906 stored calls; G1 candidate review; identity-fix design v2 after a 3-lens adversarial review
(`docs/proposals/2026-10-11-identity-fix-v2.md`, not implemented; 81-call matched plan inside).

**Not done (blocked by the stuck simulation):** M2 rep 3 + extra-B, M3 (G1 on styled-a), M4 and M5 simulations (fresh
builds of W), O4 simulations (precedence fresh-build regression, gate 4), O1 (derived cases). Precedence therefore
stays isolated (gate 4 not run).

**Calls and credits:** 62 simulation calls of the 340 cap (M1 36, M2 26); credits 433.89 at 00:37 -> 428.93 at 02:04
UTC (~0.08 per call incl. builder smoke tests). Sunday reserve (155 calls) untouched.

**Running now (08:12 UTC, after your instruction):** the stuck simulation is paused and the resume queue is running.
**Before that:** no simulation of ours (only the stuck platform one). The read-only watcher stopped at its 2-hour
background limit (03:54 UTC); a manual GET at 03:54 still showed `running` (updatedAt 01:21:29). Nothing watches it now. Offline review agents may be finishing (see the log below).

### Resume (once the simulation is freed; all slots built and provenance recorded in `<scratchpad>/sim/slots.tsv`)
`<scratchpad>/sim/queue.txt` is pre-loaded; to resume: `rm <scratchpad>/sim/STOP; bash <scratchpad>/sim/qrun.sh >>
<scratchpad>/sim/qrun.out 2>&1` (bash; it re-checks the 340 cap before each item). Priority order: M2-ABv14-all-r3 (13),
M2-ABv14-xb (9), M3-G1-styledA (30), M4-rawW-styledA (30), M5-ab1W-all (39), M5-ab1W-xb (9),
O4-rawWP-styledA (30), O4-ab1WP-all (39), O4-ab1WP-xb (9), then O1: o1-a.json on exp-g1-a x3 (27), o1-b.json on
exp-ab1-w x3 (9). Total 244 calls (with 62 used: 306 < 340; discarded slow reps (`--rerun-if-slow 1`) would eat the 34-call headroom, and the runner then cuts the tail, O1, first). `<scratchpad>` =
`/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad`.


Coordinator session: autonomous under the user's final authorization (00:50 UTC). Plan:
`docs/plans/2026-10-11-overnight-plan-v2.md`. Raw results: `runs/dev/r4/` (gitignored): `<name>.json/.log/.meta.json`,
call ledger `calls.tsv`, exports/renders, provenance.md, precedence-report.md.

## Event log (UTC)

| UTC | Event |
|---|---|
| 00:47 | Restored; tree clean at da000da; worktrees wt-g1/wt-g2/wt-f2 intact (diffs == saved patches) |
| 00:51 | M0.1: G1 = cand-g1 **83f8263** (tag cand-g1.1), G2 = cand-g2 **0bc83c4** (tag cand-g2.1); each lint clean, 769 passed. Tags got a ".1" suffix: a tag named like its branch makes the ref ambiguous |
| 00:52 | M0.2: main **322dfc9**: block-p06.json, styled-ab-all.json, ab-single.md (verbatim; 769 passed) |
| 01:00 | Started: provenance agent (M0.3 exports), precedence agent (worktree wt-wp, branch cand-wp off a01a17c), D1/D2/D3 blind derivation workflow (O1 cases + extra-B re-derivation) |
| 00:59 | M0.3 export verification: **all four MATCH** (dev-a-llm2 v8 = bd4da7c; exp-g1-a v1 = 83f8263; exp-g2-a v1 = 0bc83c4; dev-ab-llm v14 = bd4da7c, briefs a,b). 0 changed / 0 render-only paths; export-only non-empty fields are kit defaults (on_enter llm, truncation keep_all/10) or identical platform fills in every slot (interruptible true, condition.mode exact). `runs/dev/r4/provenance.md` |
| 00:59 | M1 started (queue: G1, G2, F2 x 3 interleaved, block-p06, 4 cases each), then M2 queued. Credits 433.89 |
| 01:12 | Precedence gates 1-3 **PASS** on cand-wp c3102e1 (tag cand-wp.1; 792 passed; variant-c 3/3 exactly one ending_wins; 0/8 negatives). Adversarial review running. `runs/dev/r4/precedence-report.md` |
| 01:14 | D1/D2 blind derivation: **15/15 exact matches**; committed b7fe325 (o1-a.json 9 A, o1-b.json 3 B, extra-b-rederived.json); N4/N8 scripts clarified, blind re-check matched |
| 01:16 | **M1 done (36 calls): W = G1** (cand-g1.1 83f8263). Strict per case, 3 reps each (raw): G1 PUB-06 3/3, PUB-07 3/3, PUB-09 3/3, PUB-03 1/3; G2 2/3, 2/3, 3/3, 3/3; F2 0/3, 3/3, 2/3, 2/3. Newly failing vs F2: G1 none; G2 PUB-07 (rule 21 re-ask after a question back). PUB-03 fails in F2 too (common identity mechanism; see analysis-m1.md, incl. a LEDGER failure G1 r3 d10044ef: a complete wrong DOB in a cut-off message was never submitted). |
| 01:14 | M4/M5 fresh builds of G1 started (build-raw-w START 01:14:47) (exp-raw-w, exp-ab1-w); precedence ported onto G1 as cand-wp-g1 e1a32d4 (clean cherry-pick, 792 passed, gate-1 render diff on G1 for A and A+B = only the 3 ending_wins lines) |
| 01:19 | M4/M5 builds ok=True at 83f8263 clean: exp-raw-w a41f58d9 (27 steps, 8 tools), exp-ab1-w 768e75c2 (32 steps, 12 tools); smoke tests PASS. Queued after M3 |
| 01:21 | Precedence adversarial review: **SHIP-TO-O4** (no FAIL; `runs/dev/r4/precedence-review.md`). Its C1 (ending_wins row must not be the default negotiate row) and C2 (must follow every transferred entry) guards added on cand-wp-g1: **58a7473** (tag cand-wp-g1.1, committed 01:23), 794 passed; 19 saved specs: identical (empty) check_spec issues before/after; the spec-a-llm `--dry` render is byte-identical |
| 01:24 | O4 fresh builds of cand-wp-g1.1 started (exp-raw-wp, exp-ab1-wp) |
| 01:31 | O4 builds ok=True at 58a7473 clean: exp-raw-wp dafa86d5 (27 steps, 8 tools), exp-ab1-wp c02f4a9f (32 steps, 12 tools; its consolidation call to gpt-6.1-sol timed out after 240 s and fell back to gpt-5.5, 339 s build, documents=2 vs 1 for ab1-w; smoke reply "Am I speaking with Mr or Ms Reyes?"); both specs have 0 ending_wins (negative extraction 10/10 overall). Queued after M5 |
| 01:21 | **PLATFORM: M2 rep-2 simulation a36c1d01 stuck in "running"** (all 13 calls ended by 01:21:07, iteration completed, status not updated since 01:21:29). M2 rep 3 waits ("another simulation is running"). Per the user's rule: report only, no PUT/pause/stop; if still blocked at 01:52 UTC (30 min) simulations stop for the night |
| 01:15-01:21 | M2 A+B control (dev-ab-llm v14) styled-ab-all: rep 1 12/13 (PUB-03 identity), rep 2 10/13 (PUB-05 no tool calls, PUB-12 judge, PUB-13 asks_back declined). Analysis running |
| 01:53 | **STOP CONDITION: simulations stopped for the night.** a36c1d01 still "running" at the 30-minute mark (01:52:40). No PUT/pause/stop of the simulation (user rule). Local queue stopped (STOP flag) and the waiting M2 rep-3 client killed (it had launched nothing). Calls used: **62** (M1 36 + M2 reps 1-2 26). Not run: M2 rep 3 + M2 extra-B, M3, M4, M5 sims, O4 sims, O1. One push notification sent to the user. Offline work continues |
| 08:12 | **User instruction: pause the stuck simulation and resume.** `PUT /api/v2/simulations/a36c1d01… {"status":"paused"}` -> status paused (updatedAt 08:12:00); no other simulation running. STOP removed, queue resumed (244 calls queued; ledger 62) |
| 08:15 | M2 rep 3 (styled-ab-all): 10/13 (PUB-02 no tool calls/hang-up, PUB-03 identity I1, PUB-12 corrects artefact). **M2 styled-ab-all over 3 reps: 8/13 cases at strict 3/3** (fail: PUB-02, PUB-03, PUB-05, PUB-12, PUB-13) |
| 08:30 | M2 extra-B (styled-extra-b x3): PUB-11 1/3, PUB-12 0/3, PUB-13 2/3, but **4 of 6 calls in reps 2-3 have no judge verdict** ("analysis never arrived (300s)", platform), so those reps are invalid as measurements. Real failures: PUB-11 r2 LEDGER (closed not_verified/declined during identity: identity defect); PUB-12 r1, r3 judge (paid sentence / car-loan persuasion attempt) |
| 08:20-08:28 | `scripts/run_cases_retry.py` (user request): auto-pause of stuck simulations (4c677d1), then concurrency 13 + one automatic repeat of a rep without judge verdicts + review fixes (2b4f430). Active from M3 on |
| 08:36 | **M3: G1 (exp-g1-a) on styled-a x3 = 10/10 cases at strict 3/3 (30/30 calls)** vs F2 v8 control (styledA-a2-bd4da7c) 8/10 (PUB-03 2/3, PUB-06 2/3). Newly failing: none. Closes the PUB-07-pieces caveat (3/3). Note: M3 ran at concurrency 13, the control at 5 |
| 08:13-08:38 | **Identity fix v2 implemented** (user instruction) on branch `cand-id` off G1: c4186e7 (cand-id.1) -> 3 verifier lenses (conformance PASS-WITH-ISSUES LOW only; model-read 1 HIGH + 2 MED; replay 1 MED) -> fix round 48c8ab4 (cand-id.2: hint-retry rebuild, resend exception, year joining) -> recheck: all fixed, LOW only -> 63d1c19 (cand-id.3: neutral example year; a public case uses 1991). 778 passed; render vs G1 differs only in nodes.identity.task_message (1071 words) |
| 08:44 | exp-i12-a deployed (agent f652db08, wf 14cbdcaf) from cand-id.3 with `--spec runs/dev/spec-a-llm.json` after 2 platform failures (503 "API key validation is temporarily unavailable", 504, 500); export MATCH; vs exp-g1-a export only identity task_message differs. Chat probes skipped (chat API 504) |
| 08:47 | Identity A/B queued after O4, before O1 (user decision): gate R1/R2 x3 plain + asks_back on exp-i12-a; t1/t2/t3 interleaved rep by rep vs exp-g1-a; guard styled-a x3 on exp-i12-a. Runner handed over to qrun2.sh (CAP 400) |
| 08:58 | **M4: fresh raw-A build of G1 (exp-raw-w) on styled-a x3 = 8/10 strict** (reps 10, 9, 9; slow: platform 502/503/504 on polling). Newly failing vs M3 (G1 saved spec, 10/10): PUB-03 corrects 2/3, PUB-06 talkative 2/3. **Classified (09:03):** PUB-03 r2 02018082 = simulator (the 2nd scripted wrong DOB never arrived whole) + the common I1 cut-off loop: does not block. **PUB-06 r3 3f5a442c = AGENT (rule 26, floor offered twice): after a dated floor offer, a 2nd pure small-talk turn ("My cousin's wedding is on the 30th") got the offer repeated. Not extraction-caused (FACTS/negotiate texts equivalent); the gap is in the builder's ATTEMPTS text (only "a first reply to an offer that is only small talk" is exempted), so any build can hit it. Under binding condition 1 this BLOCKS W's promotion -> top of the morning list.** G1 PUB-06 so far: M1 3/3, M3 3/3, M4 2/3; F2: M1 0/3, styled-a 2/3 |
| 08:52-08:58 | Builder retry fix (user request): cand-retry cd13eb6 + 5af8b27 (backoff 5-120 s, up to 230 s per platform call; save retries fully only when unprocessed), merged into cand-id: **cand-id.4 = 2dcd0bd**, 788 passed, render byte-identical to exp-i12-a's (so the identity A/B measures cand-id.4). Adversarial review running. Runner handover to qrun2 (CAP 400) at 08:58 |
| 08:59-09:08 | Retry fix review (2 lenses, both FIX-NOW: save still failed on the exact 503/504/500 pattern; no 30-min deadline; smoke test retried a final 500; export ran after the optional smoke test) -> fix round 290d89d -> recheck OK -> test pin d53fa0e (cand-retry.4) -> merged: **cand-id.5 = ab60786**, 794 passed, render byte-identical to exp-i12-a. Remaining LOW (not done): a first attempt can still start after the 30-min limit (guard only on retries); stray-workflow WARN printed for a retry that the deadline then cancels |
| 09:22 | **M5: G1 fresh single-file A+B build (exp-ab1-w) on styled-ab-all x3 = 7/13 strict** vs M2 control (F2 v14) 8/13; newly failing PUB-04, PUB-10, PUB-11 (x2). All 4 newly failing calls are customer hang-ups after 20-60 s agent turns (PUB-04 r1 19.6 s; PUB-11 r1 51.6 s; PUB-10 r3 59.9 s; PUB-11 r3 59.5 s, mostly right after create_promise); rep 3 was discarded once for slowness (median 28 s) and its repeat kept at 11 s. M2 at concurrency 5 had 2-7 s. Reading: latency from concurrency 13 (+ platform degradation), not agent logic |
| 09:25 | User decisions: concurrency back to 5 (82c0b7b) from the next item; **re-run M5 x3 at 5** (39 calls) first; runner handover to qrun3 (CAP 450). Offer-wait fix being implemented on branch cand-idw (off cand-id.5), proposal `docs/proposals/2026-10-11-offer-wait-fix.md` |
| 09:27 | M5 extra-B (exp-ab1-w, styled-extra-b x3, concurrency 13): PUB-11 2/3 (r2 not_verified/declined in identity: I2), PUB-12 0/3 (judge: car loan asked "today" again after the opening question / no persuasion attempt on the car loan), PUB-13 3/3; vs M2 control 1/3, 0/3, 2/3 (partly unjudged): nothing newly failing. **PUB-12 extra-B fails on every build (F2 and G1, all reps): a consistent Brief B gap (rule 4 no today re-ask per product; per-product attempt on the early-band car loan)** |
| 09:12-09:33 | **Offer-wait fix implemented** (user instruction) on branch `cand-idw` off cand-id.5: b726812 (cand-idw.1) -> 3 verifier lenses (all PASS-WITH-ISSUES; 7 HIGH/MED) -> fix round 9e3c6f0 (cand-idw.2: dates/amounts inside small talk are part of the remark; "maybe"/"we'll see" are non-answers; answer any other question and stop, never re-ask) -> recheck LOW only -> 7c2a0e4 (cand-idw.3: two wording LOWs). 795 passed; render vs cand-id.5 differs only in system_prompt and nodes.negotiate.task_message (A, A+B, raw-A specs) |
| 09:34 | exp-idw-a deployed (agent 363717a9, wf 347b82c3) from cand-idw.3, `--spec spec-a-llm`; dry-run PASS, saved; **chat smoke test FAIL after the new retries (3x 504, chat endpoint degraded all morning) -> exit 3 = agent saved**. Export check pending (GET /workspaces 504s; retrying with long backoff). Offer-wait A/B (54 calls) queued after the identity A/B, before O1 (user decision); runner handover to qrun4 (CAP 500) |
| 09:38-09:50 | **PLATFORM OUTAGE**: GETs (simulation status, /workspaces) and POST /simulations return 504 after ~60 s each. M5 re-run (concurrency 5): rep 1 11/13; rep 2's simulation b0f503fb ran but its polls 504'd for ~8.5 min, the retry budget ran out and the client crashed (results not collected; 26 calls counted). O4-rawWP's POST /simulations 504'd (crash; whether a simulation was created is unknown until the platform answers). Queue STOPPED (09:49). `run_cases_retry` a5f1514: ~17 min of GET retries + a health gate (no start until a GET succeeds, up to 30 min). Resume plan: check for an orphan simulation, fix the ledger, re-queue O4-rawWP and M5 re-run reps 2-3 at the head |
| 10:08-10:16 | Freya answering again (credits OK; simulation list still 500/504 at times). Ledger fixed (O4-rawWP's failed POST created nothing: 0 calls). Queue resumed 10:09 with M5 re-run reps 2-3 + O4-rawWP at the head; blocked by orphan b0f503fb (M5 rep 2: client crashed in the outage, platform re-running 6 runs; list endpoint down so the auto-check could not see it) -> paused by hand 10:11 (standing user approval); M5r2 started 10:16 |
| 10:10-10:25 | **Offline prep (user choice 1-3):** (1) **cand-final = ca80d52, tag cand-final.1** (cand-idw.3 + precedence ce9aa68 + guards ca80d52): 820 passed; renders vs cand-idw.3 differ only in the 3 FACTS code nodes (ending_wins lines); fresh --dry extractions A, AB1, RAW, VC, VR all ok (VR needed one repair, as before), ending_wins exactly once in VC and nowhere else, identity/WAITING/rule-44 texts present, secrets clean. (2) **Perturbed-brief rehearsal** (`runs/dev/r4/perturbed-findings.md`): HIGH: an all-at-once verify_identity tool never reaches the all-at-once prompt path (check_spec demands question/answer fields, so the repair invents a per-answer mapping -> every verifiable case would fail); HIGH: a brief whose "too much" rule differs from Brief A's (floor on the next business day, not an attempt) is overridden by the builder's fixed too-much/ATTEMPTS text -> wrong promise date; MED: "this <weekday>" meaning is fixed in the DATE TABLE; LOW: float rounding of a percentage floor. (3) **RUNBOOK** updated (exit 3 with chat 504 = deployed, builder retries, freeze-final verification, outage check); fresh-clone --dry rehearsal of cand-final: ok (97 s, 2 model calls, git=ca80d52 dirty=False, secrets clean) |
| 10:31-11:22 | Platform still badly degraded (13-call rep ~33 min; unjudged calls; GET 504s). User: measure cand-final first but do not start; STOP set 10:35; queue reordered (FINAL-* first). M5r2 rep 1 (3d8c7da4) discarded for 2 unjudged calls, repeat 6d0c9464 running; **user: stop the current item** -> client terminated 11:14:50, simulation 6d0c9464 paused ~11:22. No valid M5r2 rep. Ledger 257. Nothing running, nothing new deployed. Engine chat handed over cand-eng.4 (cfa4d9d) and cand-eng.5 (27f5647), both unmeasured; cand-eng.3 superseded. Candidate selection by the user before any deployment (handoff in WORKING_STATE) |
| 02:00 | G1 candidate review: PROMOTE-WITH-CAVEATS (`runs/dev/r4/g1-review.md`) |
| 02:02 | Identity regression cases (D1/D2 4/4 exact) committed ffab7f3: `tests/fixtures/cases/identity-rd.json` |
| 02:04-02:23 | Identity-fix design v1 (f6f4824) -> 3 adversarial reviews, all ADOPT-WITH-AMENDMENTS (888fcdc) -> v2 resolving every HIGH/MED point (55cec38): `docs/proposals/2026-10-11-identity-fix-v2.md`. Not implemented |

## Infrastructure
- Simulation queue runner (only launcher): `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.sh`, queue `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/queue.txt`
  ("name slot casefile reps"), slot table `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/slots.tsv`, output `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.out`. Writes `runs/dev/r4/calls.tsv`
  and a `.meta.json` sidecar per run. `touch /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/STOP` stops it before the next item.
- Precedence worktree: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-wp` (branch cand-wp).
- Derivation scratch: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/derive/` (inputs/, d1.json, d2.json, o1-final.json, report.md).

## Results
(filled in as blocks finish)

## Candidate review (02:05): G1 = PROMOTE-WITH-CAVEATS (`runs/dev/r4/g1-review.md`)
Generic; renders correct on 16 saved specs; only the 3 intended lines differ from F2. Unmeasured MEDIUM risks, exactly
what the blocked M3/M4/M5/O1 were to measure: PUB-07 in pieces style (styled-a has it), customer-proposed date/amount
(o1-a PUB-05, o1-b PUB-12), Brief B on G1 (M5). Cheap code hardening (no sim): print the line only when the attempt-1
date is valid (today <= date <= deadline).

## Builder robustness finding (11 Oct 08:41, NOT fixed; generic bug fix candidate)
The deploy path has no retry on transient platform 5xx: `platform.dry_run` -> `kit.validate_workflow` (POST
?dryRun=true, idempotent) failed with 503 "API key validation is temporarily unavailable" and then 504/500; the build
ended ok=False (exp-i12-a needed 3 attempts). On Sunday the same outage would fail the hidden-brief build. Proposal:
retry the dry-run validation and the publish/save calls on 503/504 and on the "temporarily unavailable" message (the
request is rejected before it is processed), with bounded backoff inside the 30-min budget; never retry 4xx.

## TOP MORNING ITEM (09:03): G1 promotion blocked by M4 PUB-06 r3 (agent-caused)
Rule 26 "offer the floor, once": a 2nd small-talk turn after the dated floor offer made the model repeat the offer
(call 3f5a442c, J11-J12). Builder text gap (ATTEMPTS exempts only a first small-talk reply). Decision for the user:
promote G1 anyway (its PUB-06 record 8/9 vs F2 2/6 on the same case), or fix the ATTEMPTS gap first (generic: after an
offer, any number of turns that are only small talk or cut off get "Please go on."/a short acknowledgement and never a
repeated offer) and re-measure PUB-06 talkative.

## Sunday RUNBOOK note (09:37): exit 3 with a chat 504
With the chat endpoint degraded, a build can end exit 3 ("agent saved, smoke test failed") purely because POST
/api/v2/chat/message returns 504 while simulations work. If the trace shows CREATED/saved, platform dry-run PASS and
only the smoke test failing with 504/503, the agent is deployed; re-running costs build time (tie-break) and adds no
information. Update `docs/RUNBOOK.md` before the freeze.

## Demonstrated correctness gaps (morning proposals; generic; NOT implemented overnight)
1. **Identity: a complete security answer inside a cut-off message is not submitted** (LEDGER failures: M1 G1 r3
   d10044ef promise recorded after 3 wrong DOBs; M2 r1 79778b2e declined instead of failed). Common to every arm.
   Fix proposal: format-based completeness (day + month + 4-digit year, also a year in words; digits:N) -> call
   verify_identity at once; a cut-off fragment never counts as a rule-15 refusal; cut-off handling must terminate
   (identity re-asks the question in short form from the 3rd cut-off); identity max-turn exit gets a spoken line.
   `runs/dev/r4/analysis-m1.md`, `analysis-m2.md`.
2. **Identity: "Why do you need that?" after an answer is counted as a 2nd decline** -> not_verified/declined
   (M2 r2 PUB-13 68d28036, LEDGER; render.py:257 groups "why you need it" with "what the call is about"). New.
   Needs a real-decline regression case first.
3. Rule 21 re-ask of the exact day after a question back (G2 r2 PUB-07; also F3). Proposal: global "answer a question
   back without repeating your question in that message".
Size (all 906 stored calls, `runs/dev/r4/analysis-identity-history.md`): I1 = 11 failed calls, all PUB-03, corrects-style
PUB-03 fails ~30% (7/23) on every recent build; I2 = 2. In the latest styled runs ~5 of 15 failing case-results would
flip with I1+I2 fixed; the other 10 are PUB-06 floor offers (6, the G1 target), PUB-07 re-ask (2), hang-ups (2).
Test/simulator artefacts (do not tune): PUB-12 corrects merges two phone answers; silent customer hang-ups
(29041b61, 3575e933); leaked simulator reasoning (704c184a).
