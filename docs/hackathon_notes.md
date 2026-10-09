# Hackathon notes — YC "Build the Builder" (Freya)

> Everything under "Official materials" must come from the official challenge text, starter kit
> or organiser announcements, with a source. Everything else is labelled as our own note.

## Logistics

| Item | Value |
|---|---|
| Event | Y Combinator — Build the Builder |
| Platform | Freya Voice AI — <https://docs.freyavoice.ai/>, dashboard <https://app.freyavoice.ai> |
| Format | Fully online |
| Start | 2026-10-10 13:00 Istanbul (UTC+3) = 10:00 UTC |
| End | 2026-10-11 23:00 Istanbul (UTC+3) = 20:00 UTC |
| Prize | Interview with Y Combinator |

## Official challenge text (as given before kickoff)

> "A bank wants to phone its customers who are late on a payment. You write a builder: a program
> that reads the bank's collections brief and creates a phone agent on Freya. We run that agent
> against simulated customers. Your score is the share of cases the agent handles correctly."

## Public event page (read 2026-10-10, before kickoff)

Source: <https://events.ycombinator.com/AI-FDE-Build-the-Builder26> (linked from freyavoice.ai).
These are paraphrased facts from the public page. They are **not** the official rules, which
come at kickoff.

- **Challenge framing.** The builder takes a new task and creates an agent for it. In the page's
  words, it "should turn a task description and the available tools into a working agent". Teams decide
  how it creates, tests and improves that agent.
- **Evaluation.** At the deadline the organisers give the builder **unseen tasks**. It creates an
  agent for each, with **no manual edits during evaluation**. The agents then run through the same
  benchmark simulations.
- **Ranking.** Based on the generated agents' performance across the final benchmark's tasks and
  test cases, under the same conditions for everyone. There are no pitches or presentation scores. Scoring rules,
  resource limits and tie-breakers are to be shared before building begins.
- **Schedule.** Day 1 covers challenge rules, development tasks, Freya platform setup, then building against a
  **practice benchmark**. Day 2 covers testing, submission, the final unseen benchmark and the leaderboard. Exact
  times go to accepted participants.
- **What to submit.** The builder, the exact code version, its dependencies and clear instructions
  for reproducing a run. They evaluate the agents it creates, not a hand-built agent.
- **Team size.** Solo or teams of up to 2. Participants use Freya's platform.
- **Pre-event preparation.** The page says the builder is built during the weekend. We found no explicit rule
  about preparation. Tonight we only set up tooling and read public docs; no builder logic was written.
- **Page metadata.** `starts_at` is 2026-10-10T10:00Z and `ends_at` is 2026-10-11T20:00Z, which is 13:00 → 23:00 Istanbul time and matches our notes.

What this implies for engineering (our reading, to confirm against the official rules):
the builder must run **unattended** and **reproducibly** (pinned Python + `uv.lock`, one documented
command). "Available tools" are part of the input, so wiring tools into the agent is likely
central. See `docs/freya_api_notes.md` §8: the tool `handler` format is undocumented.

## Official materials (fill in at kickoff)

- Challenge instructions: _TBD — link / file path_
- Starter kit: _TBD_
- Freya account / workspace / credentials process: _TBD_
- Submission requirements & deadline mechanics: _TBD_
- Rules on pre-event preparation, allowed tools, third-party LLMs: _TBD_

## Kickoff checklist (in order)

1. Read **all** official instructions and the starter kit end to end; save copies/links here.
2. Pin down the exact **input** (format of the bank's collections brief; one brief or many?).
3. Pin down the exact **output** (what the builder must produce/submit: agent id? workflow? code?).
4. Identify which Freya APIs/features are permitted or provided (keys, workspace, credits, limits).
5. Understand **how evaluation works**: who runs the simulated customers, what "handled correctly"
   means, how many cases, whether we get a local/dev evaluator or sample cases, run limits.
6. Identify the fastest route to a **valid submission**; submit a minimal valid version early.
7. Build the minimal working implementation.
8. Verify it end to end (brief → agent on Freya → evaluated conversation).
9. Build a regression suite from the official/sample cases and every failure found.
10. Improve the score through measured iteration.

## Questions to answer from the official materials

- [ ] Input: brief/task format, language(s), how many, are hidden tasks used for scoring?
- [ ] "Available tools": in what form are they given (Freya tool JSON, HTTP endpoints, integrations)?
      How must they be attached to the agent (`llmConfig.tools[].function.handler` is undocumented)?
- [ ] Practice benchmark: how do we run it, how often, and do its calls/results land in our workspace?
- [ ] May the builder itself call an external LLM? Which one, and whose key?
- [ ] Output: what exactly is submitted, and how/where?
- [ ] Does the builder run on our machine or on theirs (runtime limits, allowed deps, network, LLM keys)?
- [ ] Agent vs. workflow: is a specific Freya entity type required?
- [ ] Which Freya workspace/API key is used for scoring? Are credits limited?
- [ ] What does "handled correctly" mean (rubric, assertions, per-case pass/fail)?
- [ ] Are sample cases / personas / a scoring harness provided for local testing?
- [ ] Voice/language requirements (e.g. Turkish vs English)?
- [ ] Number of submissions allowed; is the last or best one scored?
- [ ] Is pre-event preparation restricted in any way? (We prepared only the environment and API notes.)

## Decision log

_One entry per major architectural decision: date/time, decision, alternatives, reason, evidence._

- 2026-10-10 — Prep: Python 3.12 + `uv`, src-layout package `freya_builder`, pytest + ruff only.
  Reason: lightweight, reproducible (`uv.lock`), no framework lock-in before reading the rules.

## Score log

| Time (Istanbul) | Git ref | Change | Eval set | Score | Notes |
|---|---|---|---|---|---|
| | | | | | |
