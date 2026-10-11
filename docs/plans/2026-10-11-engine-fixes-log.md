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

**Measurement request (sim chat), CORRECTED 11:05 UTC (user):** promotion of any cand-eng tag needs the
same strict 3/3 fresh-build validation as any candidate; a 1-rep run is only a smoke test. For A and A+B
the rendered prompts are identical to cand-final.1 and FACTS output is identical on the states tested,
but that is a prediction, not a measurement: any case that differs from cand-final.1 must be
investigated (transcript + FACTS of that call), not called noise. Items 1 and 2 are only observable on
perturbed briefs, and no case files exist for them: **they are unmeasured** (see "Proposed cases").
No trace line the RUNBOOK greps for changed.

## Hand-off: `cand-eng.3` = 57e6e66 (items 1, 2, 4, 5 + review fixes; supersedes cand-eng.2), tagged ~10:55 UTC

Commits after cand-eng.2: fd705de (item 4), d54a850 (item-1 review fixes), 57e6e66 (item 5).
Tests: lint clean, **857 passed**. Every fix has a regression test that fails on the old code.

- **Item 4 (MED), "this <weekday>".** New spec field `calendar.this_weekday {current_week |
  next_occurrence}` (`spec.py`, prompt in `pipeline.py`); the DATE TABLE (`sandbox/facts.py`
  `date_table`) prints "this <weekday> (the first such weekday after today): ..." only for
  `next_occurrence`; `codegen._calendar` adds the CONFIG key only then. p1 said on Fri 23 Oct: "this
  Wednesday" = 2026-10-28 (was 2026-10-21, a past date).
- **Item-1 review fixes** (3-lens adversarial review of cand-eng.1, 13 agents; 2 MED + 5 LOW
  reproduced, all in the all-at-once corner): only ONE response list whose name says wrong
  (wrong/incorrect/fail/invalid/mismatch) and that holds only question keys names wrong answers (a
  `matched_fields` list was read as wrong); otherwise the agent asks again for what the brief says
  (else every answer). Keys match request fields ignoring case (check_spec then asks for the exact
  name); a question field whose enum lists the keys stays per-answer; a required enum field is a
  setting, not a missing question; a per-answer spec whose keys are request fields (the invented P3
  mapping with other key spellings), or empty question/answer fields with non-field keys, now get one
  clear checker message (they passed silently or contradicted themselves).
- **Item 5 (LOW), three of six parts:** percentage floor in whole cents, half up (30% of 99.95 = 29.99,
  was 29.98; facts.py has no new import); verify_post reads no hint field when the brief lists no hint
  values (p1 hint_field "error" quoted error text as a hint); `cli.run` flushes stdout before the END
  line. Not done: identity entry "Please go on." (call 29041b61), pre-question sentence placement,
  first retry after the 30-min guard (need transcripts or platform work).

**check_spec on every saved spec** (39 specs under runs/dev + P1-P3b + variant fixtures, each with its
API): the same problems as cand-final.1 for every spec; only the wording of two existing messages gained
the all-at-once hint. No saved spec gets a new repair round.

**Render scope vs cand-final.1** (same 3 required specs + p1-p3b): A, A+B, raw-A: prompts, tools and
hooks byte-identical; only the 3 code nodes (shared facts module) differ, with identical output over
8000 states per spec (re-run at 57e6e66: A, A+B, raw-A all EQUAL). p1: verify_identity post_process_code (hint fix)
+ code nodes. p2: code nodes only (saved spec has no too_much). p3/p3b: identity step + code nodes.

**Fresh `--dry` extractions at d54a850** (builder LLM only): A, p1, p3b, variant-c all pass spec check
in round 1. A: too_much attempt_1, this_weekday current_week (unchanged behaviour). p1: this_weekday
next_occurrence (correct). p3b: all-at-once (correct). variant-c: per-answer question/value (correct).

**Measurement request (sim chat), CORRECTED 11:05 UTC (user): measure cand-eng.3, not cand-eng.2.**
Promotion needs strict 3/3 on fresh builds (1 rep = smoke test only). Expected for A and A+B: the same
results as cand-final.1 (identical prompts, identical FACTS on the tested states); every difference is
to be investigated, not dismissed as noise. Items 1, 2, 4 and the floor rounding are **unmeasured**
until the proposed cases below exist and run. No trace line the RUNBOOK greps for changed (the END line is unchanged; it now follows a flushed
stdout).

## Review findings after cand-eng.3 (user request 11:05 UTC: report all, before finalizing)

Review 2 (`wf_b03ec5b4-51e`, 3 lenses + verifiers, on d54a850: items 2 and 4 and the identity review
fixes). Verifiers reproduced every MED by running the generated code. None affects A, A+B or raw-A,
because all three read `too_much` = attempt_1 and `this_weekday` = current_week. Fixed in c737844:

