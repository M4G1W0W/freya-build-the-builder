# PROJECT OVERVIEW: read this first in every new session

This file describes the **whole project**. It is stable. The changing state (scores, open tasks, agent ids)
lives in `docs/WORKING_STATE.md`. Read that second. `CLAUDE.md` holds the binding rules and is auto-loaded.

## 1. What we are doing

- **Event:** Y Combinator "Build the Builder" hackathon on Freya Voice AI. It is online, solo, and the prize is a YC interview.
  - Official page: <https://www.freyavoice.ai/hackathon> (snapshot: `docs/reference/hackathon_page.md`).
  - Kit: <https://www.freyavoice.ai/hackathon/build-the-builder.zip>, saved **unmodified** in `kit/`. `kit/README.md` is the authority.
- **Task:** write a **builder**, a program that reads a bank's collections **brief** plus the bank's **tool API**
  (OpenAPI) and creates a **phone agent** on Freya. A phone agent is a **Freya workflow**: steps, prompts, tools, routes and
  code nodes. The organisers run it against simulated customers **in text, in English**.
- **We are NOT hand-building an agent.** The submission is the builder. Generated agents must never be edited by hand.

## 2. Timeline (Istanbul = UTC+3)

| When | What |
|---|---|
| Sat 10 Oct 10:00 UTC (13:00 Istanbul) | Start. Kit and key. Build against the 13 practice cases |
| **Sun 11 Oct 17:00 UTC (20:00 Istanbul)** | **Hidden briefs released** (2 briefs, each with its own tool API file) |
| **Sun 11 Oct 20:00 UTC (23:00 Istanbul)** | **Submission closes** |

The last 3 hours are only for **running the builder and fixing generic bugs**. Always check `date` (it is easy to misjudge elapsed time).

## 3. Scoring (what "good" means)

- **Pass conditions.** One case is one simulated customer. It passes only if all three hold:
  - **Ledger right:** the mock bank's records hold the correct outcome, promises, notes, callbacks and transfers.
  - **Policy followed:** judged from the transcript.
  - **Honest:** for example, the agent never says "recorded" before a tool succeeded. Judged from the transcript.
- **Final.** 2 hidden briefs × 30 customers = 60 cases. **Each case runs 3 times and must pass all 3.**
  Score = passed / 60. Consistency matters as much as average quality.
- **Tie-breaks:** (1) total promised amount on passed cases; (2) shorter builder build time (from the trace);
  (3) earlier submission.
- **The two hidden briefs.** One is a clean spec. The other is **raw bank material**: an e-mail, a policy extract,
  a memo that amends it, and a code list. They have other identity questions, limits, deadlines, outcome tables
  and calendars. **The 7 tool names stay the same, but their fields and allowed values can change.** Customers talk
  like people (split numbers, corrections, chatter, questions back, words). Calls happen on several calendar days.
  The call's date comes in the variable `now`.
- **Practice.** The 13 public cases (`kit/public-test-set.json`): 10 on Brief A, 3 on Brief B. They are scored by
  `kit/tools/run_cases.py`. Only **1 simulation** can run per workspace at a time; a 10-case run takes about 1.5–5 min.

## 4. Hard rules (break one and we are disqualified or lose points)

- **After Sun 17:00 UTC, NOTHING from a hidden brief may be written into the builder:** no rule, value, name, date or
  code. Only generic crash and bug fixes are allowed. A reviewer checks the commit.
- **Never hard-code practice Brief A/B values in `src/` or `builder/`.** `tests/test_no_brief_values.py` enforces this.
- **The phone agent may call only the kit's bank tool API.** Its model is fixed: `experimental-5` (`kit/freya.py` AGENT_LLM).
  Do not change it.
- **One Freya key per team.** Do not probe or load-test the platform. The workspace holds 200 workflows; update in place.
- **The builder must run unattended** in ≤ 30 min per brief, from one command, and print a **trace**: start and end time,
  every model call with model and purpose, the ids it created on Freya, and its self-test results. No secrets in the trace.
- **Submission:** a GitHub repo URL and commit (**the user still has to decide public vs private-with-access**). Exported
  workflows go in `submission/*.workflow.json` (`freya.export_workflow`). Traces go in `traces/*.log`. The run command
  is `python3 builder/build.py {brief_path} {tool_api_path}`. The organisers **re-run the top 10** and remove entries
  that score clearly lower, so the build must be reproducible.

