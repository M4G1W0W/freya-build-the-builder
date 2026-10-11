# WORKING STATE: update at every context save

Read `docs/PROJECT_OVERVIEW.md` first (the whole project). This file is the **current** state. Before acting, check
`date` and `git status` and compare them with the snapshot below.

**Snapshot:** 2026-10-11 19:20 Istanbul (16:20 UTC Sun). Last commit: see `git log`. The final case opens **17:00 UTC**
(20:00 Istanbul, ~40 min from now); submission closes 20:00 UTC (23:00 Istanbul). Tags: `cand-f2` = bd4da7c (F2),
`cand-f3` = a069dd2 (F3; no longer main's builder code), `cand-g1.1` 83f8263, `cand-retry.4` d53fa0e, `cand-final.1`
ca80d52, `cand-eng.4` cfa4d9d, `cand-eng.5` 27f5647, `cand-eng.6` a170935, `cand-eng.7` a985076, `cand-eng.8` 4267bb0, `cand-eng.9` b103e21, **`freeze-final` b9756fe** (= main 8e251fe's builder code).

## UPDATE 16:28 UTC: MOCK DEPLOYED (simulation chat)

- The user registered the workers.dev subdomain `atlasreyiz` and opened the worker `teampistalogic` (it served the
  onboarding "Hello World!"). `mock/wrangler.toml` name -> `teampistalogic`; deployed (version 92b9273c) at
  **https://teampistalogic.atlasreyiz.workers.dev**; secrets `ADMIN_TOKEN` / `TEAM_KEY` set from `.env`
  (`MOCK_ADMIN_TOKEN`, `MOCK_TEAM_KEY`, random, never printed). **`MOCK_URL=https://teampistalogic.atlasreyiz.workers.dev/v1`
  in `.env`.**
- Live smoke (live run, deployed version): health 200; admin/practice endpoints 403 without the token/key; unknown
  customer 404; get_account before verify 403 "identity not verified"; wrong DOB counted (wrong_answers_left 2);
  DOB + phone -> all_verified; get_account, create_promise ok; 2nd promise on p1 409; close_call ok. The kit scorer
  (`kit/tools/score.py` http + score_ledger, `FREYA_BANK_HOST`=mock origin, `FREYA_BANK_TEAM_KEY`=MOCK_TEAM_KEY) passes
  the good session and fails the bad one for the right reasons. Scripts: this session's scratchpad `smoke_mock*.sh`.
- `run_cases.py` posts `{"case": <case id>}`: our post-17:00 case ids must equal `customer_id`s in `data/customers.json`.
- Still the practice-kit tool semantics: after 17:00, adapt `src/bank.js` + `data/customers.json` to the zip's
  service contract and redeploy (`cd mock && CI=1 npx --yes wrangler@4.149.0 deploy`; secrets persist).
- `cand-final.2` not tagged yet (`cand-final-2-work` = 3abfd22 at 16:28). **16:30: Methodology tagged `cand-final.2` =
  3abfd22** (941 passed; merge with main clean). Freeze decision (new tag vs moving `freeze-final`) = the user's.

## UPDATE 17:23 UTC: FINAL CASE ARRIVING; frozen builder CRASHES on it; user D6 = case-blind generic fallback

- **Case folder: `/Users/atlasdenizakbulut/Desktop/Freya Final case`** (outside the repo). The client sends documents
  over ~1 h (user 17:16: "they are simulating it like a client is sending docs"). At 17:12: `BRIEF.md` +
  `statement-debt-call-flow.pdf` only. The brief lists README.md, sources/ (emails + 3 analysis versions, documents
  incl. the IVR integration document whose **section 6 = the mock's contract**, meetings), test-environment/
  (test customers .md/.json + rules), example-scenarios.md (6 calls), cloudflare-mock/. Submission: e-mail
  submission.json + exported workflow + trace to the address in BRIEF.md before 20:00 UTC.
- **The case is an INBOUND enquiry line** (statement debt in several currencies, due/cut-off dates, change cut-off date,
  e-mail the statement, hand-off to a human; identity done by the IVR; variables `customerNumber`, `now` ISO with +03:00).
  `now` with offset parses fine (local wall time).
- **Frozen builder fails on such cases (proven case-blind):** synthetic library-enquiry folder
  `<this scratchpad>/synth-inquiry/` (my own text) on main f35ccf3 `--dry`: spec check FAIL ('tool API has no
  verify_identity / create_promise / close_call'), then `ValueError: spec expression promise window min '': empty
  expression` in codegen.setup_source; END ok=False, 335 s, no agent. spec.py:389 requires those roles.
- **User D6 (17:20): generic fallback fix, CASE-BLIND** (Methodology; target tag cand-final.5 ~18:05): when the contract
  lacks the collections roles, render a generic workflow (consolidated rules + every contract operation as an api_call
  tool, ids baked from same-named call variables, goodbye + end) instead of crashing; collections renders byte-identical.
  Spec sent to Methodology 17:21 (synthetic reproducer only). **Disclosure (Methodology 17:22): before that message it
  had read BRIEF.md and the flow PDF text (17:19-17:22) at the user's pointer; it opens nothing more and builds/tests only
  on synthetic cases.** This chat verifies the tag before adoption.
- **Mock rebuilt as fixture-driven** (commit below; deployed b39d28e4): `mock/src/fixtures.js` resolves (method, path
  with {params}, fields from path+query+body) against `data/fixtures.json` (endpoints + documented answers with exact
  status; most specific match wins; endpoint default; `unmatched`); every fixture request logged to a RequestLog DO
  (`GET /__admin/log` with x-admin-token; DELETE clears). Practice-kit routes kept as fallback. `npm test` 10 pass.
  fixtures.json is EMPTY until the integration document + test customers arrive.

## UPDATE 17:05 UTC: FROZEN `freeze-final-2` = cand-final.4 e2635e9, merged into main; repo pushed

- **Build the final from `main` (builder code == `freeze-final-2`).** cand-final.4 = cand-final.3 + date-language fix
  (language.localize_dates: for a non-English call the negotiate step says FACTS dates in the call language, not 'as
  written'; English byte-identical). Verified (`verify_tag.sh`, log verify-cf4.log): 947 tests; spec-a-llm render
  byte-identical to cand-final.2; Turkish folder --dry ok=True, prompt 15,310 chars, no contract in the BANK BRIEF,
  negotiate has no 'as written' and says 'said in Turkish'. Merge 38a076d: 947 passed, ruff clean.
- **Prepared, NOT adopted (user decides):** `cand-final-dates` 385b326 (fix (a): upper-case/diacritic-less Turkish months
  in `now`; +137 bytes per facts node) -> adopt only if the final data's `now` is worded that way. `cand-final-3-work`
  0f943d4 (customer_field, xlsx, docx, unknown suffix, PDFKit, contract normalisation, ...; needs a rebase onto .4).
- **Size watch (Methodology):** 40,000 bytes per code node is OUR test guard, not a documented platform limit. Turkish
  1-product spec: account_facts 39,632 bytes; 3-product + Turkish months can pass 40 KB. The real build's platform
  dry-run/save shows whether Freya accepts it.
- Repo https://github.com/M4G1W0W/freya-build-the-builder (private): main + tag `freeze-final-2` pushed.

## UPDATE 16:57 UTC: cand-final.3 VERIFIED; user D5 = cand-final.4 (date-language fix) then freeze; D9 = private repo

- **cand-final.3 = 4cd9e92** (user go 16:50: folder-as-brief fix ONLY; Methodology): folder input -> `_prompt_brief` =
  consolidate's rules (trace STEP 'BANK BRIEF in the prompt = the consolidated rules, N chars'; < 1000 chars -> full text +
  WARN); brief-file inputs unchanged. **Verified by this chat** (`<this scratchpad>/verify_tag.sh`, log verify-cf3.log, 0
  Freya calls): diff 3 files +78; 943 passed (1 deselected: worktree venv check); spec-a-llm old-form render
  byte-identical to cand-final.2; Turkish folder --dry: prompt 23,805 -> 16,643 chars, no contract text in the BANK BRIEF,
  holidays + required Turkish sentences + enums kept.
- Untagged on `cand-final-3-work` (0f943d4, 962 tests; NOT approved): customer_field over role tools, xlsx refs/styles,
  docx content controls, unknown-suffix sniff + textutil, PDFKit fallback, contract path normalisation/role re-ask/enums,
  language first, mock host without scheme.
- **User D5 (16:57): cand-final.4 = cand-final.3 + prompt-only date-language fix**, then freeze it. Reason: the negotiate
  task_message says to say dates 'as written' in FACTS ('Friday 16 October 2026', English) while the system prompt says to
  speak dates in Turkish (confirmed in the Turkish render). Asked Methodology: non-English specs only; English renders
  byte-identical. Then this chat verifies (tests, spec-a-llm byte-identical, Turkish --dry), tags `freeze-final-2` (new
  tag; tags are never moved) and merges into main.
- Methodology note (a), NOT fixed: upper-case or diacritic-less Turkish month words in `now` (EKİM, kasim) fall back to the
  server clock. Check the final data's `now` format at 17:00 (ISO/numeric is safe).
- **User D9 (16:57): private GitHub repo shared with the organisers.** User go 16:59: created by this chat with gh
  (account M4G1W0W): **https://github.com/M4G1W0W/freya-build-the-builder** (PRIVATE), remote `origin` (ssh), `main`
  pushed 17:00 (44f4d4a). Before the push: every blob of all history (833) scanned for the values of FREYA_API_KEY,
  FREYA_BANK_TEAM_KEY, OPENAI_API_KEY, FREYA_WORKSPACE_ID, MOCK_ADMIN_TOKEN, MOCK_TEAM_KEY and key patterns: no value
  hit; pattern hits are placeholders only (`Bearer YOUR_API_KEY`, `fak_your_key`, `sk-test-SECRET-...`). Scanner:
  `<this scratchpad>/scan_history.py`. **Open: invite the organisers' GitHub handle (from the kit e-mail) as a
  collaborator.** Never force-push.

## UPDATE 16:48 UTC: cand-final.2 REVIEW + Turkish --dry + pdftotext (simulation chat)

- **Review** (workflow wf_266727cb-c3f, 30 agents, read-only, offline repro + 1 skeptic per medium+ finding): **no
  blocker**; 24 confirmed (~8 distinct issues), 1 refuted, 12 unverified lows. Summary:
  `<this scratchpad>/review-summary.txt`; repros `<this scratchpad>/review-tmp/`. Sent to Methodology (prepare fixes on a
  branch, do NOT tag; the user decides cand-final.3). Ranked:
  1. HIGH: PDFs without pdftotext (dropped or garbled Turkish). **FIXED in the environment (user D4 16:46): `brew install
     poppler` -> /opt/homebrew/bin/pdftotext 26.09.0**; the builder's pdf_text now reads Chrome/Quartz Turkish PDFs exactly.
     The organisers' re-run machine may lack it (trace WARNs).
  2. MEDIUM (top builder issue for the final): folder input -> when consolidate says kind=clean, `_prompt_brief` = EVERY
     file (test customers' identity answers + balances, example conversations, contract, Q&A) under "BANK BRIEF (the rules
     you must follow)" (cli.py:144-147, pipeline.py:196/208, render.py:240). Confirmed live twice (kind=clean, prompts 23.5k
     and 23.8k chars). Fix: folder/multi-doc input -> `_prompt_brief` = consolidated_rules.
  3. MEDIUM: verbatim tts lines skip the language step (render.py:611/702/712-723). **Measured: not hit on a Turkish brief**
     (below).
  4. MEDIUM: customer_field intersects over ALL tools (spec.py:670-683); xlsx empty/merged cells shift columns, date
     serials, percentages; unknown extensions skipped (flow drawing .svg/.drawio/.mmd/.html/.rtf).
  5. Contract shape (GET/path params, double /v1, full-URL paths, no response enums, missing role kills the build late,
     OpenAPI JSON with non-practice names -> KeyError): absorb by writing the mock to the trace's `tool` lines and choosing
     mock_url; a missing role is a build failure to watch for.
- **Turkish --dry (user D3 16:46: --dry only, no synthetic simulation; 0 Freya calls):** folder `<this scratchpad>/rehearse-tr/`
  (BRIEF.md = own Turkish translation of kit brief A, Turkish README, .docx contract). END ok=True, 144 s, 4 model calls,
  call language Turkish. Every verbatim spoken line is Turkish (opening, disclosure intro/product/first ask, promise line,
  identity asks, failed/decline lines, goodbye, product labels, months). account_source offline: disclosure_text fully
  Turkish; worded now '14 Ekim 2026 Çarşamba 11:00' parses like ISO. Minor: amounts '1850.50' (Turkish 1.850,50);
  account_facts dates in English for the model (prompt says to speak dates in Turkish). Files: rehearse-tr.spec.json,
  rehearse-tr.dry.workflow.json, rehearse-tr.dry.trace.log (this scratchpad). The first simulation of the REAL final
  build is the end-to-end Turkish test.

## UPDATE 16:38 UTC: cand-final.2 REHEARSAL against our mock PASSED (simulation chat)

- **Build** (live, non-dry, Python 3.12.13 standalone, worktree `<this scratchpad>/wt-cf2` at 3abfd22):
  `build.py <scratch>/rehearse-folder $MOCK_URL --slot rehearse-cf2`; folder = BRIEF.md (kit brief A) + README.md +
  docs/service-contract.docx (text copy of kit openapi; the model-read contract path). Trace
  `<this scratchpad>/rehearse-cf2.trace.log`: 7 tools, every URL `https://teampistalogic.atlasreyiz.workers.dev/v1/<tool>`;
  4 model calls (contract, consolidate, extract, language=English); spec check PASS; validation PASS; platform dry-run
  PASS; chat smoke PASS; END ok=True, 130 s. workflow 704f9b40 / agent 52cef789 (slot `rehearse-cf2`).
- **Simulation (user D2 16:36: one call)**: REH-CF2-PUB01-mock, PUB-01 talkative x1, bank = our mock
  (`FREYA_BANK_HOST`=mock origin, team key = MOCK_TEAM_KEY), suite_once.py (maxRetries 0, no reruns): **PASS**
  (verify > verify > get_account > promise > close_call; judge pass + kit scorer on our mock's ledger), 42 s, turns
  ~2 s. Ledger **cum 525**. Files `runs/dev/r4/REH-CF2-PUB01-mock.*`.
- **Chat endpoint quirk (not a regression)**: `/chat/message` model tools take `customer_id` from the workflow's
  `test_variables` (the brief's example value, e.g. kit A `c_4f2a...`), not from the chat's `customerVariables`;
  api_request nodes (close_call) get the right value. Same on the frozen-era exp-eng4-a (Brief A) agent; simulations
  resolve correctly (session ids in call records). So chat cannot test identity against a mock; use a simulation.
- **What Freya sends to the mock** (headers recorded by the mock since 7142671): `user-agent: Python/3.12
  aiohttp/3.14.3`, `content-type: application/json`, Sentry `baggage` + `sentry-trace`; **no call id header**. The
  `sentry-trace` value was identical for all 5 tool calls of the simulated call and different from the chat call:
  apparently per call (1 call of evidence, undocumented).
- **Final-mock risk to decide after reading the contract:** the hidden test customers reach our mock with fixed
  customer ids, 3 reps each (possibly concurrent): per-customer state (verified flags, wrong-answer lock, one promise
  per product -> 409) can leak between reps/calls. `idleResetSeconds` 600 only covers sequential calls >10 min apart.
  Options: key state on customer_id + sentry trace id (undocumented), reset on a new trace id, or keep the state
  lenient (contract permitting).
- Mock commits: 7142671 (PUB-01..13 practice customers, header capture), 846a1f4 (`mock/tools/xlsx_rows.py`).

## SIMULATION CHAT HANDOFF (16:20 UTC; READ FIRST after a context clear; then the 16:08 block below)

**State: nothing running.** Plan driver stopped (`PLANSTOP` in this session's scratchpad), queue paused (`sim/STOP`), no
simulation, no `wrangler dev`. Ledger `runs/dev/r4/calls.tsv` cum **524** / cap 789; credits ~374.5 USD.

**Decided (user):** D6 = eng.9 (15:51). `freeze-final` = b9756fe (cand-eng.9 + main), merged into `main` = 8e251fe
(16:06; builder code identical). eng.9g goodbye fix failed its rule (HU-PRE regression), not adopted; offers fix (o2)
and eng.4g untested. Results: `docs/reviews/2026-10-11-final-comparison-results.md`; plan + amendments:
`docs/plans/2026-10-11-final-comparison-plan.md`.

**Final format changed (16:00, see the 16:08 block):** one Turkish case folder, `python3 builder/build.py {case_folder}
{mock_url}`, our own Cloudflare mock, `submission.json`. **User split (16:13):**
1. **Methodology** (engine chat): generic builder changes BEFORE 17:00 on top of b9756fe as a NEW tag (asked by ~16:50):
   folder input (.md/.txt, .docx/.xlsx stdlib, .pdf best-effort, warn never crash), tools from the folder's service
   contract with base URL = mock_url, agent language from the brief (no hard-coded English lines/dates), old CLI kept.
   **16:20 progress (Methodology):** branch `cand-final-2-work` = 2358594 (off main 81714cb; 941 passed = 931 + 10 new);
   tag `cand-final.2` only if two `--dry` builds (kit Brief A old form; a synthetic folder with a .docx-only contract)
   end ok=True, by ~16:45. It: reads the folder (BRIEF.md/README.md first; .md/.txt/.json/.yaml, .docx/.xlsx stdlib,
   .pdf via pdftotext or a stdlib scan; others WARN); tools from an OpenAPI JSON in the folder, else ONE model call
   reads the contract's operations (mapped to the 7 roles, contract names/paths/fields kept): **every tool URL =
   mock_url + the contract's path, so the mock must serve the contract's paths and methods exactly** (trace prints one
   `tool <name> <METHOD> <url> request=[fields]` line per tool); ONE model call detects the call language (translated
   goodbye + month names; English briefs render as before except facts.py); facts.py reads a worded `now` in that
   language. Not done: the 'outbound' wording; per-line translation of other verbatim lines (prompt instruction only).
   Tags are never moved: a new freeze needs the user's call (new tag name or moving
   `freeze-final`), then re-merge into `main`.
2. **This chat**: mock bank template `mock/` (0a8d2ad, 6fc3e51; NOT builder code): `src/bank.js` (pure logic, adapt
   `HANDLERS` after 17:00), `src/worker.js` (Worker + Durable Object per customer; admin `GET /v1/ledger/<id>`,
   `POST /v1/reset/<id>` with `x-admin-token`; **practice** `POST /v1/practice/sessions` + `GET /v1/practice/ledger/<id>`
   with `x-team-key`, kit-scorer ledger format so `kit/tools/run_cases.py` runs against it with
   `FREYA_BANK_HOST=<mock origin>` + `FREYA_BANK_TEAM_KEY=<TEAM_KEY>`), `data/customers.json` (EXAMPLE public practice
   customers), `test/bank.test.mjs` (`npm test`, 6 pass), `README.md` (post-17:00 steps). Tested on `wrangler dev
   --local` (local secrets in gitignored `mock/.dev.vars`).
3. **User**: Cloudflare. `npx --yes wrangler@4.149.0 login` DONE (16:19). **Deploy blocked: the account has no
   workers.dev subdomain** ("mock" taken). User registers one at
   https://dash.cloudflare.com/708643963b93e91d297ce3b21aafd8d7/workers/onboarding.

**Next for this chat (in order):**
1. After the subdomain exists: generate two random secrets into `.env` (`MOCK_ADMIN_TOKEN`, `MOCK_TEAM_KEY`; never
   print them), `cd mock && CI=1 npx --yes wrangler@4.149.0 deploy`, then `wrangler secret put ADMIN_TOKEN` / `TEAM_KEY`
   (value via stdin from .env), smoke-test `GET /` and one practice session; write `MOCK_URL=https://freya-mock-bank.<sub>.workers.dev/v1` to `.env`.
2. When Methodology's tag lands: verify it (tests, diff limited to the input layer/language), rehearse the new command on
   a practice folder (kit brief-a.md + a contract) against the deployed mock with a 3.10+ Python
   (`~/.local/share/uv/python/cpython-3.12*/bin/python3`; system python3 is 3.9.6), and bring the freeze decision to the user.
3. From 17:00 (zip via the Submit tab / e-mail, user downloads): adapt `mock/src/bank.js` + `data/customers.json` from
   the service contract and test customers, `npm test`, redeploy; build ONE run with the new command, keep its trace;
   test with run_cases against our mock (cases from the 6 example conversations); `submission.json` before 20:00 UTC.
   Open user decisions: D8 (organisers' model key), **D9 remote/push (repo URL needed)**, and whether the filled
   `mock/` (final-case content, not builder) is committed in the submitted repo (Dashboard Creator flagged it).

**Peers:** Methodology Developer (engine; generic builder tag pending; its checker `scripts/transcript_check.py`),
Dashboard Creator (gap analysis `docs/reviews/2026-10-11-final-format-gap.md`, cd40069), Service Check (idle).
**Scratchpad (may vanish):** `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/6099f72d-6345-4df7-a171-465da9b25d18/scratchpad/`
(plan_run.sh, run_one.sh, suite_once.py, probe_strict.sh, worktrees wt-eng4/9/4g/9g/4o2/9o2, wt-final-eng4/9/9g);
copies of the harness in `runs/dev/r4/harness/`. Final-comparison call records: `runs/dev/r4/final.calls/`.

## UPDATE 16:08 UTC: THE FINAL FORMAT CHANGED (official page). READ THIS BEFORE ANY 17:00 STEP.

The user flagged the page's Submit tab (16:00 UTC). Re-read of all 7 tabs:
`docs/reference/hackathon_page_live_2026-10-11.md`, verbatim, each tab hash-checked against the live page. Digest:
`docs/hackathon_requirements.md` → "FINAL FORMAT, 11 Oct" (F1-F10). Dashboard Rules & Cases now carries it (39 items,
7 superseded conflicts, deadlines renamed; the final case is the first case set, `docs/reference/final_case_2026-10-11.json`;
the user's 14:48 "new case" report is resolved).

- **ONE case, in Turkish**: Freya Bank's credit card statement-debt line. Not two hidden briefs. One phone agent.
- **Input = a zip FOLDER** of .md/.docx/.pdf/.xlsx: BRIEF.md (read first), README.md, analysis, flow drawing,
  announcements, service contract, test customers, Q&A, 6 example conversations.
- **Command: `python3 builder/build.py {case_folder} {mock_url}`.** The frozen builder takes `{brief_path}
  {tool_api_path}` (kit openapi.json): it does not match this command as it stands.
- **We host the bank**: write a mock on **Cloudflare Workers** from the service contract + test customers, deploy it
  BEFORE the build, keep it up until results. In the final the agent may call only our mock.
- **Submit** one export + its trace, and e-mail `submission.json` (team, members, repo, commit, run_command, workflow,
  trace, mock_url) before 20:00 UTC. Criteria, weights and tie-breaks are not published; the trace is not scored.
- After 17:00 only bug fixes. Fixing a crash on an unexpected file type is allowed; adding the bank's announcements or
  field names to code or prompts is not.
- **Gap analysis DONE (16:12 UTC, read-only, freeze-final b9756fe):** `docs/reviews/2026-10-11-final-format-gap.md`
  (plan + critic). File:line evidence for 84 findings is in the `.json` next to it. Blockers [C]:
  1. `build.py {case_folder} {mock_url}` exits 1 before any model call: the folder hits `read_bytes`, cli.py:56.
  2. .docx/.xlsx/.pdf files are read as binary garbage (cli.py:54-62), and the builder is stdlib-only.
  3. Tools come only from an OpenAPI JSON file (toolapi.py:107-108), and the URL from its `servers[0]`
     (toolapi.py:85-86). spec.py:389 requires the practice tool names, so a contract with other names builds no
     agent.
  4. The agent is hard-wired to English: "Speak English.", render.py:225; English goodbye and verbatim lines,
     render.py:230/492/555. The prompts assume an outbound call (render.py:225, pipeline.py:48).
  5. There is no git remote.

  Mock: template committed by another session in `mock/` (0a8d2ad). Wrangler is not installed and there are no
  Cloudflare credentials. Filling `mock/` from the zip and committing it would put final-case content in the reviewed
  commit: a team decision. Estimate for the minimum builder changes: about 65 min plus a contract-to-tools mapper
  (60-90 min); 48 min were left at 16:12. **Open user decisions:**
  - whether to change the builder's input layer before 17:00 (generic folder + mock_url support);
  - the Cloudflare account and credentials;
  - D8/D9 (key, remote/push), now needed for `submission.json` `repo`.

## UPDATE 15:59 UTC: FROZEN. `freeze-final` = b9756fe (cand-eng.9 + main). Nothing running.

- eng.9g failed its rule (HU-PRE regression: end_call after close_call + double goodbye); not adopted. Driver stopped
  (PLANSTOP), queue paused (`sim/STOP`), no simulation running. Ledger cum 524 / 789; credits ~374.5 USD.
- Freeze checks: ruff clean, 931 passed, fresh-clone `--dry` OK with Python 3.12 (system python3 is 3.9.6: use a 3.10+
  interpreter for the hidden builds, e.g. `~/.local/share/uv/python/cpython-3.12*/bin/python3` or `uv run python`).
- Next (user): hidden builds from 17:00 UTC per `docs/RUNBOOK.md`, from a checkout of `freeze-final`. Open user
  decisions: D8/D9 (organiser key, remote/push). **16:06 UTC (user): `freeze-final` merged into `main` (8e251fe): main's
  builder code and tests == freeze-final (cand-eng.9); ruff clean, 931 passed.** Hidden builds may use main or the tag.

## UPDATE 15:53 UTC: D6 = eng.9 (user 15:51); eng.9g goodbye evaluation running; freeze commits being prepared

- Results + rule application: `docs/reviews/2026-10-11-final-comparison-results.md` (rounds 1-2 matched; round 3 lost to a
  platform outage 15:16-~15:46). Strict probe PROBE-S1 passed 15:49 (run verdict, no errors) -> driver resumed.
- Queue = the 9 eng.9g items only (`plan-before-d6-*.txt` keeps the dropped eng.4g/offers items). Adopt eng.9g only if
  its pre-registered rule holds (plan addendum 15:01/15:04/15:05) by 16:40 UTC; otherwise freeze eng.9.
- Freeze commits (no Freya): branches `final-eng9` (b103e21 + main) and `final-eng9g` (b40a576 + main), worktrees
  `<this scratchpad>/wt-final-eng9`, `wt-final-eng9g`; verify logs `<this scratchpad>/final-eng9*-verify.log`.
  `freeze-final` is tagged on one of them at ~16:40-16:50, then the RUNBOOK hidden builds from 17:00.

## UPDATE 14:40 UTC: FINAL COMPARISON RUNNING (user go 14:35): eng.4 vs challenger, fresh raw-A + A+B builds

- Pre-registered plan: `docs/plans/2026-10-11-final-comparison-plan.md` (arms, slots exp-eng4-fr/fab and exp-ch-fr/fab,
  case sets, order, cut lines, decision rule). Driver `plan_run.sh` (this session's scratchpad; copies in
  `runs/dev/r4/harness/`), plan file `plan.txt`, done log `plan-done.txt`, stop file `PLANSTOP`. Path cases
  `runs/cases/e1-a.json`, `e1-ab.json` (from 898223d). Methodology messaged 14:35 (challenger tag by 15:00 or eng.8;
  24-build `--dry` battery; main->challenger merge trial by 16:30). Queue (`sim/queue.txt`) still paused; not used.
- Challenger = **cand-eng.9 b103e21** (Methodology 14:37: eng.8 + closing guard, 875 tests). eng.4 fresh builds
  exp-eng4-fr / exp-eng4-fab (14:34-14:38, export MATCH); eng.9 fresh builds exp-ch-fr / exp-ch-fab from
  `<this scratchpad>/wt-eng9` (detached b103e21). **`final-eng4` = 924b970** (branch, worktree
  `<this scratchpad>/wt-final-eng4`): main merged into cfa4d9d, no builder-code diff, ruff clean, 891 passed; untagged.

## UPDATE 14:20 UTC: housekeeping (user ~14:05): E4-A-styledA COMPLETED and dequeued; challenger arm eng.6 -> eng.8 (eng.4 stays the comparison candidate); cap 789

- **Authorizes housekeeping only: no builds, deployments, simulations, promotion or freeze. Queue PAUSED (`sim/STOP`
  set).**
- E4-A-styledA marked COMPLETED (`sim/queue-completed.tsv`) and removed from `sim/queue.txt` (pre-removal copy
  `sim/queue-before-e4a-removal-1409.txt`). Queue now: E4-AB-all, E4-AB-xb, E4-VE (60 calls). All three reps,
  artifacts and the raw strict 4/10 are kept (`runs/dev/r4/E4-A-styledA*`; committed copy of the analysis:
  `docs/reviews/2026-10-11-e4a-styledA-analysis.md`). Note: the ledger books E4-A-styledA 40 for 30 real calls (attempt 1's
  POST-504 booking of 10 was never corrected); kept, cumulative usage is not reset.
- **Dossier §11** (`docs/reviews/2026-10-11-final-selection-evidence.md`, verified by a 3-lens read-only check):
  challenger arm now **eng.8 (4267bb0)**; eng.4 stays the comparison candidate. eng.8's bar (Primary, 201 calls):
  T1 66 + T3 96 + E1 path cases 30 + **D8** = the engine-required eng.8 `--spec fix1_audit_spec_ab4.json` defect path
  (9; 3 runnable today); T2 raw-A 60 strongly preferred; **E2 (eng.6 control only, explicit approval): 39**; T4
  dropped. D10/D11, §10.1, §10.3 (all superseded) point to §11. Prerequisite (prediction, not run): the Brief-A-ledger
  PUB-05 cases would fail the ledger on a correct A+B ab4 agent (Brief B rule 8 hardship note); only
  `styled-ab-a.json` PUB-05 fits today. **Run anything only through `run_one.sh` + `suite_once.py`**: `qrun4.sh`
  still uses `--rerun-if-slow 1`, platform retries and a nominal-only cap check. Harness copies (scratch may vanish): `runs/dev/r4/harness/`
  (`run_one.sh`, `suite_once.py`, `dump_calls.py`, `wait_bank_then_run.sh`; `suite_once.reps12.py` = the version reps
  1-2 ran with, before the corrected gate).
- **Cap 705 -> 789** in `qrun4.sh` and `run_one.sh`, applied under the user's 13:45 bounded-raise authorization:
  cum 343 (kept) + 360 planned + 36 retry + 50 hidden-brief reserve (Decision log 14:15 UTC; dossier §11.4). The user
  may lower it. Credits 391.96 USD. Ledger unchanged (cum 343).

## UPDATE 13:52 UTC: E4-A-styledA complete (3 reps): raw strict 3/3 = 4/10 (reps 4, 10, 10); cap raised to 705

- **User D3 (13:45):** run rep 3 only, same deployment/cases, maxRetries 0, no reruns, corrected gate (every platform
  error event; only PUB-10's injected create_promise failure excused). Internal cap may be raised to a computed,
  bounded value (done: **705**, Decision log 13:50 UTC); no other suite, no promotion, no automatic start.
- **Rep 3 (sim 51c4a5e0, 13:45): 10/10**, median 7 s, worst 25 s, no hang-ups, no blocking platform error. Ledger
  **cum 343 / 705**. Credits **391.96 USD**.
- **Three-rep raw strict 3/3: 4/10** (PUB-02/05/07/09 3/3; PUB-01/03/04/06/08/10 2/3, each failed only in rep 1).
  Failure classification is separate (workflows wf_cae6672e-5d3 = rep-1 failures + reps 1-2 audit, wf_5a767735-790 =
  rep-3 audit; both read-only).
- **Classification (analysis `runs/dev/r4/analysis-e4a.md`, skeptic-checked):** rep-1 PUB-01/03/04/08/10 = platform
  (opening who_answered extraction request hung; 60.3 s silence; same node as G1; agent contribution none);
  PUB-06 = mixed (platform extraction_error, then our opening design: latest-message extraction, no tools, model
  improvised, closed not_verified/declined untruthfully). Control M3 G1 used no platform retries (30/30 runs attempt 0).
- **Latent (judge-unchecked) findings, shared with G1 unless noted:** transfer endings skip rule 47 goodbye (PUB-09
  6/6 calls); read-back without product when the customer names the date (PUB-10, rule 34); eng.4 r1 PUB-07 false
  "Monday 27 October 2026 is a business day" (G1 comparison undetermined); kit slowest-turn metric undercounts.
  Not fixed (no candidate changes authorized).
- Nothing running after the audits; queue.txt/STOP untouched (E4-A-styledA line still first in queue.txt: it was run
  outside the queue; remove it only on the user's word).

## UPDATE 13:42 UTC: E4-A-styledA STOPPED after rep 2 (platform error in rep 1); awaiting the user on rep 3

- User D2 (13:25): wait for a stable bank, then start. Watcher: 5 OK checks 13:25-13:29; suite started 13:29:39.
- **Rep 1 (sim 56096a1e): 4/10.** 5 silent hang-ups (PUB-01/03/04/08/10: after the customer's first answer in the
  `opening` node the platform logged NO event for ~60 s, then customer-ended-call) + PUB-06 `extraction_error`
  (who_answered) -> model improvised DOB questions from the opening node, said 'technical issue' twice, closed
  not_verified/declined. The `opening` node is byte-identical to G1's (export diff: only setup, identity,
  account_facts, negotiate, finalize differ). **Rep 2 (sim 5407adea): 10/10**, run verdicts, slow (median 28 s);
  PUB-10's function_call_error is the case's designed 'service unavailable'.
- **My stop gate missed rep 1's platform error** (it scanned only tool-completion events, not `extraction_error`),
  so rep 2 ran; I stopped the client right after rep 2 was recorded (13:39:07), before rep 3's POST. Only 2
  simulations exist. Ledger: run_one booked 30, corrected -10 -> **cum 333**. Credits 396.26 -> 393.20.
- Raw strict 3/3 can be at most 4/10 for this suite (6 cases failed rep 1). Analysis workflow wf_cae6672e-5d3
  (read-only) classifies rep-1 failures with skeptics and audits the 14 passing calls.
- Control M3 G1 on the same set: 10/10, medians 4/4/8 s, 64-135 s per rep (much faster platform).

## UPDATE 13:10 UTC: smoke 3 judged PASS but SLOW; E4-A-styledA NOT started (latency gate)

- **User go (~13:00 UTC, organisers confirmed Freya is back):** one bounded eng.4 smoke with no automatic retries; if
  it passes with normal latency, run E4-A-styledA (10 x 3) and stop before the next queue item. Strict raw 3/3, every
  attempt preserved, within the 500 cap. Smoke + first suite only; D1-D11 stay deferred; no candidate change/freeze.
- **SMOKE3** (`runs/dev/r4/SMOKE3-e4a.{log,json}`, call record `runs/dev/r4/SMOKE3-e4a.calls/`): simulation
  f1f21b08 (maxAttempts 1 confirmed), call 299f78ae, exp-eng4-a, PUB-01 talkative. **Judged PASS (run level), ledger
  right** (verify > verify > get_account > promise > close_call). **Slowest agent turn 50 s** (kit: median > 10 s =
  slow run; the organisers' runner discards such runs): the model took 49.3 s (DOB -> verify_identity), 25.6 s (phone
  -> verify_identity) and 26.1 s (confirm -> create_promise) to emit tool calls; bank tools 0.05-0.6 s, code nodes
  0.2-0.4 s. Same pattern as smoke 2 (54 s, 12:37); the same workflow had 0-1.5 s turns at 12:10. **Gate not met:
  E4-A-styledA not started.** Ledger cum **313**. Credits 396.69 before / 396.26 after (they had risen from 391.06 at
  12:29: apparently an outage refund).
- **User 13:15 UTC: slow latency alone is acceptable; run E4-A-styledA x3, no reruns because of latency; stop for
  missing verdicts, platform errors, budget or another concrete blocker.** Attempt 2 (13:20:20) crashed BEFORE its
  simulation: mock-bank `POST /v1/practice/sessions` returned a non-JSON error (kit `score.http` JSONDecodeError). No
  simulation created (GET confirms newest f1f21b08); ledger corrected -10 (cum 313); files
  `runs/dev/r4/E4-A-styledA.attempt2-bank-nonjson.*`. Bank probes: 13:20:44 POST 200; 13:21:43 ledger GET **500
  `error code: 1101`** (Cloudflare worker exception); 13:21:51 and 13:22:05 200 => the bank is FLAPPING. Stopped per the
  user rule; asked the user. `suite_once.py` now retries the kit's bank helper on non-JSON/network errors (~2 min).
- Smoke 3 evidence check (read-only workflow wf_d1cd9ea9-206): latency = platform model latency (same workflow and
  persona, identical turns <= 1 s at 12:10, 25-54 s at 12:37/13:05; call tags llm TimeoutErrors, llm_ttfb_p95 21.5 s);
  the kit's slowest-turn metric undercounts (real waits 55.7 s / 47.6 s from messageId delivery stamps, inferred).
  Independent policy audit: policy followed, honest, ledger right; risk: the confirming yes came 4 turns after the
  read-back (after cut-off fragments) with no repeated read-back.
- Ready for the suite (scratch, this session): `run_one.sh` + `suite_once.py` in
  `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/6099f72d-6345-4df7-a171-465da9b25d18/scratchpad/`
  (one item, no queue pop, STOP untouched, POST maxRetries 0, `--rerun-if-slow 1`, every simulation recorded in
  `runs/dev/r4/<name>.attempts.jsonl`; worst case 120 calls -> 433 <= 500).

## SIMULATION CHAT HANDOFF (11 Oct 12:57 UTC; READ THIS FIRST after a context clear; supersedes the sections below)

**Roles.** This chat (Simulation Developer) owns ALL deployments and simulations. Methodology Developer (engine chat)
fixes the builder on its own branches/tags (log `docs/plans/2026-10-11-engine-fixes-log.md`, READ FIRST at its top;
its handoff `docs/plans/2026-10-11-engine-fixes-handoff.md`). **Service Check** (peer session, read-only GETs) watched
platform health and our simulations; **it STOPPED its checks at 12:56 UTC at the user's request: the organisers
confirmed services are up** (last check: API 200 in 0.31 s, bank up, nothing running). Agent-turn latency was not
re-measured after smoke 2 (12:40: 54 s turns). If Service Check is asked to watch again, coordinate via SendMessage.

**State now: NOTHING running. Queue PAUSED by the user (12:45: no simulations, no latency probes until the user says
so).** `sim/STOP` is set. The last simulations (6d0c9464 M5r2 restart, 94c9e350 smoke 1, 188b9156 smoke 2) are all
completed. Ledger `runs/dev/r4/calls.tsv` cum **312** (runner CAP 500); credits **391.06 USD** (12:29).

**Binding user rules (all still in force):**
1. No automatic freeze, no automatic selection of an unmeasured candidate, no switching candidates, no deploying
   eng.6/.7 (or .8), no adopting a new tag without the user's approval. Bring evidence + fallback options first.
2. eng.4 stays the comparison candidate. *(14:20: E4-A-styledA COMPLETED and removed from the queue; challenger arm
   eng.8; see the 14:20 update.)* The existing E4 queue is preserved (sim/queue.txt: E4-A-styledA,
   E4-AB-all, E4-AB-xb, E4-VE) and runs only when the user resumes it.
3. Resume conditions (12:09) once the user allows: one bounded smoke with a complete judged result; no stuck
   simulation still making calls; extra usage reconciled. A judged agent failure is diagnostic (inspect it first).
   Missing results or continuing platform errors keep the queue paused.
4. The 15:30 UTC freeze is an internal target; the user makes the final selection.

**Deliverable waiting for the user: `docs/reviews/2026-10-11-final-selection-evidence.md`** (commit 597c2e8): every
candidate's measured/unmeasured status, what transfers, risks, readiness, fallbacks by platform scenario (S1/S2/S3),
the eng.6/.7/.8 matched-comparison proposal (§10: T1 A 66 calls, T2 raw-A 60, T3 A+B 96, T4 optional; only T1 fits
under the cap after the E4 queue), and **decisions D1-D11 (§8) that are the user's**; default for all: nothing runs,
nothing is selected or tagged. Key facts: G1 is the only fully measured build (A saved 10/10, fresh raw-A 8/10,
fresh A+B 7/13, extra-B 1/3); `cand-retry.4` = G1 + platform retries with renders byte-identical to the measured G1
agent; final.1/eng.4/eng.5/eng.6-8 have NO valid measured rep; Fix 1 (eng.6/.7) has a CONFIRMED PUB-05 closing-row
defect in 6/16 fresh builds; main's builder code is F3 (any candidate must be merged with main's docs first;
merge-tree clean; a trial main->eng.4 merge passed 872 tests).

**Deployed eng.4 slots (export MATCH, do not rebuild):** exp-eng4-a wf 66db0b41 / agent f166447e (spec-a-llm),
exp-eng4-ab wf 0a819c5b / agent 0988e6f1 (spec-ab-llm-c45758f), exp-eng4-ve wf 56124310 / agent 7818e5e2 (fresh
variant-e). Worktree `<old scratchpad>/wt-eng4` (detached cfa4d9d). 35 of 200 workflow slots (+ up to 2 strays).

**eng.4 live evidence so far:** smoke 1 (94c9e350, PUB-01): call 6af560aa judged pass on the call record, ledger
right, 14-37 s turns, DOB asked 3x; platform retry call af507b83 judged pass with normal latency; the run itself ended
error ('No call created' on attempt 4). Smoke 2 (188b9156, maxRetries 0): run-level judged FAIL, customer hung up after
a 54 s model turn; logic correct (latency).

**Tooling changes today (main):** `scripts/run_cases_retry.py` verdict fallback (4631971, aa7726a, 7bfcf41): a run with
no judge verdict ('analyzing', or error/inconclusive 'analysis never arrived') takes `successCriteriaResult` from its
call record (one unretried read), prints `VERDICT FROM CALL RECORD`, rows carry `verdict_source` and `attempts`;
801 tests. Platform facts in `docs/freya_api_notes.md` §simulations: pause does not stop platform retries (maxAttempts
4); `maxRetries: 0` = one attempt; verdicts live on the call record (50/50 agree with runs); completed simulations get
re-judged later (outcomes provisional).

**Paths.** `<old scratchpad>` = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad`
(sim/qrun4.sh, queue.txt, queue-parked-1135.txt, slots.tsv, qrun.out, STOP; worktrees wt-final, wt-eng4). Bounded
smoke wrapper (scratch, may vanish): `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/54d12450-d446-4d3a-862a-6541a5ece9bd/scratchpad/smoke_once.py`
(= run_cases_retry wiring without the rep repeat, POST maxRetries 0). Smoke cases: `runs/dev/r4/smoke-pub01.json`.
*(14:20: superseded: run queue items one at a time via this session's `run_one.sh` + `suite_once.py`, see the 14:20
update; `qrun4.sh` reruns slow reps and uses platform retries.)* Start the queue (only on the user's go): `rm <old>/sim/STOP; bash <old>/sim/qrun4.sh >> <old>/sim/qrun.out 2>&1`
in the background + a monitor on qrun.out.

**Next (all need the user):** answer D1-D11 in the dossier; most useful now: D4 (prepare untagged merged commits
main->eng.4 and/or main->retry.4, about 10 min each, no deployment), D6 (final selection + freeze-final, before
17:00 UTC).

## UPDATE 11:44 UTC: QUEUE PAUSED (platform 500/504), nothing running, no orphan simulation

**USER RULE (11:50 UTC): no automatic freeze and no automatic selection of an unmeasured candidate. The 15:30 UTC
(18:30 Istanbul) freeze is an internal target; submission closes 20:00 UTC (23:00 Istanbul). Bring the evidence
and fallback options to the user before the final selection.**

**USER (12:00 UTC): cand-eng.6/.7 exist (Fix 1; engine log READ FIRST).** Treat Fix 1 as a BROAD fresh-build behaviour
change (rendered negotiate stage_rules ~4.5x larger), not a paid-sentence fix; saved-spec render equivalence does NOT
establish fresh-build equivalence. The proposed comparison must include full matched A/B regression coverage and
PUB-06 'rest stays overdue' speech. **eng.4 stays the comparison candidate; no new tag is adopted automatically; the
paused queue is preserved; resolve smoke simulation 94c9e350's status before starting any other simulation.** Do not
restart the dossier workflow (wf_7488b64c-9bb); add eng.6/.7 to the evidence review as an addendum when it finishes.

- **Paused on the user's instruction (relayed Service Check note, 11:38):** widespread 500/504. `sim/STOP` is SET
  (11:38:32); the runner exited 11:39:22. No builds or retries are running. The 3 eng.4 slots below stay deployed:
  **do not rebuild them.**
- E4-A-styledA attempt 1: `POST /api/v2/simulations` -> 504, client exited 1, no rep. Ledger counted 10 calls
  conservatively (cum **267**). Files kept as `runs/dev/r4/E4-A-styledA.attempt1-post504.{log,meta.json}`.
  **Service Check (peer session) confirmed at 11:40:34: no simulation created after 11:30 UTC** (no orphan). It polls
  `GET /api/v2/simulations` every 3 min read-only (up to ~2 h), re-checks for late-created simulations, and reports
  recovery after 3 OK answers in a row. This chat does NOT poll in parallel.
- **11:51-11:57 UTC:** Service Check reported GET recovery (3 OK, 11:45-11:51), then failures again at 11:56 (502).
  The bounded smoke (exactly 1 simulation, no auto-repeat: scratch wrapper `smoke_once.py`, log
  `runs/dev/r4/SMOKE-e4a.log`) CREATED simulation **94c9e350-420c-4823-b147-d2856643f5b2** (~11:54, agent f166447e,
  PUB-01); its result GETs 504 since 11:55. If the client exits without a result, this simulation is the one to
  check/pause. Not yet in calls.tsv (add 1 call when it ends). Queue still STOPPED.
- **12:07-12:08 UTC:** API recovered at 12:07:31 (Service Check). **6d0c9464 (M5r2, paused 11:22) had restarted itself
  during the outage** (iteration ab86141f running, new calls 12:00:43/12:03:35/12:06:20, unwatched). **Re-paused 12:08:11**
  (PUT status=paused; API confirmed paused 12:08:16). Its extra calls are NOT in calls.tsv (count unknown; check the
  iteration later). Service Check watches it read-only for another restart. Smoke 94c9e350: progressing late (run
  started 12:01:07), ran alongside 6d0c9464, so its timing/result may be affected.
- **USER (12:09 UTC) resume conditions for the EXISTING eng.4 queue:** (1) smoke 94c9e350 has a complete judge verdict;
  (2) M5r2 6d0c9464 confirmed paused with no continuing new calls; (3) extra usage reconciled against the budget. A
  judged agent failure is diagnostic: inspect it before broader runs. Missing results / platform errors keep the queue
  paused. No candidate switch, no eng.6/7 deploy, no select/freeze without the user.
- **Reconciliation (12:10):** 6d0c9464 status paused (API 12:09); 13 runs: 2 started 10:45 (before the 11:22 pause),
  11 started/restarted 11:38-12:06:20, none after 12:08:11; 2 still 'running' then (12:00:43, 12:06:20). Iteration dump
  `runs/dev/r4/6d0c9464-iteration-1210.json`. Credits 401.84 (11:30) -> 397.74 (12:10) = 4.10 USD ~ 16-19 calls at
  0.22-0.26 USD/call (M3/M4) incl. the smoke: booked **18 calls** to `6d0c9464-restart-reconcile` in calls.tsv
  (cum **285**; E4-A's 10 counted calls had no simulation, kept conservatively). Re-read credits before resuming.
- **12:14 UTC: conditions NOT met.** (a) 6d0c9464 started a retry at 12:09:28 despite `paused` (Service Check alert).
  Runs have attempts/maxAttempts=4: 10 of 13 runs exhausted or done; 3 runs at attempt 3 (12:00:04 error, 12:00:43
  analyzing, 12:09:28 error) => at most 3 more calls (~0.75 USD). Not using untested PUT completed/maxRetries or
  DELETE (destroys data); waiting for the retries to exhaust. (b) Smoke 94c9e350: its call 6af560aa ran (started
  12:01:07) but is stuck in 'analyzing' (no judge verdict) for 10+ min. Queue stays PAUSED.
- **12:15 UTC smoke result (`runs/dev/r4/SMOKE-e4a.{log,json,call.json}`):** client exit 0 after 1256 s; it auto-paused
  94c9e350 (UNSTUCK: call ended 632 s earlier, iteration never completed). run_cases: FAIL PUB-01 'conversation: no
  verdict' only (bank checks passed); tools verify x2, get_account, create_promise, close_call; assistant ended the
  call. **But the call record HAS the judge verdict**: `successCriteriaResult.success=True` ('All criteria were
  successfully met'); the simulation run stays 'analyzing' (attempt 2/4; attempt 1 failed in the outage), so the
  verdict never reached the run. Diagnostics: agent turns 14-37 s (platform latency, hang-up risk as in M5); DOB asked
  3x ('didn't catch that') although given each time (talkative); no tool events in the dump, cause open. First live
  run of eng.4's FACTS code nodes: the flow worked end to end. Ledger +2 (2 attempts): cum **287**. Cost 0.2055 USD.
  **Queue stays PAUSED** (simulation-level result missing, latency degraded); user decides whether the call-level
  verdict counts.
- **12:20 UTC user: YES to the call-level verdict fallback (unit-tested first). Done: 4631971.** `run_cases_retry.py`
  now fills runs with no outcome or 'analyzing' from the call record's successCriteriaResult (never overrides
  pass/fail/inconclusive/error), prints `VERDICT FROM CALL RECORD`, marks rows `verdict_source` call|run. 12 new
  tests, 794 passed. Read-only check: call-record verdict == run verdict on **43/43** judged calls (M3 x3, M2 r3).
- **12:16:40 the platform re-ran the paused smoke's call** (new call af507b83, attempt 3/4) although call 6af560aa
  had success=True: a stalled analysis triggers a full call retry (cost up to 4x per case while the judge stalls).
  Ledger +2 (attempt 3 + a possible 4): cum **289**. Queue still PAUSED; waiting for Service Check BOTH_QUIET.
- **12:22 UTC:** 6d0c9464 un-paused itself a 2nd time (status running, updatedAt 12:21:31: the platform flips status
  when it retries); re-paused 12:22:22 (API confirmed). Runs left: 91a0f2c7 analyzing 4/4 (no retry), b94597c3
  inconclusive 3/4, 06d16b86 error 3/4 => at most 2 more calls. Re-pause each time it flips (standing approval).
- **12:23-12:29 UTC:** review of the fallback (2 lenses) -> fixes aa7726a (shape guard, ONE unretried call read, rows
  carry `attempts`); 798 passed. Open (needs user): fallback for runs ending `error`/`inconclusive` with 'analysis
  never arrived' (they still repeat the whole rep); read-only: both such 6d0c9464 runs with a call have a call verdict
  (True), 7 more run==call agreements. **6d0c9464 COMPLETED 12:26:29** (final pass 6, fail 1, error 5, inconclusive 1;
  no more calls possible). Smoke 94c9e350: paused, run at 4/4 'analyzing' (no retry left); its retry call af507b83
  (12:10:32-12:10:58) had call verdict True and NORMAL latency (agent gaps 0-1.5 s, DOB asked once); the smoke
  customer's ledger holds exactly one consistent set (5 tools, 1 promise) although both calls made create_promise
  per the judge (probably close_call ends the session; unverified). **Credits 391.06 (12:29)**: 10.78 USD since 11:30
  ~ 41-49 calls, matching 6d0c9464's ~41 attempts: ledger corrected +22 -> cum **311**. Only our 2 sims exist.
- **12:31 UTC user: extend the fallback, then resume. Extension done: 7bfcf41** (`awaits_judge`: also error/
  inconclusive whose reason is missing or 'analysis never arrived'; 801 passed). **BUT (Service Check 12:31):** smoke
  94c9e350 COMPLETED 12:29:51 with run outcome ERROR after 4/4 ('No call created within 300s' on attempt 4 at
  12:23:25) and 6d0c9464 started one more call 12:23:45 (f007306e) before completing. A call-creation failure at
  12:23-12:28 = continuing platform error under the user's rule, so the queue is NOT resumed yet. Plan: after
  Service Check's first BOTH_QUIET tick, a 2nd bounded smoke via scratch `smoke_once.py` (fallback wired, no rep
  repeat, POST maxRetries 0 = one attempt, live spec 0-10); resume the E4 queue only if it gives a judged verdict
  (run or call record) with a created call and normal latency.
- **12:37-12:40 UTC 2nd smoke 188b9156** (maxRetries 0 -> maxAttempts 1, confirmed): call 6f4c5503 created in 10 s,
  RUN-LEVEL verdict (judge works again) = FAIL, customer hung up at 105 s. Diagnosis (transcript + events in
  `runs/dev/r4/SMOKE2-e4a.{log,json,call.json}`): setup code node OK (0.17 s); routing and verify_identity correct
  (DOB verified 0.5 s); the MODEL took 54 s (45.1 -> 99.5 s) to emit the tool call and the simulated customer 29 s to
  answer: latency, not agent logic (kit: 'the phone agent was slow'). Latency flaps: 14-37 s (12:01), 0-1.5 s
  (12:10), 14-54 s (12:37). **Queue stays PAUSED** (a rep now would measure hang-ups). Ledger +1: cum **312**.
- **12:45 UTC USER: keep the queue paused for now.** No latency probes or other simulations until the user says so.
- **12:55 UTC: FINAL-SELECTION EVIDENCE DOSSIER ready for the user: `docs/reviews/2026-10-11-final-selection-evidence.md`**
  (9-agent read-only workflow, every claim checked against sources; §10 eng.6/.7/.8 addendum, adversarially checked
  and corrected: Fix 1 PUB-05 closing-row defect, cand-eng.8 4267bb0 unmeasured, matched-comparison tiers T1-T4, cap
  arithmetic after the E4 queue). Decisions D1-D11 in §8 belong to the user; defaults: nothing runs, nothing is
  selected or tagged. Also found: `cand-retry.4` (d53fa0e) = G1 + platform retries, renders byte-identical to the
  measured G1 agent (the measured fallback). Outcomes read at completion during the outage are provisional (the
  platform re-judges completed simulations).
- `queue.txt` restored: E4-A-styledA, E4-AB-all, E4-AB-xb, E4-VE (the runner had popped E4-A before its POST failed).
- **Resume rule (user):** only after the endpoints recover AND one bounded smoke simulation gives a complete judged
  result: `.venv/bin/python -u scripts/run_cases_retry.py f166447e-2fc1-42d0-9794-643a8b881f8f --cases
  runs/dev/r4/smoke-pub01.json --reps 1 --out runs/dev/r4/SMOKE-e4a.json > runs/dev/r4/SMOKE-e4a.log 2>&1` (1 call,
  PUB-01 talkative, slot exp-eng4-a); add it to calls.tsv; then `rm sim/STOP` and restart qrun4.sh + monitor.
- **Offline prep done during the pause:**
  - Fresh-clone `--dry` rehearsal of cand-eng.4 (uv python 3.12.13, no venv): exit 0, 98 s, 2 model calls,
    `git=cfa4d9d dirty=False`, spec check round 1 PASS, validation PASS, secrets CLEAN
    (`runs/dev/r4/fc-eng4-a.trace.log`).
  - Trial merge main -> cand-eng.4 (throwaway, removed): **no conflicts**, 872 passed, ruff check + format clean.
    Main's side changes NO builder code (src/, builder/, kit/, pyproject, uv.lock untouched since the merge base
    a01a17c), so the merged commit builds exactly the deployed eng.4 agent plus the current docs/RUNBOOK. Note that
    cand-eng.4's own `docs/RUNBOOK.md` is OLDER than main's: `freeze-final` must be on the merged commit (user's call).

## UPDATE 11:37 UTC: cand-eng.4 picked to MEASURE FIRST, DEPLOYED (superseded by the 11:44 pause above)

- **User picked `cand-eng.4` (cfa4d9d) at 11:30 UTC to deploy and measure first; NOT a final selection** (Decision log). Worktree (detached):
  `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-eng4`.
  Its `--dry` renders of spec-a-llm and spec-ab-llm-c45758f differ from cand-final.1 only in the 3 FACTS code nodes.
- Slots (in `slots.tsv`, export MATCH: 0 changed, 0 render-only, 0 needs-review):
  `exp-eng4-a` wf 66db0b41 / agent f166447e (spec-a-llm); `exp-eng4-ab` wf 0a819c5b / agent 0988e6f1 (spec-ab-llm-c45758f).
  Build logs `runs/dev/r4/build-eng4-{a,ab}.log`: exit 3 = chat smoke 500/504 only; the chat endpoint 504'd for the
  G1 control too (platform). The A create POST 504'd once then retried: **a stray duplicate workflow may exist**.
- `exp-eng4-ve`: FRESH build of `tests/fixtures/briefs/variant-e.md` (worktree) with `--save-spec
  runs/dev/r4/spec-eng4-ve.json`; log `runs/dev/r4/build-eng4-ve.log`. Register in slots.tsv + export-check it before
  the runner reaches E4-VE (otherwise the runner stops with "unknown slot").
- **Queue (user D3 at 11:35):** E4-A-styledA, E4-AB-all, E4-AB-xb (x3 each), then E4-VE (eng-variant-e.json x3).
  Old component A/Bs parked in `sim/queue-parked-1135.txt` (not to run). Runner qrun4.sh started 11:36 UTC
  (STOP removed); results `runs/dev/r4/E4-*.{log,json,meta.json}`.

## SIMULATION CHAT HANDOFF (11 Oct 11:25 UTC; HISTORICAL, superseded by the 12:57 handoff above)

**Roles.** This chat owns ALL deployments and simulations. The Methodology Developer (engine) chat fixes the
builder on its own branches and hands over tags; its log is `docs/plans/2026-10-11-engine-fixes-log.md`
(hand-off sections at lines ~57, ~125, ~197). Detailed event log/results: `docs/plans/2026-10-11-overnight-report.md`.

**State now: NOTHING is running, nothing new deployed.**
- Current item stopped on the user's instruction: M5r2-ab1W-all-c5 (G1 fresh A+B build exp-ab1-w, M5 re-run reps 2-3
  at concurrency 5). Client terminated 11:14:50 (exit 143); its simulation 6d0c9464 PUT `paused` at ~11:22 (API
  confirmed). **It produced no valid rep:** rep 1 (sim 3d8c7da4, 10:12-~10:45) was discarded because PUB-02 and PUB-13
  had no judge verdict (its judged calls: PUB-04, 06, 08, 12 failed, unclassified; see `runs/dev/r4/M5r2-ab1W-all-c5.log`);
  the repeat (6d0c9464) was stopped before its results were collected.
- Runner `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun4.sh` has exited; `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/STOP` is SET. Ledger `runs/dev/r4/calls.tsv`: **257 calls** (M5r2
  counted 26 = 2 simulations launched). CAP in qrun4.sh is 500. Last credits reading ~406 (10:09).
- Platform: outage 09:38-10:08 UTC, badly degraded since (GETs 504 after ~60 s, list endpoint 500/504, a 13-call rep
  took ~33 min instead of ~4, judge verdicts missing). Check with `.venv/bin/python scripts/credits.py "check"`.

**Candidate selection comes FIRST (user, after the context restore), then deployment.** All engine tags are UNMEASURED.
| Tag | Commit | Branch | What |
|---|---|---|---|
| `cand-final.1` | ca80d52 | cand-final | G1 + identity fix v2 + builder retries + offer-wait fix + precedence (ending_wins + 2 guards); 820 tests; offline checks + fresh-clone `--dry` rehearsal passed |
| `cand-eng.4` | cfa4d9d | cand-eng-safe | cand-eng.3 + review-2 fixes (01b7a80) + fixtures (variant-e brief, 4 cases); 859 tests; prompts for A, A+B, raw-A byte-identical to cand-final.1 (code nodes differ); single-product FACTS/setup equal cand-final.1 on 8000 states each |
| `cand-eng.5` | 27f5647 | cand-eng | cand-eng.4 + item 3 (PUB-12 multi-product paragraph, 4006d5c); 861 tests; changes Brief B FACTS by design |
| `cand-eng.3` | 57e6e66 | | **superseded** (do not measure) |
Engine items in cand-eng.4/5: all-at-once verify_identity (6c80c5d, d54a850); a brief's own "too much" rule
(0267b60, 17eddb0, 01b7a80/c737844); "this <weekday>" from the brief (fd705de); percentage floor half-up, hint, stdout
flush (57e6e66). The engine chat's measurement request (log ~:197): cand-eng.5 vs cand-eng.4 (or cand-final.1) on
styled-extra-b x3 (PUB-12 target) and styled-b x3, fresh A+B builds, strict 3/3; adopt eng.5 only if PUB-12 reaches
3/3 and no B case falls below; also verify the A set. Behavioural cases for the new paths:
`tests/fixtures/cases/eng-variant-e.json` with an agent built from `tests/fixtures/briefs/variant-e.md` + kit openapi.
Engine note: the styled-extra-b PUB-12 check "asks for no payment on it" is misread by the judge (official wording:
"takes no promise"); rewording that fixture is the user's call.

**Queue staged (not started):** `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/queue.txt` begins FINAL-A-styledA (exp-final-a), FINAL-AB-all and
FINAL-AB-xb (exp-final-ab) for cand-final.1, then O4, identity A/B, offer-wait A/B, M2 extra-B re-run, O1
(old order in queue-before-reorder.txt). **After the user selects the candidate, re-point these lines** to slots built
from that tag (e.g. exp-eng4-a / exp-eng4-ab), and drop or keep the component A/Bs as the user decides.

**Deploy + start procedure (only on the user's go):**
1. Worktree for the chosen tag (cand-final.1 already has `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-final`; for an engine tag:
   `git worktree add /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/wt-<tag> <tag>` then symlink `.env` and `.freya-agents.json` from the main tree).
2. From that worktree: `set -a; . ./.env; set +a; uv run python builder/build.py "$R/kit/briefs/brief-a.md" "$R/kit/tools/openapi.json" --spec "$R/runs/dev/spec-a-llm.json" --slot <slot-a>`
   and with `"$R/kit/briefs/brief-a.md" "$R/kit/briefs/brief-b.md"` + `--spec "$R/runs/dev/spec-ab-llm-c45758f.json" --slot <slot-ab>`
   (saved specs: matched to the M2/M3 controls). Exit 3 with only a chat 503/504 = deployed (RUNBOOK). For the
   engine's "fresh build" requests, build without `--spec` (fresh extraction) into separate slots.
3. Add the slots to `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/slots.tsv` (name, agent id, workflow id, 1, build tag+commit, spec path).
4. Export check: `freya.export_workflow(<wf>, runs/dev/r4/exports/<slot>.json)`; `--dry` render into
   `runs/dev/r4/renders/<slot>.json`; `python3 runs/dev/r4/exportdiff.py <slot> <render> <export>` (0 changed, 0 render-only).
5. Edit the queue, `rm /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/STOP`, start `bash /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun4.sh >> /private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/ababcede-be05-48a1-9009-b4b2dae0baeb/scratchpad/sim/qrun.out 2>&1` in the background,
   re-arm a monitor on qrun.out ("done |CAP:|Traceback").
- `scripts/run_cases_retry.py` (a5f1514): GET retries ~17 min, health gate before start, auto-pause of stuck
  simulations (standing user approval), one repeat of a rep without judge verdicts, concurrency 5.

**Matched controls:** styled-a: M3 G1 exp-g1-a 10/10 (`runs/dev/r4/M3-G1-styledA.json`), F2 v8 8/10
(`runs/dev/r3/styledA-a2-bd4da7c.json`); styled-ab-all: M2 F2 v14 dev-ab-llm 8/13 (`M2-ABv14-all.log` reps 1-2,
`M2-ABv14-all-r3.json`); extra-B: M2 (partly unjudged), M5. Measured so far: M1 W=G1; M3 G1 10/10; M4 G1 fresh
raw-A 8/10 (PUB-06 agent re-offer, which the offer-wait fix targets); M5 G1 fresh A+B 7/13 (latency hang-ups at
concurrency 13; no valid re-run); PUB-12 extra-B fails on every build (engine item 3 in cand-eng.5).

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