| Sev | Finding | Status |
|---|---|---|
| MED | separate: the too-much floor date equals attempt 1's date on every Thursday (next business day = Friday) and before a Friday holiday, so after a refusal the plan repeats the refused offer | FIXED: the TOO MUCH line marks it ("attempt N below offers the same floor on the same date: if the customer refused this offer, follow the brief's rules on refused offers"). The brief's own rules decide; the engine does not pick a reading |
| MED | separate with an empty date fell back to attempt 1's date (collision on every day; "on not available" in a 0-attempt band) | FIXED: check_spec problem "too_much.offer is 'separate' but date_expr is empty" (repair round); prompt no longer offers that default |
| MED | the date self-test never checked the too-much date; a past date had no mark | FIXED: past/after-deadline marks on the line; `datecheck` checks it like an attempt date |
| MED | attempt_1 mode drops a date the brief gives for the too-much offer ("offer the floor, payable on the next business day, once", without "not an attempt") | **OPEN** (pre-existing in cand-final.1, same behaviour). A fix would let the LLM fill a date for Brief A too: not safe before the cutoff without fresh-build measurement |
| LOW | separate line appeared in mandatory-transfer bands | FIXED |
| LOW | separate line (unscoped) contradicted "after attempt 1 is refused: NO further offer" in a 1-attempt band | FIXED: scoped "before your first offer", as the attempt-1 line is |
| LOW | all-at-once required-field check skips every enum field, also an enum-typed answer field | OPEN (rare; an enum answer field would get no missing-question warning) |
| LOW | both question/answer fields empty on a per-answer API: the message points only to the all-at-once shape and skips answer_ok checks | OPEN (the repair round still gets a problem; wording only) |
| LOW | `_WRONG_ALL` name filter does not name wrong answers for unverified_fields, rejected_fields, errors, not_matched | OPEN by design: the fallback (ask what the brief says, else every answer) is always safe; widening it risks the MED that review 1 found |

Review 1 (`wf_dcf7f97f-cd8`, on cand-eng.1): 2 MED + 5 LOW reproduced, all fixed in d54a850 except
"a hint response hides other answers the bank marked wrong" (LOW, OPEN: the hint instruction comes from
the brief and wins) and "a per-answer API whose keys equal field names" (LOW, now guarded by the
selector-enum check).

## Tags for measurement (11:10 UTC). Promotion of either needs strict 3/3 on fresh builds

- **`cand-eng.4` = cfa4d9d** (branch `cand-eng-safe`) = cand-eng.3 + review-2 fixes (01b7a80) +
  fixtures (variant-e brief, 4 cases). Tests: 859 passed. Prompts for A, A+B, raw-A: byte-identical to
  cand-final.1 (code nodes differ only).
- **`cand-eng.5` = 27f5647** (branch `cand-eng`) = cand-eng.4 + item 3 (PUB-12 paragraph, 4006d5c).
  Tests: 861 passed. Same render scope.
- Single-product FACTS/setup output of both tags equals cand-final.1 for the saved A, A+B and raw-A specs
  (8000 states each, sha256 equal). The PUB-12 paragraph (cand-eng.5) only appears on multi-product
  accounts, which this check does not cover: it changes Brief B FACTS by design.

## Proposed behavioural cases (the new paths are UNMEASURED until these run)

`tests/fixtures/cases/eng-variant-e.json` (on both tags), for an agent built from
`tests/fixtures/briefs/variant-e.md` + `kit/tools/openapi.json`. variant-e is Brief A with 3 rules
changed: 22 ("this <weekday>" = first such weekday after today), 25 (floor = 35% of past due, half a
cent rounded up), 26 (too much: floor on the next business day, not a persuasion attempt). The mock
bank seeds a case's account by its public id, so each case reuses an existing account (now = Wed
2026-10-14):

| Case | Account | Path | Expected ledger (blind-derived, 2/2 + author agree) | cand-final.1 FACTS (computed) |
|---|---|---|---|---|
| ENG-E1 (PUB-01) | card 420.00, 6 days | too much -> separate offer | promise 147.00 on **2026-10-15** | floor on attempt 1's date 2026-10-16 |
| ENG-E2 (PUB-07) | loan 540.00, 5 days, 1 attempt | too much -> refuse -> attempt 1 | promise 189.00 on **2026-10-16** | too-much offer IS attempt 1 -> after refusal no offer left -> no promise |
| ENG-E3 (PUB-08) | card 180.00, 5 days | "this Monday" | promise 180.00 on **2026-10-19** | "this Monday" = 2026-10-12 (past) |
| ENG-E4 (PUB-06) | card 2125.10, 12 days, 2 attempts | refuse, refuse, attempt 2 = floor | promise **743.79** on 2026-10-23 | floor 743.78 (float round) |

