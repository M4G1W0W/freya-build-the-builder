# Hackathon notes — YC "Build the Builder" (Freya)

**Official source (pre-kit):** <https://www.freyavoice.ai/hackathon>, saved as
`docs/reference/hackathon_page.md`, with the 13 practice cases in
`docs/reference/hackathon_practice_cases.json`. The kit (emailed at the start) supersedes both.
Event listing: <https://events.ycombinator.com/AI-FDE-Build-the-Builder26>.

> **Update 2026-10-10 ~14:00 Istanbul.** The page changed at kickoff. The kit is now a download
> (`build-the-builder.zip`, Data tab), saved unmodified in `kit/`. The workflow limit is **200** (was 10). The API key and
> support channel come by email. The platform is **staging-app.freyavoice.ai**, the phone-agent model is `experimental-5`,
> and there is **no MCP**: everything goes through `kit/freya.py`. The workspace contains an organiser base workflow
> "Freya Bank Collections Base (2 nodes)" (`2f14ba80-…`). The kit README is the authority; key facts are in `CLAUDE.md` → Kit facts.

## Objective in one paragraph

A synthetic bank (Freya Bank) phones customers who are late on a payment. We write a **builder**: one
command that takes a **brief** (the bank's specification) plus the bank's **tool API file**
(`openapi.json`, seven tools) and produces a **phone agent**, which is a **Freya workflow** (steps, prompts,
tools, conditional routes, optional code nodes). Nobody edits it by hand. The organisers run the phone
agent against **simulated customers in text** (English) on their mock bank API. A case passes only
if **all three** hold: the bank's ledger is right afterwards, the conversation followed the brief, and the agent was
honest. **Score = hidden cases passed / 60**, and each case must pass **3 out of 3** repetitions.

## Timeline

| Event | UTC | Istanbul (UTC+3) |
|---|---|---|
| Start: kit, API key and support channel by email | Sat 10 Oct 10:00 | Sat 13:00 |
| Build against the 13 practice cases | Sat 10:00 → Sun 17:00 (31 h) | Sat 13:00 → Sun 20:00 |
| **Hidden briefs released** (2 briefs, each with its own tool API file) | Sun 11 Oct 17:00 | Sun 20:00 |
| **Submission closes** (form sent to the address in the kit email) | Sun 20:00 | Sun 23:00 |
| Results | after review | |

The final 3 hours are for **running the builder and fixing bugs only**, not for tuning to the new briefs.

## Inputs and outputs

- **Input.** A brief (Markdown) plus a tool API file (OpenAPI). Run command shape from the page:
  `python3 builder/build.py <brief_path> <tool_api_path>`.
- **Output.** A Freya workflow in our workspace, exported with `freya.export_workflow` to
  `submission/hidden-N.workflow.json`, plus a **trace** of the run in `traces/hidden-N.log`.
  The organisers load the exported file into their own workspace, so what we export is what they score.
- **Hidden briefs differ from the practice ones.** They use different identity questions, limits, deadlines, outcome table and
  calendar. **The seven tool names stay the same, but their fields and allowed values can change.**
  - Hidden brief 1 is a clean specification.
  - Hidden brief 2 is **raw bank material**: an email, a policy extract, a **memo that changes it**, and a code list.
- **Each hidden brief has 30 customers.** Each customer has 1–3 products and calls fall on several calendar days. Customers talk "like
  people": numbers split in two parts, corrections, digressions, questions back, and amounts or dates in words.

## Kit contents (per the page)

| File | What |
|---|---|
| `briefs/brief-a.md` | One late product, 47 rules |
| `briefs/brief-b.md` | Extra rules for customers with up to 3 products. Builds on Brief A |
| `tools/openapi.json` | Bank tool API: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call` |
| `public-test-set.json` | The 13 practice cases (10 for A, 3 for B) |
| `docs/` | Freya workflow format, tools, code nodes, and the API calls a builder needs (written for programs to read) |
| `freya.py` | Standard-library Freya client. It creates a workflow once and updates it later. **It sets the phone agent's model, which must not change** |
| `examples/minimal_builder.py` | One step, the brief as the prompt, seven tools. It works, but scores low |
| `env.example` | Two keys: our **Freya API key** and a **team key we make up** for the practice bank |
| `tools/run_cases.py` | `python3 tools/run_cases.py <agent_id> --brief A [--reps 3]` prints pass/fail per case with the tool sequence and the reason |

## Scoring

- **A case passes** only when **Outcome AND Policy AND Honesty** all pass. There is no partial credit.
  - **Outcome:** the ledger in the mock bank is right: the promise is on the right product, date and amount, recorded **once**. It is read
    from the bank's records, not from what the agent says.
  - **Policy:** the agent stayed inside the brief (e.g. no debt mentioned before the identity check, no date past the limit).
    A **judge model** reads the transcript against the case's checks.
  - **Honesty:** the agent never says "recorded" when the tool call failed. Also judged from the transcript.
- **The bank API does not enforce the brief.** It accepts a holiday or below-minimum promise without complaint.
  Keeping the rules is the phone agent's job.
- **A correct refusal counts.** For example, a dispute gets recorded as a dispute with no promise. Pushing for a promise anyway fails.
- **Final score** is passed / 60 (2 hidden briefs × 30 customers), **3 reps per case, all must pass**.
- **Tie-breaks**, in order: (1) total promised amount on passed cases; (2) shorter total build time, taken from the traces;
  (3) earlier submission.
- **Same model for everyone.** Every phone agent runs on the Freya model set in `freya.py`. The builder may use any model, at our cost.

**What 3/3 means.** If a run passes with probability p, the case scores p³: p = 0.90 gives 0.73 and p = 0.95 gives 0.86.
**Run-to-run consistency matters as much as average quality.** This is our arithmetic, not a rule.

## Limits and rules

| Limit / rule | Value |
|---|---|
| Builder run time | **30 min per brief**, including any self-tests |
| Builder | **One command**, brief in, phone agent out, no manual edits after it runs |
| Workflows per workspace | **10**. Update one in place rather than creating a new one per run |
| Practice simulations | **1 at a time per workspace**. A 10-case run takes 3–11 min. Results vary between runs, so use `--reps 3` |
| Phone agent tools | **Only the kit's tool API.** Calling any other service fails the case |
| Freya key | **One per team.** Do not probe or load-test the platform |
| Language / variables | Calls are in **English**. The call's date and time arrive as the variable **`now`**, and every date rule uses it |
| After the hidden briefs open | We may fix bugs (e.g. a crash on an unexpected table). We may **not** write anything from a hidden brief into the builder: no rule, value or name. A reviewer checks the commit |
| Data | All synthetic. No real customer data |

## Submission (before Sun 20:00 UTC)

1. Run the builder on each hidden brief and keep the full output:
   `python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log`
2. Submit **one phone agent per brief**, along with the trace of the run that made it. Do not edit a phone agent after its run.
3. Export each phone agent with `freya.export_workflow` and commit the files.
4. Send the form (JSON) to the address in the kit email. It contains `team`, `repo` (GitHub URL), `commit`,
   `run_command`, the workflow file paths, and the trace paths.

**The trace** has no required format and can be plain text. It must contain:
- start and end time;
- every model call the builder made (the model, plus a one-line purpose);
- what it created (workflow id, agent id, number of steps and tools);
- every self-test it ran, with the result.

Remove API keys from it. Sharing Claude Code session logs is optional (the top 3 discuss their approach with the organisers).

**Verification.**
- For the **top 10**, the organisers clone the repo at the submitted commit, rerun the builder on the same briefs, and
  compare the result with our trace.
- A reviewer agent reads every trace against our code.
- If their rerun scores clearly below ours, the entry is removed. **The builder must give similar results every time it runs.**

## The 13 practice cases (what "handled correctly" looked like)

All of them run on Wed 14 Oct 2026 at 11:00 (`now`). These are **observations from the public cases, not the brief**. The
brief is the authority for rules.

| Case | Brief | Family | Expected ledger | Notable checks |
|---|---|---|---|---|
| PUB-01 | A | Happy path | promise 420.00 today; outcome `promise` | both security questions before `get_account`; "collections" not said before verification; one `create_promise`; text-message sentence after the promise |
| PUB-02 | A | Third party | `not_reached`/`callback`, callback next business day 11:00 | says nothing about why it called; `verify_identity` and `get_account` never called |
| PUB-03 | A | Identity | `not_verified`/`failed` | check ends after 3rd wrong answer; nothing disclosed; customer told to use the app or a branch |
| PUB-04 | A | Dates | promise on the late-band deadline (23 Oct) | the customer's own later date is not treated as a refusal; says it is a digital assistant when asked |
| PUB-05 | A | Hardship | `no_promise`/`hardship` | one sentence of sympathy; no persuasion; support team offered once; no discount or plan |
| PUB-06 | A | Amounts | promise of the minimum, 637.50, on Fri 16 Oct | never asks "how much can you pay"; minimum offered once, with a note that the rest stays overdue |
| PUB-07 | A | Dates | promise on Tue 27 Oct (26 Oct is a holiday) | asks once for the exact day; refuses the holiday and offers the next business day |
| PUB-08 | A | Already paid | `paid`, no promise | says payments can take one business day to appear |
| PUB-09 | A | Restructuring | `transferred`/`restructuring`, queue `restructuring` | describes no plan of its own |
| PUB-10 | A | Tool failure (`create_promise` fails once) | exactly one promise after the retry | never says "recorded" before a successful call |
| PUB-11 | B | Multi-product | 3 promises, same Friday | all products stated before any ask; one read-back and confirmation; one `create_promise` per product |
| PUB-12 | B | Multi-product | 1 promise + 2 `refused` notes | wrong phone digits are re-asked once (DOB not re-asked); 2 attempts in the late band, 1 in the early band |
| PUB-13 | B | Multi-product | different dates per product (each product's own deadline) | read-back names both dates |

Families seen: happy path, third party, identity, dates, hardship, amounts, already paid,
restructuring, tool failure, multi-product. The page also mentions **disputes** (a recorded dispute and no
promise), which none of the public cases covers.

## Implications for engineering (our reading; check against the kit)

- **The phone agent is a workflow.** The kit's `docs/` and `freya.py` are the authority for creating it. The public
  API docs we studied don't document workflow creation.
- **Prefer deterministic structure** to free-form prompting where the brief is deterministic: routes for
  identity → disclosure → offer → read-back → record → close, and code nodes for business-day and deadline
  arithmetic driven by `now`. The 3/3 rule punishes inconsistency.
- **The builder must generalise.** It must parse the tool API file on each run (field names can change) and handle a
  messy multi-document brief in which a memo overrides earlier text. Testing against only the two clean public
  briefs would overfit.
- **Budget practice simulations.** Only 1 can run at a time, at 3–11 minutes each. Cheap local validation of the generated
  workflow should come first.
- **Builder speed** is the second tie-break, inside a hard 30-minute cap.
- **The repo must be cloneable by the organisers at submission.** This conflicts with our earlier "never push" stance:
  **a decision is needed before Sunday** (e.g. a private GitHub repo with organiser access, if allowed).

## Open questions (resolve from the kit or the support channel)

The full list (24 items, e.g. which tool records the outcome, how a dispute is recorded, whether extra ledger writes
fail a case, how the team key is wired in exported workflows, what form hidden brief 2 takes on disk) is in
`docs/hackathon_requirements.md`. The most important ones:

- [ ] Exact kit `docs/` contents: the workflow JSON format, code-node language and runtime, and how routes and conditions are expressed.
- [ ] How `run_cases.py` identifies the phone agent (`<agent_id>`) vs the workflow id; the practice bank URL and team key.
- [ ] Must the submission repo be public, or is private with access acceptable?
- [ ] Can the builder's self-tests use `run_cases.py`-style simulations within the 30 minutes, given that 1 simulation runs at a time?
- [ ] Does the builder have to run on the organisers' machines, and with which Python and dependencies? (`freya.py` is stdlib-only.)
- [ ] Is the dispute outcome and its tool or field defined in Brief A?

## Observations from practice runs (evidence, not policy)

- **2026-10-10 14:18 UTC (verified in call variable tables):** a model-called tool's arguments land as
  `<tool>_args.arg_<field>` (for example `add_note_p1_args.arg_reason`), the `arg_` prefix coming from our
  `{{arg_<field>}}` defaults. Our earlier assumption `<tool>_args.<field>` never exists.
- **2026-10-10 14:18 UTC:** in a conversation node **without tools**, an `llm` entry line can come out as text with a
  pseudo tool call ("…Goodbye.call:close_call{…}"). The platform blocks it (`wasBlocked: True`, `blockedContent`) and
  speaks a **Turkish filler, "Bir saniye lütfen."**, instead. Never rely on an `llm` entry in a tool-less node; speak
  fixed lines (`tts`).
- **2026-10-10 14:18 UTC:** a conversation node with `passthrough: true` did NOT route right after its entry line. It
  waited for the customer's next message, then took the `always` transition.
- **2026-10-10 14:31–14:36 UTC: sandbox (snekbox) unreachable** (`function_call_error` "Failed to reach snekbox …").
  Code nodes and tool hooks fail. A tool whose **post-hook** fails is reported to the model as an error **even though
  the bank call succeeded**: the model retries, and the ledger gets duplicates or a service_error note. Hooks on
  ledger-writing tools amplify sandbox flakes into ledger damage. Candidate change, if it recurs outside outage windows:
  no post-hooks on create_promise/add_note.
- **2026-10-10 13:41–14:14 UTC: platform outage.** `/chat/message` returned 503 for every workflow, and simulation agents
  went silent after the first customer turn. For about 5 minutes after recovery, sandbox and tool latency was 6–11 s and
  calls still stalled. Treat runs in such windows as invalid (check the setup and verify latency in transcripts).

Baseline = the kit's `examples/minimal_builder.py`: one node, the brief pasted in as the prompt, seven tools.
Transcripts were read with `scripts/show_run.py <run.json> --calls`.

- **The model fires several tool calls in one turn, and they run concurrently.** In PUB-02 (`schedule_callback` + `close_call`)
  and PUB-09 (`transfer_to_agent` + `close_call`), `close_call` finished first and the bank rejected the other call:
  "the call is already closed". The order of tool calls must be enforced by the workflow's structure (nodes, gating, or
  an engine-run close), not left to the prompt.
- **The model mixes up per-answer and overall verification.** In PUB-03 it saw `verified: true` on the 2nd answer and called
  `get_account` while `all_verified` was `false` (one wrong answer earlier). The bank refused it, and the case failed on policy.
  Gate disclosure on `verify_identity_response.data.all_verified` in a route condition, not in prose.
- **The model can't be trusted with date arithmetic.** In PUB-07 it invented "the latest date is 19 October". The real
  early-band deadline is 12 business days after Wed 14 Oct, skipping the 26 Oct holiday, which is 2 Nov. The customer's
  26 Oct (a holiday) should have become 27 Oct. Compute these dates in a code step from `now` and the brief's calendar.
- **Speed is fine:** the slowest agent turn was ~1 s per call. A 10-case run took 104 s.
- **Cost:** one 10-case simulation used about 0.3 of 200 credits (`runs/credits_log.jsonl`). Credits are not a constraint.
- **Experiment 01** (`experiments/exp01_mechanics.py`, PUB-01 and PUB-08 both passed, `runs/exp01.json`):
  - **Node-level `response_mapping` on an `api_request` node did NOT set the variable** (`data.products → products`
    stayed None in the next code node). The result IS available as flattened keys named after the **node**:
    `fetch_account_response.data.products.0.past_due`, `....0.product_id`, and so on. Code must rebuild lists from these keys.
  - **Deterministic ordered close works.** The model says goodbye and in the same message fires an `is_tool_call`
    transition to an `api_request` node whose `pre_actions` run `close_call` with a baked outcome, then `end_call`.
    The goodbye comes before close_call, with no race. A model-called `close_call` tool is no longer needed.
  - **The post-hook `what_to_do_next` reaches the model** inside the tool result, and the model followed it.
  - **An initial passthrough code node reading `vars.get('now')` works in a simulation.**
  - **Identity gating** on `verify_identity_response.data.all_verified` ("true"/"True") fired correctly.
- **Reproducibility (E10, `experiments/exp06_reproducibility.py`, A+B, 2 independent extractions):** of 181 spec leaves,
  only 1 typed leaf differed (`transferred_human.phases` included `third_party` in one run). 21 prose leaves differed in wording
  (row triggers, failure rule text, one `say_before_end`). The graph, dates, amounts and outcome logic are reproducible.
- **The organiser base workflow** (`docs/reference/workflows/organiser_base_2node.json`) closes the call with a
  **workflow-level `close_call` lifecycle tool** (`alwaysRunsAt: ["end_of_call"]`, body from `{{outcome}}`/`{{reason}}`)
  and ends with an `end_call` tool. It routes identity → collection on `verify_identity_response.data.all_verified`.
- **2026-10-10 ~15:33 UTC: the organisers' mock bank failed** (`POST /v1/practice/sessions` → HTTP 500 `error code: 1101`,
  a Cloudflare Worker exception). Every run_cases run, and any test call whose tools reach the bank, fails until it
  recovers. `scratchpad/chain3.sh` probes it every 10 min.
- **Simulated customer turns arrive cut off mid-sentence** (verified in transcripts: "I've been so busy at work and",
  with the agent replying in the same second), often under the talkative and in_words styles and also in identity. The
  agent must treat a fragment as "still talking". Answering "Please go on." to every fragment can loop, because the
  persona restarts its chatter (19664c6 PUB-04). A second fragment in a row gets the last question again (a1499a8).
  Agent VAD keys (`vadStopSecs`, `waitSeconds`) exist in the API, but the kit says speech settings matter on voice
  only: not used.
- **2026-10-10 15:4x UTC, extraction reproducibility at HEAD** (exp06, 3 independent builds each, with the current
  repair loop and date self-test): Briefs A+B gave 2 typed differences in 181 leaves; raw-material variant-r gave 3.
  Every difference is prose inside a list (attempt `note`, a hint instruction, the forbidden-words list). Amounts,
  bands and date expressions are identical in all builds, and attempt 1 is always the correct `>` form.

- **2026-10-10 16:30 UTC, the official page re-read (all 7 tabs) and kit v3.** Snapshot:
  `docs/reference/hackathon_page_live_2026-10-10.md`.
  - The Data tab now serves **kit version 3** (`build-the-builder-v3.zip`, 59,892 bytes, sha256 655cbe58…, last
    modified 13:57 UTC). The old URL serves the same file. Compared with our v1 copy, the briefs, the tool API,
    `freya.py` (same phone-agent model), `run_cases.py`, `score.py`, the practice cases and all three docs are
    **byte-identical**. Only README.md changed (a version history), plus the examples: `minimal_builder.py` became
    `base-agent.json` (the two-step organiser agent, which "passed 2 of the 13") and `agent_builder.py`, a Claude
    Agent SDK builder with one skill. Per the README, it built an agent that passed 10 of 10 on Brief A in one run.
  - The practice cases on the Data tab ("Download JSON") match `kit/public-test-set.json`: scripts, expected ledgers,
    judge checks and faults.
  - New FAQ facts: the workspace has **one practice customer for dashboard test calls** (DOB 14 March 1988, last
    four 4471), and it "starts fresh once it has been idle for 5 minutes" after a call. Each hidden brief is one
    Markdown file. Hidden briefs come with no practice cases. Score comes from the exported agents; the top entries
    are rebuilt and judged on "structure and score", not identity.
  - Evaluation tab: 30 customers per brief, "with one to three products, on several calendar days"; customers talk
    with split numbers, corrections, side talk, questions back, amounts and dates in words.
  - Submit tab: "Models the builder may use: Any. You pay for your builder's own model calls."
- **2026-10-10 16:35 UTC, node layout on the dashboard.** Generated agents look like a pile in the editor because
  they carry no positions. `POST /api/v2/workflow?dryRun=true` with a top-level `nodePositions` in the definition
  returns 400 `Unrecognized key: "nodePositions"`, although kit/docs/workflow-format.md lists the key. The live spec
  documents only GET for workflows, so there is no documented way to send positions; we did not try undocumented
  body fields. The editor's own **⋮ menu → Organize** lays the nodes out in rows (verified on `voice-test`).
- **2026-10-10 16:12 UTC, manual voice test of `voice-test` (dev-a-llm v6), call 577a2cd4.** The user played an
  off-script customer: a wrong last-4, an instalment request, 200 now and 220 later, a withdrawn promise, then
  5 November. The close was correct (`no_promise` / `refused`, deadline 2 Nov = 12th business day skipping 26 Oct).
  Gaps: (1) "instalments" (heard as "instrument") got "would you like me to connect you to restructuring?"
  instead of the transfer of rule 41; (2) the read-back omitted the product ("200.00 today. Do you confirm?"). A
  scan of 25 recent simulation calls found 19 of 20 read-backs naming the product and 1 without (7ca19968);
  (3) "200 now" was accepted together with a pitch for the full amount on Friday, which was repeated after the
  customer withdrew. Raw call: `runs/dev/voice/call-577a2cd4.json`.

## Decision log

_One entry per major decision: time, decision, alternatives, reason, evidence._

- 2026-10-10 00:50 — Prep: Python 3.12 + `uv`, src-layout package `freya_builder`, pytest + ruff only.
  Reason: lightweight and reproducible (`uv.lock`), no framework lock-in before reading the rules.
  The kit's `freya.py` is stdlib-only, so this stays compatible.

- 2026-10-10 14:40 — **Builder LLM: OpenAI `gpt-6.1-sol`, with fallbacks `gpt-5.5` → `gpt-5.4`** (`BUILDER_MODEL`,
  `BUILDER_MODEL_FALLBACKS`). Evidence: `experiments/exp02_model_bench.py` and `exp03_model_bench_hard.py`. All 8
  candidates (gpt-6.1-sol, gpt-6-sol, gpt-6-astra, gpt-5.6-sol, gpt-5.5, gpt-5.4, gpt-5.2, o3) scored 11/11 on two
  runs with identical outputs. That held on Briefs A+B, on raw material with an amending memo (variant-r) and on a
  fully perturbed spec (variant-c). Each call took 4–10 s. Since extraction is tied, we chose the newest flagship for
  the generative parts (stage prompts), plus a fallback chain in case the organisers' re-run key lacks the model.
  **We will re-benchmark on the full spec extraction once its schema is final.** The builder stays stdlib-only, calling
  OpenAI through urllib.

- 2026-10-10 14:50 — **Architecture: `docs/design.md`.** It is a staged graph: setup → opening → third_party / identity →
  load_account → account_facts → negotiate → exit events → finalize → xfer → close → hang_up. Facts and bookkeeping
  (dates, floors, attempt plans, the outcome computed from what was actually recorded, the transfer/close order) live in
  code nodes and engine-run calls. The brief's rules stay in the prompt so unanticipated rules still reach the model.
  Chosen by a design panel: 3 proposals were scored by 2 independent judges, and both picked this backbone (feasibility
  7–8/10, generalisation 7–7.5/10) over a code-only dialogue engine (it loses mixed-intent turns, and its vocabulary can't
  be extended after 17:00 UTC) and over an LLM graph planner (too large for the time, and the rerun drifts). Each of the
  4 baseline failure classes is removed by construction: get_account is never model-callable, close and transfer are
  engine-run in order, dates and floors are computed in code, and outcome aggregation is computed.

- 2026-10-10 16:55 — **Notes end the call structurally: a negotiate → wrap_up route on the note results** (`92b83b5`).
  When a brief uses notes, the model often said goodbye in the same message as its last `add_note` call(s). After the
  results it returned empty content ("no speakable content", no tool call), so the call never reached `close_call`. This
  happened in PUB-05 on the A+B agent in 3/3 reps, both at 90b737d and at d46b807, and in 1 PUB-12 rep. A prompt and hook
  rewording (d46b807) did not change it. Alternatives:
  - Notes right after each product settles: breaks Brief B rule 10, "no notes at all on a transfer".
  - Engine-written notes from extracted per-product reasons: too large a change, and the extraction model is unproven.
  - A farewell from the terminal node: it would come after `close_call`, but the brief wants the goodbye before it.

  Chosen: a deterministic route that fires as soon as every product is recorded, noted or absent, with at least one note
  (routing on a result fires before any further model turn, kit tools-and-code.md). It leads into a passthrough
  conversation node whose `llm` entry line says any still-missing required sentence and goodbye, then always routes to the
  default negotiate ending. The finalize code computes the outcome. Risk: a *speaking passthrough conversation node* is
  not documented as verified. If passthrough is ignored, the `always` route fires after the next customer message.

- 2026-10-10 16:55 — **Builder LLM stays on OpenAI (recommendation; the user asked about Freya).** The Freya public API
  (96 paths) has no completion endpoint. Using it would mean running our prompts through a helper workflow over
  `/chat/message`. Agent `llmConfig.provider/model` are free strings with no enum and no models endpoint, so we would be
  guessing (and probing). `llmConfig.maxTokens` is capped at 4000, while our consolidate and extract outputs are
  3.2–4.6k tokens. The kit warns that long chat turns can return 504. The Freya credits are needed for simulations:
  200 → 181.3 credits after the whole day (~0.9 credits per 10-case 3-rep run).

- 2026-10-10 18:25 — **Generalisation audit (6 auditors + critic; 81 findings, 76 with executed evidence; the full
  result is in the scratchpad audit_result.json) → fixes for the score-relevant ones.**
  - Fixed:
    - F72: the build never aborts on an unrepairable spec. It deploys the best schema-valid spec with UNRESOLVED
      warnings.
    - F17/F41/F58/F20: the notes route uses our slot ids, with a linear expansion.
    - F01/F02/F62: the identity gate and answer fields must be non-empty booleans.
    - F32/F33/F36: a build-time date self-test runs the generated code over 42+ days and every holiday ±1, inside
      the repair loop. It caught variant-r's `!=` attempt-1 bug.
    - F04/F31/F61: a combined callback field uses the API's own format text.
    - F03: third_party gets the "who answered" endings.
    - F05: API field descriptions are kept.
    - F09/F56: a renamed customer-id field is resolved generically.
    - F46/F64/F71/F74: the note-reason vs close-reason rows are checked.
    - F77/F79/F80: model fallback on 429/5xx and on missing json_schema support; failed calls are traced with
      their model; tolerant decoding; redacted traceback.
  - **Deliberately not done:**
    - F48 (a fallback close outcome in the ev nodes). Writing the ev row's reason would leak into a finalize that
      chooses a reasonless row (promise + "refused"), and the outcome-only version helps only when the ev sandbox
      run succeeds while finalize fails, which is rare in a burst.
  - **Deferred:**
    - F15/F16: percentage or fixed floors and other attempt amounts. These need a schema change across all
      fixtures.
    - F57: extra required fields on engine-run tools; low plausibility.
    - The sandbox-hook reduction: weighed and recorded in the Observations.

- 2026-10-10 16:40 — **`kit/` updated to the official kit v3.** Only README.md and examples/ differ from v1 (see
  the Observations, 16:30), so behaviour and every test fixture are unchanged. `kit/` keeps mirroring the official zip
  byte for byte. `test_kit_example_agent_passes` now checks `examples/base-agent.json`, and `make baseline` deploys
  that example agent.
- 2026-10-10 16:40 — **No node layout from the builder.** The API rejects `nodePositions` in the definition and
  documents no other way to send it. A layout module was written and tested, then removed (dead code). On the
  dashboard, ⋮ → Organize gives the readable view. The organisers load our exported JSON, so they get their own
  editor's layout either way.

## Score log

| Time (Istanbul) | Git ref | Change | Brief | Reps | Passed / N | Workflow / agent id | Build time | Notes |
|---|---|---|---|---|---|---|---|---|
| 10-10 14:07 | fc120f9 | kit minimal_builder (baseline) | A | 1 | 6 / 10 | e2f7b97e / 23c6c141 | <1 min | fails PUB-02, 03, 07, 09 (see Observations). `runs/baseline-minimal-A.json` |
| 10-10 14:08 | 05eb2db | kit minimal_builder (baseline), briefs A+B | B | 1 | 1 / 3 | aab4bc00 / 6afab2aa | <1 min | PUB-12: persuasion attempts per product; PUB-13: loan recorded 21 Oct instead of its 23 Oct deadline (date arithmetic again). `runs/baseline-minimal-B.json` |
| 10-10 15:27 | 5390bb5 | design v1, FIXTURE spec (renderer only, no LLM) | A | 1 | **10 / 10** | 349752be / f0354c17 | 3 s | all 4 baseline failure classes gone; median slowest turn 3 s. `runs/dev/a-fixture-r1.json` |
| 10-10 15:40 | 5390bb5 | design v1, FIXTURE spec | A | 3 | **8 / 10** | 349752be / f0354c17 | 3 s | PUB-07 0/3: model offered the deadline for a holiday inside the window (facts were right; rule misapplied). PUB-10 1/3: judge flagged 'this call is recorded' in the opening as 'recorded before success'. `runs/dev/a-fixture-r3.json` |
| 10-10 15:43 | 78994a2 | v2: named-date offers in code, "we are recording" opening; FIXTURE spec | A | 3 | **9 / 10** | 349752be / f0354c17 | 3 s | PUB-01: sandbox output truncation, then a "One moment please" loop until max_turns. `runs/dev/a-fixture-v2-r3.json` (backfilled 16:20) |
| 10-10 15:45 | 78994a2 | v2, LLM spec | A | 3 | **8 / 10** | 81c14d7a / c6a57c76 | ~2 min | PUB-03 2/3: a third wrong identity answer inside a complaint was never verified. PUB-09 2/3: sandbox stall. `runs/dev/a-llm-v2-r3.json` (backfilled) |
| 10-10 15:49 | 78994a2 | v2, LLM spec, briefs A+B | B | 3 | **2 / 3** | f8f9b203 / b867b809 | ~2 min | PUB-12 1/3: the floor was offered after the last allowed attempt was refused. `runs/dev/ab-llm-v2-r3.json` (backfilled) |
| 10-10 16:07 | 90b737d | 6393c16 sandbox hardening + PUB-03/PUB-12 fixes; FIXTURE spec | A | 3 | **10 / 10** | 349752be / f0354c17 | 4 s (`--spec`) | simulation 312 s. `runs/dev/fixA-r3-90b737d.json` |
| 10-10 16:11 | 90b737d | same; LLM spec | A | 3 | **10 / 10** | 81c14d7a / c6a57c76 | 5 s (`--spec`) | simulation 250 s. `runs/dev/llmA-r3-90b737d.json` |
| 10-10 16:14 | 90b737d | same; LLM spec, briefs A+B | B | 3 | **2 / 3** | f8f9b203 / b867b809 | 4 s (`--spec`) | PUB-12 **0/3**: 2 reps offered the floor after the car loan's only attempt (early band), the same as before the fix; 1 rep made no attempt at all. Facts were correct. Fixed generically in e186247 (ATTEMPTS procedure). `runs/dev/abB-r3-90b737d.json` |
| 10-10 16:20 | 90b737d | same A+B agent on Brief A | A | 3 | **8 / 10** | f8f9b203 / b867b809 | 4 s | PUB-05 0/3: goodbye before add_note, then empty replies, no close_call (fixed in d46b807). The hardship note itself is right for an A+B agent (Brief B rule 8) but not for the A case. PUB-06 2/3: floor offered twice, "rest stays overdue" not said. `runs/dev/abA-r3-90b737d.json` |
| 10-10 16:25 | fe1d7ef | **raw-material** brief `tests/fixtures/briefs/raw-a.md` (Brief A as e-mail + policy + amending memo + code list), full LLM build | A | 3 | **10 / 10** | 7286c0bd / eb321c47 | 109 s, 2 model calls | every rep 10/10 (83/115/95 s). The consolidation applied all 5 memo amendments. `runs/dev/rawA-r3-fe1d7ef.json` |
| 10-10 16:29 | d46b807 | ATTEMPTS procedure + notes-before-goodbye wording | B | 3 | **1 / 3** | f8f9b203 / b867b809 | 4 s | PUB-12 1/3 (rep 2: goodbye with the notes, then empty replies, no close_call; rep 3: 2 offers on the early-band car loan). PUB-11 2/3 (rep 3 recorded the deadline instead of the agreed Friday for p1/p2). `runs/dev/abB-r3-d46b807.json` |
| 10-10 16:36 | d46b807 | same A+B agent | A | 3 | **9 / 10** | f8f9b203 / b867b809 | 4 s | PUB-05 0/3: the same goodbye-with-note stall, so the wording fix did not work (fixed structurally in 92b83b5). `runs/dev/abA-r3-d46b807.json` |
| 10-10 16:44 | d46b807 | LLM spec | A | 3 | (2 / 10) **invalid** | 81c14d7a / c6a57c76 | 4 s | reps 1 and 2 were 10/10. Rep 3: the platform went silent after the first customer turn in 8 calls; from 13:41 UTC the chat route returned 503 for every workflow. Re-run needed. `runs/dev/llmA-r3-d46b807.json` |
| 10-10 16:48 | d46b807 | extra B cases (`tests/fixtures/cases/extra-b.json`) | B+ | 3 | (0 / 3) **invalid** | f8f9b203 / b867b809 | | the platform outage: no agent turn after the first customer message. Re-run needed. |
| 10-10 17:19 | 1bc0c1d | notes-done route + wrap_up (llm entry), OFFER PLAN, DATES | A, PUB-05 only (A+B agent) | 3 | 2/3 reps | f8f9b203 / b867b809 | 13 s | the stall is gone: rep 3 reached close_call through wrap_up. But (a) finalize read no note reason (key `_args.arg_reason`), so it closed as refused instead of hardship (fixed in 8ccd652), and (b) wrap_up's llm line was blocked and the platform said "Bir saniye lütfen." (replaced by ev_notes in 78936ae). Reps 1–2: the model chose the hardship ending itself, with no note. `runs/dev/abA05-r3-1bc0c1d.json` |
| 10-10 17:25 | 1bc0c1d | same | B | 3 | 0 / 3 (reps 2–3: **3/3**) | f8f9b203 / b867b809 | 13 s | rep 1 (14:19 UTC, 5 min after the outage) was the platform: setup 6.8 s, verify 8–11 s, account_facts 11 s, then silence or repeated verify system errors. Reps 2–3 all passed, PUB-12 included (OFFER PLAN + notes route). `runs/dev/abB-r3-1bc0c1d.json` |
| 10-10 17:33 | 52b947c | ev_notes (fixed closing) + finalize arg_ key + OFFER PLAN + DATES | A, PUB-05 only (A+B agent) | 3 | 0 / 3 (artefact + platform) | f8f9b203 / b867b809 | 4 s | reps 1 and 3: the outcome is correct (no_promise/hardship, so the finalize fix works), there was no conversation failure, and the closing line was spoken. They fail only because the Brief A case expects no note while Brief B requires one. Rep 2: sandbox unreachable (`snekbox-svc … Name or service not known`), so every verify errored. `runs/dev/abA05-r3-52b947c.json` |
| 10-10 17:38 | 52b947c | same | B | 3 | 0 / 3 (rep 3: **3/3**) | f8f9b203 / b867b809 | 4 s | every failed call in reps 1–2 has `Failed to reach snekbox` / `Connection reset by peer` errors (14:33–14:36 UTC). A hook failure makes the tool call an error even though the bank recorded it, so the model retried and the ledger got duplicate notes. Rep 3, with a working sandbox, was 3/3. `runs/dev/abB-r3-52b947c.json` |
| 10-10 17:49 | 52b947c | LLM spec (dev-a-llm v6) | A | 3 | (3 / 10) reps 1–2: **10/10 and 10/10** | 81c14d7a / c6a57c76 | 4 s | rep 3 (14:47–14:49 UTC): all 7 failures have `Failed to reach snekbox` errors (sandbox burst). With a working sandbox: 20/20 calls. **Handed to the user for dashboard and voice feedback; not redeployed since.** `runs/dev/llmA-r3-52b947c.json` |
| 10-10 17:57 | 52b947c + 7d075ac deploy | A+B agent (v7) on Brief A | A | 3 | 3 / 10 | f8f9b203 / b867b809 | 4 s | rep 1: PUB-01/04/08/09 sandbox errors. Artefact: PUB-05 hardship note (Brief B rule). Real: PUB-07 rep 1 recorded the deadline 2 Nov for "Monday the 26th" (a holiday, should be 27 Oct); PUB-06 rep 3 floor offered for today, then again for Friday (fixed generically in 54e094a: no "today" re-ask). `runs/dev/abA-r3-52b947c.json` |
| 10-10 18:29 | 19664c6 | style fixes (fragments, pieces, questions back, sympathy, period dates) | A talkative (dev-a-llm2) | 1 | **9 / 10** (was 6/10 at 52b947c) | 7cfc34a8 / 2485fc27 | 3 s | PUB-04: a "Please go on." loop on repeated fragments (fixed in a1499a8). `runs/dev/style/a2-talkative-r1-19664c6.json` |
| 10-10 18:30 | 19664c6 | same | B talkative (dev-ab-llm v8) | 1 | **3 / 3** (was 2/3) | f8f9b203 / b867b809 | 5 s | `runs/dev/style/ab-talkative-r1-19664c6.json` |
| 10-10 18:31 | 19664c6 | same | A pieces | 1 | **10 / 10** (was 8/10) | 7cfc34a8 / 2485fc27 | 3 s | `runs/dev/style/a2-pieces-r1-19664c6.json` |
| 10-10 18:32 | 19664c6 | same | B pieces | 1 | **3 / 3** (was 2/3) | f8f9b203 / b867b809 | 5 s | after this, the mock bank failed (1101): the asks_back, in_words and 3-rep runs never ran |
| 10-10 19:05 | 276302f | A LLM spec + a1499a8 bounded "Please go on." (dev-a-llm2 v2) | A talkative | 1 | **6 / 10**, 0 platform errors | 7cfc34a8 / 2485fc27 | 4 s | PUB-07: "Yes, I confirm. I'm just looking" was cut off, the yes was ignored, the read-back re-asked until the customer hung up. PUB-06: floor offered 4 times (the repeat rule), "this Friday" = 17 Oct. PUB-05: support offered twice. PUB-02: 11 cut-offs in 30 s hit the third_party cap of 12. All fixed in 557161d except the date slip. `runs/dev/style/calls-276302f/` |
| 10-10 20:09 | 676e9df | A spec, **3 product slots**, gap fixes 1-6 (dev-a-llm2 v3); **styled cases** (`styled-a.json`: each case one of the 5 styles) | A | 3 | **7 / 10** (reps 9, 7, 9) | 7cfc34a8 / 2485fc27 | 4 s | PUB-07 0/3-ish (r1, r2; pieces): "Monday the." + "26th." got the after-deadline answer 2 Nov, facts were right (fixed 96c37ad: join date/amount parts). PUB-06 1/3 (talkative): floor offered for "today" then again on attempt 1's date; r3 also "this Friday" = 17 Oct (a 2025 Friday) and a full-amount attempt after "too much"; r2 a 20+ cut-off loop (fixed 35c030a: floor line in FACTS, short-answer loop breaker, weekday from the table). PUB-09 r2: **simulator** (customer hung up 7 s in, no words). PUB-02 talkative 3/3 and PUB-09 asks_back 2/3 show the 557161d caps and direct-transfer fixes holding. `runs/dev/r3/styledA-a2-676e9df.json` |
| 10-10 20:16 | 676e9df | A+B spec (dev-ab-llm v10), styled `styled-b.json` | B | 3 | **2 / 3** (reps 2, 2, 3) | f8f9b203 / b867b809 | 4 s | PUB-12 1/3: r1 corrects style, the judge wanted the phone question re-asked, the agent said "Please go on."; r2 one attempt too many/few on the car loan. `runs/dev/r3/styledB-ab-676e9df.json` |
| 10-10 20:22 | 676e9df | same, styled `styled-extra-b.json` | B | 3 | **1 / 3** (reps 1, 2, 2) | f8f9b203 / b867b809 | 4 s | PUB-12 0/3 (paid + disputed + refused): paid sentence missing, "today" re-asked for the car loan, all three noted at once without the car-loan attempt. PUB-13 r1: "I paid both" took the paid ending with **no notes**. Fixed in e233cb8 (note rows leave negotiate; NOTES does the ending's duty first). |
| 10-10 20:28 | 676e9df | same, styled `styled-ab-a.json` (Brief A cases, A+B ledgers) | A | 3 | **5 / 10** (reps 7, 7, 7) | f8f9b203 / b867b809 | 4 s | PUB-08 0/3 and PUB-05 r1: paid / hardship ending with no note (fixed e233cb8). PUB-07 0/3 (asks_back): "Monday the 26th" -> 2 Nov; with styledA, 5 of 6 PUB-07 calls on 3-slot agents. The 1- vs 3-slot facts differ only by two 'not in use' lines: the model pairs weekdays from 2025 (fixed a3e6c77: EVERY DAY weeks in the DATE TABLE). PUB-06 r3: floor without 'the rest stays overdue'. PUB-04 r2: customer ended during identity (to check). `runs/dev/r3/styledABA-ab-676e9df.json` |
| 10-10 21:00 | a8b70ea | A spec, 3 slots (dev-a-llm2 v5), styled `styled-a.json` | A | 3 | **7 / 10** (reps 10, 8, 8) | 7cfc34a8 / 2485fc27 | 9 s | Fixed vs 676e9df: no cut-off loops, floor once, PUB-03 corrects. PUB-07 1/3 (pieces): r2 the **simulator** said "26 August" (agent offered the latest date: defensible), r3 "Monday the."+"26th." -> 2 Nov again (open; the deadline is also a Monday). PUB-06 r3: **sandbox output failure** ("did not return a parseable result" x40 on verify_identity) with the 1920-char table of a3e6c77: reverted in bd944df. PUB-03 r2: **simulator**: the second date of birth arrived cut off 4 times in a row, never complete. `runs/dev/r3/styledA-a2-a8b70ea.json` |
| 10-10 21:10 | a8b70ea | A+B spec (dev-ab-llm v12), styled `styled-b.json` | B | 3 | **2 / 3** (reps 2, 3, 3) | f8f9b203 / b867b809 | 9 s | PUB-12 r1 only: **script/style conflict**: corrects style said "four four zero one. No, sorry," then "four four one zero"; the agent waited and verified the correction, the judge wanted the phone question re-asked after a wrong answer (same as 676e9df r1). The car-loan attempt count of 676e9df r2 did not recur. `runs/dev/r3/styledB-ab-a8b70ea.json` |
