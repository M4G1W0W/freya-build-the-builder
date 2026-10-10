# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-10 19:08 Istanbul (16:08 UTC). Last commit: see `git log` (after `7fb6ba0`). Hidden briefs open
Sun 11 Oct 17:00 UTC (about 25 h from now).

## Phase

The phases come from `docs/design.md` §7:
- **Phases 1–2 (Briefs A and B):** working.
- **Phase 3 (robustness):** most of today's work.
  - A generalisation audit: 6 auditors + critic, 81 findings. The score-relevant ones are fixed.
  - Customer speech styles: diagnosed and fixed.
  - Extraction reproducibility: measured.
- **Phase 4 (submission):**
  - Done: RUNBOOK, `scripts/check_secrets.py`, the fresh-clone build (110 s, stdlib only), the Python 3.10+ guard.
  - Open: the freeze and the Sunday run.

## USER (read this first)

- **Team Pistalogic. The repo stays PRIVATE for now**; the user will share it or make it public later.
- **The user is testing the Brief A agent `dev-a-llm` (frozen at v6, code 52b947c)** through the slot `voice-test`:
  - workflow `39e29145-bb65-47ec-9f95-24bbd2286502`, agent `cdd31f6c-…`;
  - it is a copy with `test_variables` for practice customer PUB-01 `c_946ea8ba-608`, still unused at 15:58 UTC.
  - `scripts/voice_test.py 81c14d7a-c622-49e2-98fb-8cd347ef4ac2 --case PUB-07` gives the copy a fresh customer.
  - **Do NOT redeploy `dev-a-llm` or `voice-test` until the user's feedback is in.**
  - When the user says "done", pull the call (`scripts/show_call.py`, the bank ledger) and go through it with them.
- The user asked about running the builder's LLM on Freya. Our recommendation is no (see the Decision log, 16:55).
  **Open:** how the organisers get an OpenAI key for their re-run. The user should ask on the support channel.
- The user wants: keep developing carefully, measure everything, and say when something is ready for their feedback.
  Ultracode is on: use the Workflow tool for substantive work.

## Running right now

- **16:06 UTC, NEW FINDING (read first):** A talkative at `276302f` (dev-a-llm2, with a1499a8's bounded "Please go
  on.") is **6/10** with **0 platform errors**: real failures.
  - "Please go on." appears 5–46 times per failed call (PUB-06: 113 turns, the floor offered 4 times, a wrong date).
  - PUB-02: no callback booked. PUB-05: support offered twice. PUB-07: no close_call.
  - At 19664c6 (without the bound) the same style was 9/10 (1 rep; variance is high).
  - **The fragment handling is fragile.** Next session:
    - read these 4 calls (`runs/dev/style/a2-talkative-r1-276302f.json`, `all_rows`);
    - compare with 19664c6;
    - decide, e.g. revert a1499a8, or limit "Please go on." to identity, or reply to the content so far without
      counting it.
  - Measure at 3 reps before trusting any 1-rep number.

- **chain3** (`<scratchpad>/chain3.sh`, background job `b6aj25921`, monitor `b1miemwej`). The mock bank recovered at
  15:54 UTC, then the chain deployed HEAD `276302f`: dev-ab-llm v9 and dev-a-llm2 v2. It then runs, in order:
  - styles at 1 rep: A talkative (started 15:56 UTC), B talkative, B asks_back, B in_words;
  - then 3 reps: a2A, abB, extraB.

  Results go to `runs/dev/style/*-276302f.*` and `runs/dev/{a2A,abB,extraB}-r3-276302f.*`. **Log each in the Score
  log** and read every failure (`all_rows` in the result JSON).
- `d2195cf` (the smoke-test retry) is build-time only and is not part of chain3; nothing to redeploy for it.

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

The Score log in `docs/hackathon_notes.md` has every run with its reasons. The extra-B cases
(`tests/fixtures/cases/extra-b.json`: refuse-all, paid+dispute+refused, all-paid) were checked on Freya at 52b947c:
the ledger was correct in every clean rep. They still need a clean 3-rep run (it is in chain3).

## What changed today (all committed; details in the Decision log and git log)

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

1. Read chain3's results as they land, log them in the Score log, and read every failure transcript. Classify each
   failure (sandbox / bank / platform vs real). Real failures get a generic fix and a regression test.
2. When the user reports on their dashboard/voice test: pull the call and the ledger, discuss, and fix generically.
   Only after their feedback: refresh dev-a-llm to HEAD (or point voice-test at dev-a-llm2).
3. If B and extraB are clean at 3 reps: tell the user the multi-product agent (dev-ab-llm) is ready for their test
   (make a voice-test copy of `f8f9b203…` with `--case PUB-12` or an extra-b case).
4. Remaining deferred audit items, if time allows:
   - F16: attempt amounts other than full/floor;
   - F42: an "override" precedence rule (insolvency-style);
   - F44/F45: ev_notes loses the event row's say_before_end;
   - critic "uncovered": get_account returning a single object; create_promise without a product field;
     time-of-day rules.
   - Weigh plausibility; each needs a schema change plus fixture updates.
5. Freeze about Sun 15:30 UTC (tag `freeze-final`). From 17:00 UTC follow `docs/RUNBOOK.md` (which now lists the new
   trace signals to grep).

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
