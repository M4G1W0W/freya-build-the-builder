# Engine-fixes log (11 Oct 2026; engine-fixes chat)

Brief: `docs/plans/2026-10-11-engine-fixes-brief.md`. Branch `cand-eng` (worktree
`<scratchpad>/wt-eng`, off `cand-final.1` = ca80d52). No simulation, run_cases, deploy or non-`--dry`
build was run by this chat. `<scratchpad>` = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/0ff87ea7-15f5-4256-b709-1c128c353294/scratchpad`.

## Hand-off: `cand-eng.2` = 17eddb0 (items 1 + 2), tagged 10:45 UTC

Commits on top of cand-final.1: 6c80c5d (item 1, tag cand-eng.1), 0267b60 + 17eddb0 (item 2).
Tests: lint clean, **841 passed** (cand-final.1: 820). Each fix has regression tests that fail on
the old code (item 1: 17 fail on cand-final.1 source).

**Item 1 (HIGH), all-at-once `verify_identity`.** Files: `spec.py` (new `identity_all_at_once`: every
identity question key is a verify_identity request field; `check_spec` then skips the
question/answer/answer_ok fields and checks that every required answer field has a question),
`render.py` (`_per_answer` uses it; the all-at-once tool gets per-question field descriptions instead
of "Which security question was answered."), `hooks.py` (`verify_post(..., all_at_once=True)`: no
one-answer flag, so `ok=true` can never read as "Correct"; a failed check says "at least one answer is
wrong", names the answers in a response list of question keys, and asks again then re-sends every
answer), `pipeline.py` (extraction prompt: for an all-at-once tool each key = its request field and
question/answer/answer_ok fields = ""). Evidence: fresh `--dry` extraction of p3b at cand-eng.1 now
gives question/answer/answer_ok = "" and passes spec check in round 1 (the rehearsal needed 2 repair
rounds and invented the mapping); the identity step says "(field date_of_birth; ...)" and "CALL
verify_identity once with all of them"; fresh p1 (per-answer) unchanged in shape, round 1 pass.

**Item 2 (HIGH), a brief's own "too much" rule.** New spec field `too_much {offer: attempt_1|separate,
date_expr}` (`spec.py`, extraction prompt in `pipeline.py`). `separate` (brief says the floor offer
after "too much" is NOT a persuasion attempt): FACTS (`sandbox/facts.py`) say "offer exactly the floor
X on <its date>, once; this offer is NOT a persuasion attempt: every listed attempt stays available",
the OFFER PLAN names that offer first, and the negotiate ATTEMPTS clause (`render.py`) says it is not one
of the attempts. `attempt_1`, or a spec without the field (all saved specs), keeps today's text and
code-node CONFIG (`codegen.py` adds `fn_too_much`/`too_much_separate` only for `separate`). p2 on Thu
29 Oct: the floor 120.00 on **Mon 2026-11-02**, both attempts kept (the rehearsal expected exactly
this). Fresh `--dry` extractions at 0267b60: Brief A, A+B (ab-single.md) and raw-A all read
`attempt_1`; p2 reads `separate` + `next_business_day(today)`. All 4 built ok (raw-A needed one
repair round for an unrelated attempt-1 weekend date check; that check exists in cand-final.1).

**Render scope vs cand-final.1** (`--dry --spec`, no network; script `<scratchpad>/scope/render_all.sh`):
- `runs/dev/spec-a-llm.json` + brief-a, `runs/dev/spec-ab-llm-c45758f.json` + briefs a,b,
  `runs/dev/r4/spec-raw-w.json` + raw-a.md: **all prompt text, tool definitions and hooks
  byte-identical**. Only the three code nodes (`setup`, `account_facts`, `finalize`
  `pre_actions[0]...code.default`) change, because they embed the shared `sandbox/facts.py` source.
  Their **output is identical**: the old and new account_facts + setup code were run over 8000 states per
  spec (40 days x 2 times x every product type x 11 days-late values x 3 amounts) and give the same
  variables (sha256 equal for all three specs; `<scratchpad>/scope/facts_equiv.py`).
- p3/p3b: identity task, verify_identity description, its two field descriptions and its
  post_process_code change (intended). p1, p2 (saved specs): code nodes only, as above.

**Measurement request (sim chat).** For A and A+B the deployed behaviour should be the same as
cand-final.1 (identical prompts, identical FACTS output), so this is a regression check, not a new
A/B arm: one fresh build of cand-eng.2 for A (and A+B if a slot is free), then the cand-final.1
validation set at 1 rep (or whatever the 12:30 validation runs). If any case differs from
cand-final.1 it is noise or a fresh-extraction difference, not these fixes. Items 1 and 2 are only
observable on the perturbed briefs (p3b/p2), which have no case files: no simulation needed for them.
No trace line the RUNBOOK greps for changed.

## Next (in progress)
- `cand-eng.3`: item-1 review fixes (a 3-lens adversarial review of cand-eng.1, 13 agents: 2 MED + 5
  LOW confirmed; all in the all-at-once corner, none touches A/B) and item 4 ("this <weekday>" as a
  spec field `calendar.this_weekday`, default today's meaning).