All expected promises are outcome `promise`, no notes. Floors are above each account's own
minimum_payment/instalment_amount in case the mock checks those (unknown). Ambiguities the derivers
flagged: E2, whether attempt 1 (floor on Fri) "repeats" the refused floor offer on Thu (both said no:
different date); E1/E2, whether "too much" in reply to "can you pay today" is a flat refusal instead
of the rule-26 trigger (both said rule 26 applies). Suggested run: build variant-e (fresh) on the tag,
`run_cases.py <agent> --cases tests/fixtures/cases/eng-variant-e.json --reps 3`: 12 calls.
Fresh `--dry` extractions of variant-e at 27f5647 (3 runs): all pass spec check round 1 and all 3 read
too_much = separate + `next_business_day(today)`, this_weekday = next_occurrence, floor_percent 35 for
every type. The "cand-final.1" column is computed, not assumed: the account/setup code of cand-final.1
(ca80d52) and of cand-eng.4 was run on the r1 spec with each case's account (`<scratchpad>/scope/case_facts.py`):
cand-eng.4 FACTS give exactly the expected values (147.00 on 2026-10-15; 189.00 on 10-15 then attempt 1
on 10-16; "this <weekday> (the first such weekday after today): Mon 2026-10-19"; floor 743.79), cand-final.1
gives the right-hand column. FACTS being right does not show the agent follows them: only the run does.

**Identity all-at-once (item 1) cannot be measured by simulation:** the official mock's
`verify_identity` takes one answer per call (field/answer), and the agent may call only the kit's
tool API, so an all-at-once agent would only send bodies the mock rejects. It is covered by unit tests
(hooks executed on P3-shaped responses) and fresh `--dry` extractions (p3b x2), nothing more: it stays
unmeasured end to end.

## Item 3 (PUB-12), in cand-eng.5 only: a SEPARATE, riskier arm

Diagnosis (read-only agent over saved logs/transcripts; no transcripts were saved for the 6 M2/M5
calls, older ones in `runs/dev/r3/XB12*` show the same): PUB-12 extra-B ledger is right in all 6
calls; the conversation check fails. 5 of 5 judged reps show either (a) after the customer's no to
the opening question the agent asks "can you pay the car loan today?" and then makes attempt 1 (judge:
two offers), or (b) it takes the opening question as the car loan's "ONE offer only" and notes a
refusal without an offer. 1 rep was "analysis never arrived". The ATTEMPTS clause only prohibits the
re-ask; nothing says what the next words about each product are.

Change (`sandbox/facts.py` `account_main`, one paragraph after the OFFER PLAN, only when the account has
more than one product, an OFFER PLAN and a `first_ask_multi`): "AFTER THE OPENING QUESTION ("<the
brief's multi-product first ask>"): that question is not one of the offers above and uses no
attempt. If the customer does not agree to pay all of them today, go through the products one at a time
in the order above; for each product with no date or amount from the customer and no situation that a
brief rule handles without persuasion (such as already paid, a dispute or hardship), your next words
about it are its offer 1 in the OFFER PLAN (that amount on that date), if it has one, even after a firm
no to the opening question. Never ask about paying today again, not even for one product." No dates,
no brief values. Prompts unchanged (render scope: A, A+B, raw-A differ only in the 3 code nodes);
single-product FACTS are unchanged. Tests: **859 passed**.

Risk: the model may bundle several products' offers in one turn, or make an offer for a product the
customer already gave a date for; extra FACTS text has moved date choices before (PUB-07). The agent's
estimate: ~55% that PUB-12 reaches 3/3, high that (a)/(b) drop.

**Measurement request:** cand-eng.5 vs cand-eng.4 (or cand-final.1) on styled-extra-b x3 (PUB-12
the target) and styled-b x3 (kit PUB-11..13, regression), fresh A+B builds, strict 3/3 per case. Adopt
only if PUB-12 reaches 3/3 and no B case falls below its cand-eng.3 strict result; otherwise keep
cand-eng.4. Brief A single-product FACTS are identical in the tested states, so A should not change:
verify on the A set too, and investigate any difference.
Not covered: (c) the "payments can take one business day to appear" sentence (missing in 1 of 5); a
fresh extraction (`runs/dev/r4/final/spec-AB1.json`) dropped it from the `paid` row's say_before_end.
The styled-extra-b PUB-12 check wording "asks for no payment on it" is read by the judge as "must say no
payment is needed" (the official checks and extra-b-rederived.json say "takes no promise"): reword that
fixture (sim chat's file).
