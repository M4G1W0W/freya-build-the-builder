# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-11 03:45 Istanbul (00:45 UTC Sun). Last commit: see `git log`. Hidden briefs open Sun 11 Oct
17:00 UTC (about 16 h from now). Tags: `good-pre-f1` = the builder before Saturday night's FACTS changes;
`cand-f2` = bd4da7c (F2); `cand-f3` = a069dd2 (F3, the builder code at HEAD).

## OVERNIGHT EXECUTION IN PROGRESS (autonomous, user asleep; read this first)

The live log and morning handoff is `docs/plans/2026-10-11-overnight-report.md`. A coordinator session runs the plan under
the user's final authorization (00:50 UTC). Only that coordinator launches simulations (queue runner in its
scratchpad, see the report). G1 = cand-g1 83f8263, G2 = cand-g2 0bc83c4, case files on main 322dfc9.
**01:53 UTC: simulations STOPPED for the night** (platform simulation a36c1d01 stuck "running" since 01:21:29; per the
user's rule no PUT/pause/stop). If it is cleared (user decision), the remaining queue is in the report: M2 rep 3 +
extra-B, M3, M4, M5, O4 (slots exp-raw-w, exp-ab1-w, exp-raw-wp, exp-ab1-wp are already built), O1. W = G1.

## TONIGHT: execute the APPROVED overnight plan v2 (start here)

**`docs/plans/2026-10-11-overnight-plan-v2.md` is the plan the user approved** (about 00:35 UTC). It carries the
user's binding conditions, the verified slot provenance, the mechanics, the must-finish blocks M0–M5, the optional
blocks, the budget, the stop conditions and the approvals. Follow it exactly. The decision is in the hackathon_notes
Decision log (11-10 00:35).

Execution stopped at 00:40 UTC for a context save. **Nothing is running.**

**Done:**
- Credits: 433.89 (00:37 UTC).
- At HEAD: 769 passed, lint clean.
- Tags `cand-f2` and `cand-f3`.
- Worktrees `wt-g1`, `wt-g2` and `wt-f2` in the old session's scratchpad:
  `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/4f150fc6-b7a9-4d54-bc9f-33f85e684098/scratchpad/`.
  They may be gone; the branches `cand-g1` and `cand-g2` exist at a01a17c.
- The G1 and G2 edits are untested and uncommitted. They are saved as `runs/dev/r4/cand-g1-uncommitted.patch` and
  `runs/dev/r4/cand-g2-uncommitted.patch`.

**Next:** finish M0 (plan, "M0"): test and commit G1 and G2 on their branches; write the three case/brief files;
verify the exports; then M1.

**Binding user conditions** (repeated from the plan):
1. Any newly failing agent-caused or unexplained case blocks promotion, fresh builds included.
2. The precedence change stays isolated until it passes 3/3 variant-C extractions, the negative checks and the
   fresh-build regression.
3. Export-only fields may be ignored only once verified as harmless defaults.
4. **No B-date tonight.**
5. 340 calls is the absolute overnight cap, retries included; keep the Sunday reserve.
6. If time runs short, M2, M4 and M5 come before optional work.

## Phase

- **Phases 1–2 (Briefs A and B):** working.
- **Phase 3 (robustness):** today's afternoon: a generalisation audit (fixed), customer speech styles, then a
  **direction review against the live page** (`docs/reviews/2026-10-10-direction-review.md`, 20 ranked gaps,
  skeptic-checked). Gaps 1, 2, 3, 5 and 6 are fixed (16:47–16:57 UTC); gap 4, the measurement, is running.
- **Phase 4 (submission):** RUNBOOK, `scripts/check_secrets.py`, the fresh-clone build, the 3.10+ guard: done. Open:
  review gaps 12 and 14 (RUNBOOK: one brief file only; `mkdir -p traces submission`, explicit `--slot hidden-N`, a
  rehearsal), the freeze and the Sunday run.

## USER (read this first)

- **Team Pistalogic. The repo stays PRIVATE for now**; the user will share it or make it public later.
- **The user's voice test is done** (call 577a2cd4 on `voice-test`, an off-script customer). Findings are in the
  hackathon_notes Observations (16:12) and became fixes 557161d (direct transfers) and the read-back point (gap 18,
  open, low). `voice-test` and `dev-a-llm` may now be redeployed.
- **Dashboard tips for the user:** the editor's ⋮ menu → Organize lays out the nodes (the API refuses
  `nodePositions`). The dashboard has its own test customer for test calls (DOB 14 March 1988, last four 4471; FAQ).
