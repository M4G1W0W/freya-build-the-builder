# Brief for the ENGINE-FIXES chat (11 Oct 2026, written 10:30 UTC by the simulation chat)

You fix the builder ("the engine"). A separate chat owns **all simulations and deploys**. Read `CLAUDE.md`, then this
file, then `docs/plans/2026-10-11-overnight-report.md` (top handoff + event log) for context. Check `date -u` first.

## Deadlines (UTC, Sunday 11 Oct)
- **12:00**: no more candidate changes (the plan's rule; the user may move it). **12:30**: final validation runs (sim chat).
- **14:30**: RUNBOOK rehearsal. **15:30**: freeze, tag `freeze-final`. **17:00**: hidden briefs open; after that ONLY
  generic bug fixes, and nothing from a hidden brief may ever be written into the builder (CLAUDE.md hard rule).
- Hard limits: the builder must finish in 30 min per brief; it must stay generic (CLAUDE.md rule 11: no Brief A/B
  values, names, dates, enums in the builder); never invent bank policy.

## Division of work (binding)
- **You do NOT run simulations, run_cases, or deploys** (no `builder/build.py` without `--dry`), and you do not touch
  Freya slots. Use unit tests and `--dry` builds (they call only the builder LLM; `--dry` returns before any Freya call).
- **Git:** work only in your own worktree on your own branch, created from `cand-final.1`:
  `git worktree add <your-scratchpad>/wt-eng -b cand-eng cand-final.1`, then symlink `.env` and `.freya-agents.json`
  from the main tree into it. Do not commit on `main`, `cand-final`, `cand-id*`, `cand-idw`, `cand-retry`, `cand-g1`.
  Do not edit `docs/WORKING_STATE.md` or `docs/plans/2026-10-11-overnight-report.md` (the sim chat owns them). Write
  your log/decisions to `docs/plans/2026-10-11-engine-fixes-log.md` (commit it on `main` with that explicit path only;
  on an `index.lock`, wait and retry).
- **Hand-off for measurement:** when a fix is ready, tag it (`cand-eng.N`), and add to your log: the tag, the commit,
  what changed (files), the test result, the render-scope result (which rendered paths change vs `cand-final.1` for
  `runs/dev/spec-a-llm.json` + brief-a, `runs/dev/spec-ab-llm-c45758f.json` + briefs a,b, `runs/dev/r4/spec-raw-w.json`
  + `tests/fixtures/briefs/raw-a.md`), and what the sim chat should measure (cases x styles x reps). The user relays it.
- Before every commit: `uv run ruff format --check src tests && uv run ruff check src tests && uv run pytest -q`
  (never `make verify`; it reformats files owned by others). Each bug gets a regression test first.

## Current candidate: `cand-final.1` = ca80d52 (not merged to main; merging is the user's decision)
G1 83f8263 (restored too-much FACTS line) + identity-stage fix v2 (`docs/proposals/2026-10-11-identity-fix-v2.md`) +
builder platform retries (deadline-aware, `src/freya_builder/platform.py`) + offer-wait fix
(`docs/proposals/2026-10-11-offer-wait-fix.md`) + precedence `ending_wins` + 2 guards (variant-c rule 47).
820 tests pass; fresh `--dry` extractions of A, single-file A+B, raw-A, variant-c, variant-r all build; fresh-clone
rehearsal ok. Measurements of these parts are running in the sim chat (identity A/B, offer-wait A/B, O4 precedence).

## Work items, by priority (evidence: `docs/reviews/2026-10-11-perturbed-rehearsal.md`; perturbed briefs and tool
APIs: `tests/fixtures/briefs/perturbed/`)
1. **HIGH: all-at-once `verify_identity`.** If the identity tool takes every answer in ONE call (no question/answer
   pair; e.g. fields `date_of_birth` + `phone_last4`), `check_spec` (src/freya_builder/spec.py ~:407-410, :425)
   demands `question_field`/`answer_field`/`answer_ok_field`, so the repair round invents a per-answer mapping
   (question_field=date_of_birth, answer_field=phone_last4) and `render._per_answer` takes the per-answer branch: the
   agent sends the question key as the date of birth -> every verifiable case ends not_verified/failed; with
   answer_ok_field="ok" the post-hook also says "Correct" after a wrong answer. The identity fix already renders an
   all-at-once shape (T2-A/T9) when the tool has no answer field; make the spec schema/check accept that shape and
   make hooks (verify_pre ~:595-612, verify_post) handle it. Fixture: `tests/fixtures/briefs/perturbed/p3b-brightwater.md`
   + `p3-brightwater.openapi.json`. WORKING_STATE noted this as "gap 8b, deferred: speculative without the API shape".
2. **HIGH: a brief's own "too much" rule is overridden.** The builder hard-codes Brief A's reading ("a floor offer
   after too much is attempt 1, on attempt 1's date"): FACTS line in `src/freya_builder/sandbox/facts.py` ~:518-530
   ("IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH ... this IS attempt 1") and the ATTEMPTS clause in
   `render.py` ~:431. A brief that says "too much -> offer the floor on the next business day; this is not a
   persuasion attempt" (fixture `perturbed/p2-meridian.md`) gets the wrong promise date and loses an attempt. Needs a
   spec field (e.g. the too-much offer's amount, date expression, and whether it counts as an attempt) extracted from
   the brief, defaulting to today's behaviour when the brief is silent; keep Brief A's rendered text byte-identical.
3. **Brief B gap (consistent):** PUB-12 extra-B fails on every build and rep (F2 and G1): the agent asks again
   whether the customer can pay the car loan "today" after the opening question (Brief B rule 4: ask about today once,
   then product by product) and/or makes no persuasion attempt for the early-band car loan. Evidence: judge reasons in
   `runs/dev/r4/M2-ABv14-xb.log`, `runs/dev/r4/M5-ab1W-xb.log`; case `tests/fixtures/cases/styled-extra-b.json`
   (PUB-12) and `extra-b-rederived.json`.
4. **MED: "this <weekday>" meaning is fixed** in the DATE TABLE (`sandbox/facts.py` ~:256: "this Monday-to-Sunday
   week"). A brief that defines it as "the first such weekday after today" (fixture `perturbed/p1-calder.md`) gets a
   past date. Needs a spec field with today's meaning as default.
5. **LOW:** percentage floor uses float `round` (`facts.py` ~:454; 30% of 99.95 -> 29.98, below the real floor: use
   Decimal half-up or ceil to the cent, per the brief); the identity entry line can say "Please go on." instead of the
   first question (call 29041b61); a brief's pre-question sentence lands only in the stage_rules line at the bottom of
   the identity task; `hint_field="error"` with no hints makes verify_post quote error text as a hint; `--dry` stdout is
   block-buffered so the END line is glued to the JSON (flush before `trace.end`); the platform retry guard stops
   retries near the 30-min limit but a first attempt can still start after it.

## Not yours (already done or owned by the sim chat)
Identity fix, offer-wait fix, retries, precedence (all in cand-final); the stuck-simulation checker
(`scripts/run_cases_retry.py`); all measurements and deploys; the RUNBOOK (updated 377dabb; tell the sim chat if a fix
changes a trace line the RUNBOOK greps for).
