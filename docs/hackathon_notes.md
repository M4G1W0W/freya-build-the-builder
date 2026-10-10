# Hackathon notes — YC "Build the Builder" (Freya)

**Official source (pre-kit):** <https://www.freyavoice.ai/hackathon>, saved as
`docs/reference/hackathon_page.md`, with the 13 practice cases in
`docs/reference/hackathon_practice_cases.json`. The kit (emailed at the start) supersedes both.
Event listing: <https://events.ycombinator.com/AI-FDE-Build-the-Builder26>.

> **Update 2026-10-10 ~14:30 Istanbul.** The page changed at kickoff. The kit is now a download
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

## Decision log

_One entry per major decision: time, decision, alternatives, reason, evidence._

- 2026-10-10 00:50 — Prep: Python 3.12 + `uv`, src-layout package `freya_builder`, pytest + ruff only.
  Reason: lightweight and reproducible (`uv.lock`), no framework lock-in before reading the rules.
  The kit's `freya.py` is stdlib-only, so this stays compatible.

## Score log

| Time (Istanbul) | Git ref | Change | Brief | Reps | Passed / N | Workflow / agent id | Build time | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