- **The user should email the organisers (gap 1):** how to supply the builder's model key for the top-10 re-run. A
  draft was given in the chat. The code side is done (77fb337: default model chain in code, README re-run section).
- The user wants careful development, measurement of everything, and a word when something is ready for feedback.
  Ultracode is on: use the Workflow tool for substantive work.

## Saturday night's queue (historical; nothing is running now)

- **qrun3** (`<scratchpad>/qrun3.sh`, queue `queue3.txt`, output `qrun3.out`, result names `-bd4da7c` whatever the
  agent): **G1-p06-talkative finished 22:54: 2/3**; the queue runner has stopped and nothing is running. **G2 was NOT run** (removed from the queue at the user's request; run it next session: `exp-g2-a` agent efb690fd, `--only PUB-06 --style talkative --reps 3`). When it
  ends, the runner prints "queue empty" and stops. Read `runs/dev/r3/G1-p06-talkative-bd4da7c.json` / `G2-...`.
- All runs use `scripts/run_cases_retry.py` (GET 5xx retries + report-only STUCK detection, fed67b1). A stuck
  simulation was paused once with the user's OK (21:55 UTC); **ask again before any further PUT** on Freya.
- `<scratchpad>` = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/84c40ea0-ff94-472f-b564-a8a424800981/scratchpad`
  (may be gone after a restart; the queue runner is just: pop a line "name agent brief args", run
  `scripts/run_cases_retry.py <agent> --brief <b> --reps 3 --out runs/dev/r3/<name>-<sha>.json <args>`, repeat).

## Builder state tonight (all committed; read the Score log rows 10-10 22:28 to 11-10 "running")

| Name | Commit | What | PUB-07 (6 calls) | PUB-06 talkative | Full sets |
|---|---|---|---|---|---|
| HEAD before | c45758f (= aa94ccb code) | | 1/6 | 3/3 (pre-F1 8/8 calls) | styled-a 7/10 (a8b70ea) |
| F1 | 15bcbad | no DATE TABLE period rows; no separate too-much FACTS line | raw 3/6 (adjusted 4/6) | **1/3 (regression)** | styled-a 6/10 |
| F2 | bd4da7c | F1 + DATES: "start your reply to a named date with that date as written in FACTS" | **6/6** | **2/3** in styled-a (raw JSON; was misrecorded as 1/3) | **styled-a 8/10** (PUB-07 3/3) |
| F3 = **HEAD code** | a069dd2 | F2 + too-much rule on the attempt-1 line and OFFER PLAN item | raw 5/6; dates 6/6 (1 judge fail: re-asked after a question back) | **1/3** (still "floor ... today?") | not run |
| G1 (candidate) | a069dd2 + `runs/dev/exp07/g1-on-a069dd2.patch` | F3 + the old trigger line "IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH ... offer exactly the floor X on <date> ... not today" | not run | **2/3** (r1: floor offered twice, call bfe80eb8, not yet read) | |
| G2 (candidate) | a069dd2 + `exp07 offerdate` | F3 + ATTEMPTS: "Each offer of yours names its amount and its date as written in FACTS; the only today question is the opening one" | not run | **not run (cancelled for the context save)** | |

**Next steps: superseded by `docs/plans/2026-10-11-overnight-plan-v2.md`.** The list below is Saturday's, kept for
history:
1. Read G1 and G2 PUB-06. Pick the one that fixes PUB-06 (target 3/3), then run PUB-07 asks + pieces on it (the
   too-much line once interacted with PUB-07, but that needed the period rows, which are gone, and echo-date was
   not there). Adopt the winner into the builder (G1 = apply the patch; G2 = move the sentence into render.py), with
   a regression test, commit, tag.
2. Deploy the winner to dev-a-llm2 and dev-ab-llm (`--spec runs/dev/spec-a-llm.json` and
   `--spec runs/dev/spec-ab-llm-c45758f.json`), then the four styled sets: styled-a, styled-ab-a, styled-b,
   styled-extra-b. The A+B sets have **not** been measured since c45758f (styled-ab-a 6/10 there; extra-B was cut by
   the stuck simulation at reps 1/3, 1/3).
3. Pending user decisions: PUB-05 fix (no improvised offers after refusing something the brief forbids); review
   finding 2 (`event_row_in` precedence for an ending that overrides a recorded promise, variant-c rule 47).
4. Generic follow-ups found tonight (not started): the identity step's "answer a question back, do not repeat your
   question in that message" made global (F3 PUB-07 asks r2); a message ending in "." is complete even if it ends on a
   number word (F1 PUB-03 r1: a full DOB got "Please go on."); never ask "how much can you pay" (one echodate call).
5. Classify the extra-B c45758f reps 1-2 failures (PUB-11 x2, PUB-13, PUB-12; Score log row 11-10 00:54).
6. Freeze about Sun 15:30 UTC (tag `freeze-final`); from 17:00 UTC follow `docs/RUNBOOK.md`.

**Slots** (verified provenance is in the plan; dev-a-llm2 v8 was built at 71add36, which has the same code as bd4da7c;
dev-ab-llm v14 was built at bd4da7c with `spec-ab-llm-c45758f.json` and is **unmeasured**; the last measured A+B is
v13 at c45758f): dev-a-llm2 = F2 v8 (7cfc34a8 / 2485fc27); dev-ab-llm = F2 v14 (f8f9b203 / b867b809); exp-f3-a 35098a88;
exp-g1-a 31f79439 (dirty G1 build); exp-g2-a efb690fd; exp-p07-* (throwaway). About 30 workflows of 200 used.
dev-a-llm (52b947c v6) and voice-test unchanged.

**Results so far tonight** (styled = every case in one of the 5 kit speech styles; a case counts at 3/3):

| Set | 676e9df (17:00) | a8b70ea (17:55) | What is fixed since a8b70ea (not yet measured) |
|---|---|---|---|
| A agent, styled-a | 7/10 | 7/10 (2 simulator, 1 sandbox-output, PUB-07) | bd944df size revert; aa94ccb period rows |
| A+B, styled-b | 2/3 | 2/3 (script/style conflict only) | |
| A+B, styled-extra-b | 1/3 | 2/3 (paid sentence, "today?" re-ask) | 92d91ea |
| A+B, styled-ab-a | 5/10 | 7/10 (PUB-08 no note, PUB-07) | 39d7dd9 auto-notes; aa94ccb |

Every failure is read and classified in the Score log (rows 10-10 20:09 to 21:35).

**Open problems:** see "Next steps" above (they replace the earlier list).

## Latest measured results (3 reps unless marked; a case counts only at 3/3)

| Agent (slot) | Code | Brief | Result | Notes |
|---|---|---|---|---|
| dev-a-llm | 52b947c | A | **20/20 calls** in the 2 clean reps | rep 3 was the sandbox outage; given to the user |
| dev-a-fixture / dev-a-llm | 90b737d | A | **10/10** each | |
| dev-raw-a (raw-material Brief A) | fe1d7ef | A | **10/10** | |
| dev-ab-llm | 52b947c | B | 3/3 in every clean rep | the other reps were sandbox bursts |
| dev-a-llm2 | 19664c6 | A talkative, 1 rep | **9/10** (was 6/10) | the remaining one is the "Please go on." loop, fixed in a1499a8 |
| dev-ab-llm | 19664c6 | B talkative / pieces, 1 rep | **3/3, 3/3** (were 2/3) | |
| dev-a-llm2 | 19664c6 | A pieces, 1 rep | **10/10** (was 8/10) | |
| style sweep | 52b947c | A asks_back / corrects / in_words | 10/10 each | |

| dev-a-llm2 | 276302f | A talkative, 1 rep | **6/10**, 0 platform errors | fragment rule: a cut-off yes ignored (PUB-07), offers repeated (PUB-05/06), third_party cap hit (PUB-02); PUB-06 also resolved "this Friday" as 17 Oct. Fixed in 557161d except the date slip |

The Score log in `docs/hackathon_notes.md` has every run with its reasons. The extra-B cases
(`tests/fixtures/cases/extra-b.json`: refuse-all, paid+dispute+refused, all-paid) were checked on Freya at 52b947c:
the ledger was correct in every clean rep. Their styled 3-rep run is in chain4.

## What changed this evening (16:47–16:57 UTC, from the direction review)

- 3a55e6d: `kit/` is now the official **kit v3** (only README and examples differ from v1); the live page snapshot is
  `docs/reference/hackathon_page_live_2026-10-10.md`.
- 77fb337 (gap 1): `llm.DEFAULT_MODELS` gpt-6.1-sol → gpt-5.5 → gpt-5.4 in code; env models go in front. README
  "Organiser re-run" section: only FREYA_API_KEY and OPENAI_API_KEY are needed.
- 773b0dd (gap 2): `spec.product_slots()` = max(3, extracted max_products), from the page's "one to three
  products". **Every agent now has 3 product slots**, the Brief A agent included; the trace warns when the brief was
  read as fewer.
- 557161d (gaps 3, 5, 6): a cut-off message is read first and its yes/no/date/amount/answer/request acted on;
  never repeat a question, offer, amount or date because of a cut-off; caps opening 25, third_party 40, identity 40,
  negotiate 120; endings whose rule says transfer or close happen at once, ask first only when the rule says so.
- 676e9df: `scripts/make_style_cases.py` and `tests/fixtures/cases/styled-*.json`.
- 1a5245f (gaps 10, 12, 14): trace START has sha256 of inputs, git commit, dirty flag, python, model chain; RUNBOOK
  Sunday mechanics (mkdir/pipefail, `--slot hidden-N`, verified greps, one brief file, same commit in both traces).
- 96c37ad: negotiate joins dates and amounts given in parts.
- 7dadfcb (gap 8a): `spec.engine_fields` fills new required fields on get_account/close_call/transfer_to_agent.
  **Gap 8b (all-at-once verify_identity) deferred**: speculative without the API shape.
- 1bd07ee (gap 15): smoke test sends a real `now`; a failed smoke test ends `ok=False`, exit 3.
- 35c030a: loop breaker "Sorry, your message was cut off. Could you answer in a few words?" on a second cut-off;
  FACTS states the floor offer's date (attempt 1); DATES: never pair weekday and date from memory.
- dcb3915 (gap 13): 25-min model-call budget, 240 s per call, a stall falls back, repair skipped under 5 min.
- 4e6629f (gap 16): variant-c/-r rebuilt at dcb3915 with the real LLM (both PASS, 11 tools) and are pytest fixtures.
- e233cb8: with notes, note-derived rows are no negotiate ending; NOTES says do the ending's duty, then note.
- 347e01d: diff-review fixes (note endings stay; deferred notes; one "complete" definition; transfer precedence; failed repair keeps the best spec; engine_fields checks). a8b70ea: the loop breaker covers repeated parts.
- bd944df: EVERY DAY weeks (a3e6c77) reverted after a sandbox-output failure; size guard test.
- 92d91ea: the forbidden "can you pay <product> today?" named; extraction turns "say that X" into sentences.
- 39d7dd9: note-derived endings add missing notes in code (an_<k> chain; platform dry run valid).
- aa94ccb: "next week" / "the week after next" rows list their seven days.
- `make verify`: **759 passed**.


## What changed earlier today (all committed; details in the Decision log and git log)

- **Notes path:**
  - The goodbye-with-note stall was fixed structurally. A deterministic notes-done route goes to `ev_notes` /
    `ev_notes_p`, fixed closing lines with no model turn.
  - finalize reads note reasons from `<tool>_args.arg_<field>`. Before this, no note-derived outcome ever worked.
- **Negotiation:**
  - an ATTEMPTS procedure;
  - an OFFER PLAN line;
  - no "today" re-ask;
  - DATES: weekday phrases are resolved first; week rows "next week" and "the week after next";
  - read-back honesty.
- **Customer speech styles:**
  - a cut-off message gets "Please go on." (a second one in a row gets the last question again);
  - identity answers in parts are joined;
  - no restated security question after a question back;
  - sympathy only where a rule asks;
  - situation-tied options only after the customer described the situation.
- **Generalisation audit fixes:**
  - the build deploys the best spec with UNRESOLVED warnings instead of aborting;
  - the notes route uses our slot ids;
  - identity gate fields must be booleans;
  - a build-time date self-test (`datecheck.py`) runs inside the repair loop;
  - a combined callback field;
  - third_party gets the "who answered" endings;
  - API field descriptions are kept;
  - customer-id field resolution;
  - note/close reason row checks;
  - `floor_percent`;
  - LLM fallback on 429/5xx and on missing json_schema support;
  - tolerant brief decoding;
  - a redacted traceback;
  - engine-call required-field warnings;
  - a smoke-test retry.
- **Tools:** `scripts/voice_test.py`, `scripts/check_secrets.py`, `tests/fixtures/briefs/raw-a.md`,
  `tests/fixtures/cases/extra-b.json`.
- `make verify`: **721 passed**.

## Deployed slots (`.freya-agents.json`, gitignored)

| Slot | Workflow | Agent | State |
|---|---|---|---|
| dev-a-llm | 81c14d7a-c622-49e2-98fb-8cd347ef4ac2 | c6a57c76-a3ea-42cc-9cfb-7eb8773b9436 | **FROZEN v6 (user testing)** |
| voice-test | 39e29145-bb65-47ec-9f95-24bbd2286502 | cdd31f6c-f48c-4a6f-b0e8-3d5323b0f26c | copy of dev-a-llm + test_variables |
| dev-a-llm2 | 7cfc34a8-5b97-4bfc-a3a8-b4e884c4dd96 | 2485fc27-f1d4-47e1-ab89-a1a86fd12a87 | **A control: v8 at 71add36 (= F2 code), spec-a-llm.json. Never overwrite overnight** |
| dev-ab-llm | f8f9b203-66ae-43e1-9d37-82e76d26b762 | b867b809-5d2b-4e75-935f-1ed6086432c3 | **A+B control: v14 at bd4da7c, spec-ab-llm-c45758f.json, unmeasured. Never overwrite overnight** |
| exp-g1-a / exp-g2-a / exp-f3-a | 5f39ed9a… / 4d64b871… / c2a1e221… | 31f79439… / efb690fd… / 35098a88… | G1 (dirty build) / G2 (exp07 runtime variant) / F3; all spec-a-llm.json |
| dev-a-fixture | 349752be-0764-4025-9e5f-4248a6fe6bff | f0354c17-f459-4d7a-bfef-62acea2e5cd7 | v5 (52b947c era) |
| dev-raw-a | 7286c0bd-223f-4185-a61a-a7fedd43279b | eb321c47-0eb5-4ceb-9624-a3012d3c1957 | fe1d7ef |
| brief-a, brief-a+brief-b | e2f7b97e… / aab4bc00… | 23c6c141… / 6afab2aa… | kit baseline |

Saved specs for `--spec` redeploys (no LLM): `runs/dev/spec-a-llm.json`, `runs/dev/spec-ab-llm.json`,
`tests/fixtures/spec_a.json`. All now have `floor_percent`.

## Next steps (in order)

1. Read chain4's four results as they land (`runs/dev/r3/*-676e9df.*`), log them in the Score log, read every failure
   transcript, classify platform vs real. Real failures get a generic fix and a regression test. Watch especially:
   the Brief A agent with 3 slots (a change from 1), talkative/pieces cases, PUB-09 transfers directly, PUB-06 dates.
2. If the styled numbers hold, refresh `dev-a-llm` / `voice-test` to HEAD for the user and tell them it is ready.
3. Remaining review gaps (`docs/reviews/2026-10-10-direction-review.md`), by value:
   - 14 + 12 (RUNBOOK mechanics, 20 min): `mkdir -p traces submission`, `set -o pipefail`, explicit
     `--slot hidden-1/2`, builds one after the other, real TEST strings, exactly one brief file; then a full rehearsal.
   - 10 (30 min): commit, dirty flag, argv and model chain in the trace START line; re-run both briefs after any fix.
   - 7 (1–2 h): a generic "ending overrides a recorded promise" close option (variant-c rule 47).
   - 8 (2–4 h): changed tool APIs (a new required field on close/transfer; verify_identity taking all answers).
   - 9, 11: other call days/hours (`--now` for scripts/chat.py), time-of-day and non-floor amount rules.
   - 13, 15, 16, 17, 18, 19, 20: low.
4. Freeze about Sun 15:30 UTC (tag `freeze-final`). From 17:00 UTC follow `docs/RUNBOOK.md`.

## Platform facts learned today (details in the hackathon_notes Observations)

- **Outages:**
  - Freya was down 13:41–14:14 UTC (chat 503, silent agents).
  - The sandbox ("snekbox") was unreachable in bursts until about 14:50 UTC.
  - The mock bank returned Cloudflare 1101 from 15:33 to 15:54 UTC.
  - Probe before blaming code: `scripts/chat.py` for Freya, POST `/v1/practice/sessions` for the bank.
- **A post-hook failure** makes the tool call an error even though the bank recorded it (duplicates).
- **Passthrough code-node `tts` lines** are spoken when the call ends (after close_call).
- **A passthrough conversation node** waits for the customer.
- **An `llm` entry line in a tool-less node** can be blocked, and the platform then speaks a Turkish filler.
- **Simulated customer turns arrive cut off mid-sentence**, especially under the talkative style.
- **The `test_variables` of a workflow** reach chat and web calls (verified).

## Gotchas

- Use bash for chain scripts: zsh does not word-split `$var`, which twice produced runs that never simulated.
- Only one simulation can run at a time. Stopping a run_cases client leaves its simulation running for about 2
  minutes.
- `runs/` is gitignored: tests must not depend on it.
