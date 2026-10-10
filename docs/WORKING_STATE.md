# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-10 20:25 Istanbul (17:25 UTC). Last commit: see `git log` (after `676e9df`). Hidden briefs open
Sun 11 Oct 17:00 UTC (about 23.5 h from now).

## Phase

- **Phases 1–2 (Briefs A and B):** working.
- **Phase 3 (robustness):** today's afternoon: a generalisation audit (fixed), customer speech styles, then a
  **direction review against the live page** (`docs/reviews/2026-10-10-direction-review.md`, 20 ranked gaps,
  skeptic-checked). Gaps 1, 2, 3, 5 and 6 are fixed (17:00–17:25 UTC); gap 4, the measurement, is running.
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

## Running right now

- **chain4** (`<scratchpad>/chain4.sh`, background job `b9brwzcqx`, started 17:25 UTC at `676e9df`):
  deploy dev-a-llm2 (spec-a-llm, now with 3 product slots) and dev-ab-llm (spec-ab-llm) from saved specs, then
  four styled 3-rep runs, one at a time:
  1. `styledA-a2`: dev-a-llm2 on `tests/fixtures/cases/styled-a.json` (Brief A, each case one of 5 styles);
  2. `styledB-ab`: dev-ab-llm on `styled-b.json`;
  3. `styledXB-ab`: dev-ab-llm on `styled-extra-b.json`;
  4. `styledABA-ab`: dev-ab-llm on `styled-ab-a.json` (Brief A cases with A+B ledgers: PUB-05 and PUB-08 get notes,
     Brief B rule 8).
  Results: `runs/dev/r3/<name>-676e9df.{json,log}`, deploy logs `runs/dev/deploy/*-676e9df.log`. **Log each in the
  Score log** and read every failure (`all_rows`). Classify platform vs real before changing code.
- chain3 (276302f) died with the previous session after its first run (A talkative 6/10, 0 platform errors). Its
  four failures were read (`runs/dev/style/calls-276302f/`) and fixed in 557161d.

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

## What changed this evening (17:00–17:25 UTC, from the direction review)

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
- `make verify`: **725 passed**.


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
| dev-a-llm2 | 7cfc34a8-5b97-4bfc-a3a8-b4e884c4dd96 | 2485fc27-f1d4-47e1-ab89-a1a86fd12a87 | A LLM spec at HEAD (v2 = 276302f) |
| dev-ab-llm | f8f9b203-66ae-43e1-9d37-82e76d26b762 | b867b809-5d2b-4e75-935f-1ed6086432c3 | A+B LLM spec at HEAD (v9 = 276302f) |
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