## 5. Architecture (decided; details in `docs/design.md`)

**Facts in code, rules in the prompt.** The builder's pipeline is:
1. **LLM consolidate** (`pipeline.consolidate`): classify the brief as clean or raw, apply memo amendments, map code
   lists to API values. For clean briefs the original text is kept for the prompt.
2. **LLM extract** (`pipeline.extract_spec`): a strict **PolicySpec** (`spec.py` SPEC_SCHEMA). It is checked by
   `schema_problems` and `check_spec`, which cross-checks every outcome, queue, identity field and product field
   against the tool API. Up to 2 automatic repair rounds.
3. **Render** (`render.py`): generic code turns spec + tool API into the workflow. Every value comes from the spec and
   every tool shape from the API.
4. **Validate** locally (`validate.py`), then Freya dry run, then `freya.save_workflow` (create or update, then publish),
   then a chat smoke test, then optionally export.

**The workflow graph** (all built by `render.py`):

| Step | Kind | Role |
|---|---|---|
| `setup` | code | Calendar facts from `now`, sentinels |
| `opening` | conversation | Who answered (extraction enum), no tools |
| `third_party` | conversation | Callback only |
| `identity` | conversation | `verify_identity`; gate on the `all_verified` response field, both "true" and "True" |
| `load_account` | api_request | **Engine-run** `get_account` |
| `account_facts` | code | Per product: band, deadline, floor, attempt plan, valid window, and "IF THE CUSTOMER NAMES A DATE" offer lines |
| `negotiate` | conversation | Disclosure TTS; per-product tools `create_promise_p<k>` / `add_note_p<k>`, with `product_id` baked |
| `ev_<row>` | exit | The model says goodbye and fires `transition_to_ev_<row>` in the same message |
| `finalize` | code | Outcome from **what was actually recorded** (`close_precedence`) |
| `xfer` | api_request | Engine-run transfer |
| `close` | api_request | Engine-run `close_call` |
| `hang_up` | end_call | |

- **Endings before negotiation** (opening, third party, identity rows) close with **literal values, no code**: `ev_<row>` is
  an api_request, with `cl_<row>` after a transfer.
- **Negotiate rows** take the path `ev_<row>` (code, sets `end_event`) → `finalize` → `xfer`? → `close`.
- **Turn caps** route to `ev_<default row of that stage>`.

**Builder LLM:** OpenAI `gpt-6.1-sol`, with fallback chain `gpt-5.5`, then `gpt-5.4` (`llm.py`, stdlib urllib, strict
json_schema). The whole builder is **stdlib-only**, so `python3 builder/build.py` works from a fresh clone (Python 3.10+).

## 6. Verified platform facts (learned the hard way; trust these)

- **API access.** Freya runs at `https://staging-app.freyavoice.ai`, paths `/api/v2/...`. Requests need a browser-like
  User-Agent; `kit/freya.py` handles it. **There is no MCP**: use REST through `kit/freya.py`.
- **Saving.** `PUT /workflow` saves an **unpublished** version; `freya.save_workflow` publishes. Simulations run the
  published version.
- **Tool results.** These land in **flattened variables** `<tool or node>_response.data.<path>`. On an api_request node
  they are named after the **node**. A node-level `response_mapping` of a list did NOT work, so `sandbox/flatvars.collect_list`
  rebuilds lists from the flattened keys.
- **Booleans** arrive as strings "true" or "True". Test both.
- **Parallel calls race.** The model may fire several tools in one turn and they run in parallel (`close_call` raced the
  transfer). So `close_call`, `get_account` and `transfer_to_agent` are **never model-callable**; the engine runs them in order.
- **Closing pattern** (verified): the model says goodbye and fires the `is_tool_call` transition in the same message, then
  an api_request runs `close_call`, then `end_call`.
- **Post-hooks** (`post_process_code`) can add `what_to_do_next` to a result and the model follows it. They can write `vars`
  (the sticky `p<k>_recorded` flag).
- **The sandbox truncates output.** Every sandbox run (code node, pre-hook, post-hook) returns **ALL variables** as JSON,
  and the platform sometimes **truncates that output**. After the first failure, every later sandbox run in the call failed
  and the agent stalled. Mitigations are in place: a compact calendar, no pre-hooks, sandbox-free closes before
  negotiation, and a retry rule. **Keep variables small and sandbox runs few.**
- **Code-node rules:** no `{{` or `}}` in code (config is hex-encoded JSON), never raise, and only json, re and datetime.
  Code is minified at assembly (`sandbox/__init__.py`). Each node is about 31–35 KB, which works.
- **Judge sensitivity:**
  - **"this call is recorded" in the opening failed honesty checks.** The opening now says "we are recording this call"
    (`render.opening_line`).
  - **Do not invent dates.** The model misapplied rules even with correct facts, so offers for named dates are computed in
    code (`promise_window.non_business_day` and `after_max`).
- **Chat route.** `POST /api/v2/chat/message` gives quick text tests (`scripts/chat.py`, the builder's smoke test).

## 7. Evidence so far (details in the `docs/hackathon_notes.md` Score log and Observations)

- **Baseline.** The kit's minimal builder scored 6/10 on A and 1/3 on B.
- **Our design.** 10/10 on A in a single run. At 3 reps it has scored 8–9/10 on A. Remaining failures were sandbox
  truncation and two behaviour gaps that are being fixed.
- **Extraction generalises.** On the synthetic unseen briefs `tests/fixtures/briefs/variant-r` (raw material plus memo)
  and `variant-c` (fully perturbed), every typed field matches the answer keys (`experiments/exp04` and `exp05`).
- **Reproducibility.** Two independent extractions differed in 1 of 181 typed leaves (`exp06`).
- **Model choice.** All 8 OpenAI candidates scored 11/11 and were consistent (`exp02`, `exp03`). gpt-6.1-sol is used.

## 8. How to work (conventions)

- **Commands:**
  - Python: `.venv/bin/python` (system `python3` is 3.9 and too old).
  - Secrets: `source .env`. It holds FREYA_API_KEY, FREYA_API_URL, FREYA_BANK_TEAM_KEY, FREYA_WORKSPACE_ID,
    OPENAI_API_KEY, BUILDER_MODEL and BUILDER_MODEL_FALLBACKS. **Never print, log or commit them.**
  - Build: `.venv/bin/python builder/build.py <brief(s)> <tool_api.json> --slot NAME [--save-spec f] [--spec f (DEV: skip LLM)] [--export f]`
  - Score: `source .env && .venv/bin/python -u kit/tools/run_cases.py <agent_id> --brief A|B --reps 3 --out $PWD/runs/dev/x.json`
  - Inspect: `.venv/bin/python scripts/show_run.py runs/dev/x.json --calls` and `scripts/show_call.py <call_id>`
- **Before every commit:** `make verify` (format, lint, all tests). **When piping output use `set -o pipefail`**; piping
  through `tail` once hid failures. Commit small, with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Record results.** Every score goes in the `docs/hackathon_notes.md` Score log. Every decision goes in its Decision log.
  Every failure becomes a regression test.
- **Generic fixes only.** A fix must make sense for any brief of this kind. Read the failing transcript first.
- **Ultracode is usually on.** For substantive tasks use the Workflow tool (parallel agents plus adversarial review). The
  user wants autonomy on technical decisions; ask only for genuine user decisions (keys, publishing, repo visibility).
- **Do not push** to any remote without the user's explicit go-ahead.

## 9. Key files

| Path | What |
|---|---|
| `CLAUDE.md` | Binding rules and kit facts (auto-loaded) |
| `docs/design.md` | Adopted architecture, §9 implementation contract (variable and node names) |
| `docs/hackathon_notes.md` | Rules digest, Observations (verified facts), Decision log, Score log |
| `docs/WORKING_STATE.md` | **Current status, open tasks, agent ids (update at every context save)** |
| `src/freya_builder/` | `cli`, `pipeline`, `spec`, `expr`, `render`, `codegen`, `hooks`, `nodes`, `toolapi`, `validate`, `llm`, `trace`, `platform` |
| `src/freya_builder/sandbox/` | Code that runs inside Freya code nodes: `calendar_core`, `policy_helpers`, `flatvars`, `facts` |
| `tests/fixtures/spec_a.json` | Hand-written Brief A spec (test-only, dev `--spec`) |
| `tests/fixtures/briefs/` | Synthetic unseen briefs with answer keys |
| `experiments/` | exp01 (platform mechanics), exp02/03 (model choice), exp04/05 (extraction vs truth), exp06 (reproducibility) |
| `kit/` | The official kit, unmodified (`freya.py`, briefs, docs, `run_cases.py`) |
