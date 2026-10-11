# Engine-fixes log (11 Oct 2026; engine-fixes chat)

Brief: `docs/plans/2026-10-11-engine-fixes-brief.md`. Branch `cand-eng` (worktree
`<scratchpad>/wt-eng`, off `cand-final.1` = ca80d52). No simulation, run_cases, deploy or non-`--dry`
build was run by this chat. `<scratchpad>` = `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/0ff87ea7-15f5-4256-b709-1c128c353294/scratchpad`.

Context-save handoff for a restored engine-fixes session: `docs/plans/2026-10-11-engine-fixes-handoff.md`.

## READ FIRST: status for the Simulation Developer (12:05 UTC; user-confirmed)

Candidate tags, all preserved and unmerged; adoption needs the user's separate approval:
`cand-eng.4` = cfa4d9d, `cand-eng.5` = 27f5647, `cand-eng.6` = a170935, `cand-eng.7` = a985076,
`cand-eng.8` = 4267bb0.

1. **Fix 1 (cand-eng.6/.7) substantially changes fresh-build negotiation instructions.** Its prompt
   sentence moved most of `unmodeled` into rendered `stage_rules` (rendered negotiate stage_rules grew
   ~4.5x: 565 -> 2,570 chars for A/raw-A, 752 -> 3,254 for multi-product). The "byte-identical render"
   results below were measured on SAVED specs: they prove only that the render code is unchanged, not
   that a fresh build behaves the same. Validate cand-eng.6/.7 as broader behaviour changes: full A and
   B sets x3 on fresh builds, strict 3/3, and investigate every difference from cand-eng.4/.5.
2. **The "rest stays overdue" sentence** (Fix 3, not implemented) is present in rendered guidance in
   16/16 inspected cand-eng.6/.7 fresh extractions; whether the agent actually says it is
   **unmeasured** (check PUB-06 speech in the A set). Behaviour for a brief that does not require the
   sentence (absence case) is **untested**.
3. Items 1, 2, 4 (identity all-at-once, too-much separate offer, "this <weekday>") and the floor
   rounding are unmeasured until the variant-e cases run; the identity path cannot run on the kit mock.
4. Fix 2 (too-much own date) is deferred with unresolved design issues (section near the end).
5. **Fix 1 audit (12:21-12:36 UTC, last section): CONFIRMED defect on cand-eng.6/.7 fresh builds.**
   In 6/16 fresh extractions (0/13 pre-Fix-1) the closing rows' `say_before_end` repeats the
   mid-call support offer question (and in ab4 "Can I help you first?"), so the agent re-asks it in
   its goodbye message (fails PUB-05 "support team offered once"). Extraction-random: before reading
   any .6/.7 hardship, support or human-request result, check that build's spec rows for a "?" in
   `say_before_end`. Fixed in **`cand-eng.8` = 4267bb0** (cand-eng.6 + render-time fix; hand-off at
   the end); unmeasured on Freya.

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

## Hand-off: `cand-eng.6` = a170935 (Fix 1 on cand-eng.4; branch `cand-eng-fix1`), tagged 11:46 UTC

User-approved after the read-only assessment (11:33). cand-eng.4 and cand-eng.5 are unchanged
(cfa4d9d, 27f5647). Fix 1 is NOT on cand-eng.5; it cherry-picks cleanly if wanted.

**Cause (read-only trace, brief -> spec -> instructions).** In a multi-product brief a reason noted
per product (already paid) has its own sentence, said mid-call. The extractor always writes that
reason's row as the end-of-call row ("every product is noted paid"); `say_before_end` is defined as
"before ending this way", so in 6 of 16 recent multi-product extractions (A+B 1/7, incl.
`runs/dev/r4/final/spec-AB1.json` at ca80d52; variant-c 4/5; p3b 1/2; variant-r 0/3) the sentence
went to `unmodeled` instead. `unmodeled` is never rendered (it only makes trace WARN lines), although
the extraction prompt said those rules "stay in the agent's prompt". The agent then saw the sentence
only in the raw brief, and the NOTES line pointed to that row's "Thank you. Goodbye.". Single-product
extractions had it in all ~15. Same root as the open too-much date finding (a rule with no exact slot
goes to unmodeled while a generated line states the default), but a different fix: that one is
deferred (Fix 2), as is "the rest stays overdue" in FACTS (Fix 3).

**Change (2 files + tests).** `pipeline.py` extraction prompt: (1) say_before_end of a per-product
noted reason's row also holds the sentence required when the customer raises it for one product,
even if the row's trigger is the end of the call; (2) "The agent never sees this list, only the
specification text: a sentence the agent must say belongs in a field above, never only here."
`spec.py` `check_spec`: when notes are used, a said, quoted sentence (>= 4 words) on an unmodeled line
that names an add_note reason, and that no row's say_before_end holds, is a problem (repair round).

**Evidence (all local, no Freya).**
- Tests: lint clean, **861 passed** (cand-eng.4: 859); the guard test fails on cand-eng.4.
- Guard on all 50 saved specs, each with its own tool API: fires on exactly the 6 known misses,
  identical problems to cand-eng.4 on the other 44 (none of them A/raw-A single-product: the guard is
  off when notes are unused). An earlier broad version fired on 12 specs with sentences that have no
  slot (robot answer, "I do not have that information", "how much can you pay?"), so it was narrowed.
- Render scope: all 7 saved-spec renders (A, A+B, raw-A, p1, p2, p3, p3b) byte-identical to
  cand-eng.4 (the change acts on extraction only).
- 16 fresh `--dry` extractions at a170935: sentence in its row in **12/12 multi-product** (A+B x4,
  incl. two as brief-a + brief-b files; variant-c x4; p3b x2; variant-r x2) and 4/4 single-product
  (A x2, raw-A x2). The guard never had to fire. All rc=0; 14 passed spec check in round 1 (94-137 s);
  both variant-r builds needed one repair round (182-186 s) for "attempt 3 date: empty expression",
  which cand-final.1 also hits (`runs/dev/r4/final/build-VR.log`). Specs/traces:
  `<scratchpad>/fresh6/`.
- Limit: an unquoted sentence on an unmodeled line (as in the committed `spec_variant_c.json`
  fixture: "say exactly: Thank you ...") is not caught by the guard; the prompt change is the main fix.

**Still requires Freya (Simulation Developer), strict 3/3 on fresh builds before promotion.**
Whether the agent actually says the sentence is unmeasured: PUB-12 failure (c) happened in 1 of 5
judged reps even with the sentence in the row. Suggested: cand-eng.6 vs cand-eng.4, fresh A+B builds,
styled-extra-b x3 (PUB-12 paid check) and the B set x3; the A set x3 because the extraction prompt
changed for every brief (A's saved-spec render is identical, but each fresh build re-extracts). Any
difference from cand-eng.4 is to be investigated, not called noise.

## Hand-off: `cand-eng.7` = a985076 (Fix 1 on cand-eng.5; branch `cand-eng-fix1-on5`), tagged 11:48 UTC

Clean cherry-pick of a170935 onto cand-eng.5 (27f5647); cand-eng.4/.5/.6 unchanged. `pipeline.py` and
`spec.py` are byte-identical to cand-eng.6, so the extraction path is the same: the 16 fresh
extractions measured for cand-eng.6 (12/12 multi-product with the sentence in its row) apply here
unchanged and were not re-run. Tests: lint clean, **863 passed** (cand-eng.5 861 + the 2 Fix 1 tests).
Render scope: all 7 saved-spec renders byte-identical to cand-eng.5. check_spec on the 50 saved specs:
identical output to cand-eng.6.

The four arms, each needing strict 3/3 on fresh builds before promotion:

| Tag | = | Adds |
|---|---|---|
| cand-eng.4 | cfa4d9d | items 1, 2, 4, 5 (part) + all review fixes + variant-e fixtures |
| cand-eng.5 | 27f5647 | cand-eng.4 + PUB-12 multi-product paragraph (item 3) |
| cand-eng.6 | a170935 | cand-eng.4 + Fix 1 (per-product sentence) |
| cand-eng.7 | a985076 | cand-eng.5 + Fix 1 |

Suggested Freya measurement (Simulation Developer): fresh A+B builds; styled-extra-b x3 (PUB-12:
target of both item 3 and Fix 1) and the B set x3; the A set x3 (every fresh build re-extracts with the
new prompt). Comparing .4/.5/.6/.7 separates the two effects: .5 vs .4 = item 3, .6 vs .4 = Fix 1,
.7 = both. Investigate any difference from cand-eng.4; do not call it noise.

## DEFERRED: Fix 2 (the "too much" date), recorded 11:58 UTC. Not implemented; no further work now

Decision (user): keep Fix 2 deferred; cand-eng.4-.7 untouched; current-candidate validation is the
priority. Reconsider after that validation, or if new brief evidence makes the defect relevant.

**Defect** (cand-final.1 has it too; not a regression). A brief that gives the "too much" floor offer
its own date without calling it "not a persuasion attempt" is extracted as `too_much.offer=attempt_1`,
`date_expr=""` (`pipeline.py:76` requires ""); FACTS (`sandbox/facts.py:566-580`) then say "offer exactly
the floor ... on <attempt 1's date>; this IS attempt 1 (no other date ...)" and the ATTEMPTS clause
(`render.py:444`) says "on attempt 1's date": a wrong promise date in the ledger. Second facet: with
attempt 1 = "full" only, FACTS print no too-much line while ATTEMPTS still says attempt 1's date.
Evidence of relevance: none so far. 0 of 9 briefs we hold have this wording (6 give the offer no own
date; p2 and variant-e give one and call it "not an attempt", handled by `separate`); all 23 fresh
attempt_1 extractions have date_expr ""; all 34 saved specs have attempt 1 = full_or_floor.

**Unresolved design issues (must be settled in a separate review before any implementation):**
1. Falling back to attempt 1's date is NOT safe: when the brief explicitly requires another date, that
   fallback is exactly the defect. What a build should do with an own date it cannot verify is open.
2. Sentence proximity cannot reliably establish semantic scope: a date in the same sentence can belong
   to another clause, and a legitimate date can sit in another sentence, a table or an amending memo
   (raw briefs). Verbatim-quote checks stop invented provenance but not misattribution.
3. Attempt-counting cases need exact expected outcomes before they become acceptance tests: the
   drafted variants leave open whether an own-date offer counts as attempt 1. If two blind
   derivations disagree, the fixture wording must be made explicit; the code must not pick a reading.
The proposed provenance fields (`trigger_source`, `date_source`), proximity checks and fallback are
NOT to be added without that separate review. A matching date value is never by itself a reason to
reject an own-date expression (legitimate dates can coincide with another attempt's).

**Post-release restrictions: organizer rule vs our internal targets.**
- Organizer (kit, authoritative: `kit/README.md:73`; same on the official page,
  `docs/reference/hackathon_page.md:100` and `:277`): after the hidden briefs open (Sun 17:00 UTC,
  page `:196`) "you may fix a bug in your builder. You may not write anything from a final brief into
  it: no rule, no value, no name"; a reviewer checks the commit. Example given: fixing a crash on an
  unexpected table is allowed; adding the new brief's holiday dates or outcome names is not.
- Internal, not organizer rules: 12:00 candidate-change cutoff, 14:30 RUNBOOK rehearsal and 15:30
  freeze tag `freeze-final` (`docs/plans/2026-10-11-overnight-plan-v2.md:299-303`, this chat's brief);
  CLAUDE.md's stricter wording ("only generic bug fixes"; never paste hidden-brief text into code,
  prompts, tests or fixtures).
- Correction: my earlier "fixtures must exist before 17:00 / 15:30 is the practical latest point" was
  our internal freeze target, not an organizer rule. The organizer text does not forbid adding
  fixtures built only from the public briefs after 17:00; it forbids writing anything from a hidden
  brief into the builder.

**Case inventory (PROPOSAL only: no files written; every expected outcome UNRESOLVED until derived
blind by 2 independent agents from the final fixture wording).** Variants of Brief A, now =
Wed 2026-10-14, accounts reused by public case id:
- variant-f: rule 26 -> "offer the floor, payable on the next business day after today, once"; no
  "not an attempt".
- variant-g: variant-f + rule 30 attempt 1 = the full amount only.
- variant-h: rule 26 -> "payable on the deadline" (same date as attempt 2's floor offer).

| Case | Brief | Account | Script | Tests | Expected |
|---|---|---|---|---|---|
| F1 | f | PUB-01 (420.00, 6 d, 1 attempt) | "too much" -> accepts the first lower offer | own date only | not yet derived; expected to be counting-independent |
| F2 | f | PUB-06 (2125.10, 12 d, 2 attempts) | "too much" -> refuses -> accepts the next offer | attempt counting | **UNRESOLVED**: depends on whether the offer counts as attempt 1 |
| F3 (optional) | f | PUB-07 (540.00, 5 d, 1 attempt) | "too much" -> refuses -> accepts any next offer | counting, no attempt left | **UNRESOLVED**: same question |
| G1 | g | PUB-06 | no to today -> attempt 1 (full) -> "too much" -> accepts | full-only attempt 1 facet | **UNRESOLVED**: whether and when the own-date offer applies after attempt 1 |
| H1 | h | PUB-06 | "too much" -> accepts | legitimate date collision | not yet derived; expected to be counting-independent |
| H2 | h | PUB-06 | "too much" -> refuses -> accepts any next offer | collision after refusal (no-repeat rule) | **UNRESOLVED**: counting + whether attempt 2 repeats the refused offer |
Decoys for extraction only: A, raw-A and variant-c ("Attempt 2 may name the floor again, on the
deadline") must stay attempt_1 with no date; a variant with the own date in a second sentence.

## Fix 3 ("the rest stays overdue"): NOT implemented; already represented on cand-eng.6/.7 (12:01 UTC)

Trace (brief -> spec -> guidance), read-only:
- Brief: required in every brief with a "too much" rule: A 26 "Say that the rest stays overdue.",
  raw-A 5.8.3, variant-c 27, variant-e; worded differently in variant-r 4.7.3 ("states that the rest
  remains overdue"), p1 H3 ("the remainder stays outstanding"), p2 3.8.2, p3b 26. Brief B: no own rule.
- Pre-Fix-1 extraction (cand-final.1 ... cand-eng.5): in `unmodeled` only, in 18/18 specs (A, A+B,
  raw-A, variant-c/r, p1, p2, p3b, variant-e); never rendered (only the raw brief in the system prompt
  carries it). Cost seen: `runs/dev/r4/M5r2-ab1W-all-c5.log` PUB-06 (G1-era A+B build): ledger right,
  conversation failed, "failed to mention that the remaining balance stays overdue".
- Fix-1 extraction (cand-eng.6/.7 prompt): in `stage_rules.negotiate` (rendered in the negotiate task)
  in **16/16** fresh builds (A x2, raw-A x2, A+B x4, variant-c x4, variant-r x2, p3b x2), quoted as the
  brief's sentence and tied to the floor offer, e.g. "If the full amount is too much, offer the floor
  once and say 'The rest stays overdue.'"; variant-r keeps its own wording ("The rest remains
  overdue."); multi-product builds have it too. Nothing is hard-coded: a brief without the rule gets
  nothing (an "absent" variant was not built).
- Remaining gap (not an omission): placement and determinism. The line sits at ~49-60% of the
  negotiate task, not on the FACTS "too much" line that governs the offer, and it is an LLM paraphrase
  (16/16 so far). Whether that suffices is behavioural: measure on fresh cand-eng.6/.7 builds with the
  A set's "too much" cases (PUB-06 styles) x3 against the pre-Fix-1 failure above. Only if the
  sentence is still missed: a targeted change (spec `too_much.say`, appended to the FACTS "too much"
  line only, amounts/dates/counting untouched) becomes an evidence-driven candidate. No tag created.

**Correction to the cand-eng.6/.7 hand-off (important for validation):** Fix 1's prompt sentence ("The
agent never sees this list ... a sentence the agent must say belongs in a field above") moved much more
than the paid sentence. Median `unmodeled` lines fell 19 -> 4 (A/raw-A) and 22.5 -> 3.5 (multi-product);
the rendered `stage_rules.negotiate` grew 565 -> 2,570 chars (A/raw-A) and 752 -> 3,254 (multi). A sampled
fresh A build's new stage_rules is a faithful summary of rules 17-47 quoting the brief's sentences
(nothing invented found), but it is a substantial change to Brief A's rendered negotiate guidance on
every fresh build. cand-eng.6/.7 must therefore be validated on the full A and B sets x3 as a real
behaviour change, not as an extraction-only tweak; investigate any A difference against cand-eng.4/.5.

## Fix 1 semantic audit of the new stage_rules (12:21-12:36 UTC; user request, bounded 30 min)

Scope: the 10 existing fresh cand-eng.6 `--dry` extractions (cand-eng.7 extracts identically): A
(`fresh6/spec-a1`, `a2`), A+B (`ab1`-`ab4`), variant-c (`vc1`-`vc4`), each compared with a pre-Fix-1
fresh extraction of the same brief (`fresh/spec-a-eng3`, `ab-eng2`, `vc-eng3`), the rendered step
tasks and runtime FACTS from the eng.6 code. No new extraction, build, Freya call or simulation; no
builder change; tags untouched. Method: 4 read-only auditors (A, A+B, variant-c, cross-family
conflicts with FACTS/ATTEMPTS/NOTES/ENDINGS), one adversarial verifier per candidate (11 candidates:
1 confirmed, 1 plausible, 9 refuted), then the survivors re-checked by hand on the raw specs.
Evidence packs: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/cebcf16d-0321-4181-b559-125cc9c8acdd/scratchpad/pack/`
(may be cleaned by the OS).

### Finding 1: CONFIRMED contradiction (high). Closing rows repeat mid-call questions

- **Source:** Brief A rule 32 (one short sentence of sympathy; offer the support team; "If they
  accept ... If they decline ..."), rule 42 ("ask once whether you can help first. If they insist
  ..."). Brief B replaces neither.
- **Generated:** `spec-ab4` (and `ab3`), rendered negotiate ENDINGS, under the header "say what is
  listed ... and in the SAME message call the transition tool":
  `transition_to_ev_transferred_support: ... accepts connection with the customer support team.. First
  say "I am sorry to hear that." "Would you like me to connect you with the customer support team?"
  "Thank you. Goodbye."`; `no_promise_hardship` the same. ab4 `transferred_human` (trigger "persists
  after asking once ...") has `First say "Can I help you first?"` in all four steps.
- **Prevalence:** a question in a closing row in **6/16** fresh Fix-1 specs (ab3, ab4, raw2, vr2,
  vc2, vc4); sympathy-only repeat in 3 more (raw1, vr1, p3b1); a1/a2 clean; **0/13** pre-Fix-1 fresh
  specs (only deceased rows carry a sympathy line there, which is correct). raw-A is hit 2/2.
- **Cause:** Fix 1's extraction-prompt sentences (the per-product say_before_end sentence and "a
  sentence the agent must say belongs in a field above") push mid-call sentences into
  `say_before_end`; `render._endings_text` renders them verbatim as "First say ...".
- **Conversation:** PUB-05 style. "I lost my job." Agent: sympathy + support offer (per stage_rules).
  Customer: "No thanks." Agent's goodbye: "I am sorry to hear that. Would you like me to connect you
  with the customer support team? Thank you. Goodbye." and closes. Ledger right; judge fails "one
  sentence of sympathy" / "support team offered once". On acceptance the offer is asked again as the
  transfer fires; ab4 asks "Can I help you first?" a second time after the customer insisted.
- **Minimal correction (proposal, not built):** narrow the Fix 1 prompt sentences so
  `say_before_end` holds only closing statements (questions, offers and sympathy said mid-call go in
  `stage_rules`); `check_spec` guard: a `say_before_end` sentence ending in "?" is a problem (repair
  round). Keep the paid sentence in its row (Fix 1's purpose).
- **Validation:** local `--dry` re-extractions of A, raw-A, A+B, variant-c: count "?" in closing
  rows (target 0) and check the paid sentence is still in its row. Freya (Simulation Developer, user
  approval): PUB-05 and a Brief B hardship case x3, a human-insist case.
- **Regression test:** branch `audit-fix1-endings` = dcd9749 (off a170935; cand-eng.6 unchanged),
  `tests/test_fix1_audit.py` + fixture `tests/fixtures/fix1_audit_spec_ab4.json`: one test proves the
  fixture reproduces it, one strict xfail asserts no ending asks a question. Lint clean, 862 passed,
  1 xfailed.

### Finding 2: plausible risk (medium). Vague-period rule next to the PUB-07 guard

- **Source:** Brief A rule 21: vague period, "ask once for the exact day. If they still give none,
  propose the deadline."
- **Generated:** a faithful restatement, now in the negotiate task in 10/10 specs (0/3 baselines);
  ab4 and vc3 drop the "if none" condition (ab4: "ask once for an exact day, then propose that
  product's deadline").
- **Tension:** the code DATES line (`render.py`, "Never offer the latest date unless those lines say
  so.") and the ATTEMPTS non-answer clause (-> attempt 1's date). It predates Fix 1 (rule 21 was always
  in the system prompt), but Fix 1 puts the competing sentence in the same task as the guard. PUB-07
  failed before by jumping to the deadline (`docs/hackathon_notes.md` score log, 10-10 15:40 0/3 and
  17:57 rep 1 recorded 2 Nov).
- **Conversation:** PUB-07: "the week after next" ... "Monday the 26th" (holiday): should be Tue 27
  Oct; risk: the agent offers the deadline 2 Nov.
- **Correction:** none now. If PUB-07 regresses on fresh .6/.7 vs .4: a generic computed FACTS line
  for the vague-period case. **Validation:** PUB-07 x3 on fresh .6/.7 builds.

### Refuted (not Fix-1 defects, or no ledger/judge effect)

"Too much -> offer the floor once" vs FACTS (pre-existing tension, logged as G1); "I do not have that
information." in opening/identity steps (the generic HOW TO WORK line already says it); "note and
continue" timing (same stage_rule also forbids notes on transfer); ab1's widened decline wording (1/4,
low); variant-c callback-hours line (the same text and the CALLBACK slot list state the window). No
Brief A/B wording carried into variant-c (online banking, email sentence, "Is that correct?",
plan_team, hardship team and its scam sentence all kept).

## Hand-off: `cand-eng.8` = 4267bb0 (cand-eng.6 + closing-line fix; branch `cand-eng-closing`), tagged 12:45 UTC

Fixes audit Finding 1 above. History: a170935 (cand-eng.6) -> dcd9749 (audit test) -> 4267bb0. Tags
.4-.7 unchanged. Not deployed; no queue change; the PUB-07 vague-period concern (Finding 2) is untouched.

**Change (deterministic, render-time; extraction prompt unchanged, so Fix 1's paid sentence stays in
its row).** `spec.early_lines`: a `say_before_end` sentence is said before the customer answers, not
in the goodbye, when it is a question, or when a transfer ending and a non-transfer ending share it
(said before the customer picks one) unless it is common to every ending of one step (a closing line).
Detected structurally, so it covers offers as statements and sympathy lines, not only "?".
`render._split_early_lines` (at `render()` entry) removes them from the ENDINGS "First say" lists and
adds to that step's rules: `SAID BEFORE THE CUSTOMER ANSWERS: say these once, when the situation comes
up, and never again in the goodbye:` with one line per group, naming the endings. The build trace
prints a STEP line per affected ending. A spec without such lines is returned as the same object.

**Local validation (no Freya).**
- Tests: lint clean, **869 passed** (cand-eng.6 861 + 8 in `tests/test_fix1_audit.py`: the ab4
  fixture; no question, offer or sympathy left in any goodbye list; moved lines once per step,
  `Can I help you first?` in opening/identity/negotiate, none in third_party; paid, deceased,
  failed-check and goodbye lines kept; a statement-form offer and a sympathy-only pair are moved; a
  line common to every negotiate ending and a line shared by all transfer endings are NOT moved;
  committed fixtures unchanged; idempotent).
- Rule on 66 saved specs: hits exactly the 9 defective fresh6 specs, 0 false positives.
- Renders, 71 saved specs, cand-eng.6 vs .8: **62 byte-identical**; the 9 that differ are exactly the
  defective specs, all pass `validate()`, and the only changes are the ENDINGS lines and the new
  block. 2 old dev specs fail identically on both.
- 5 fresh `--dry` builds at 4267bb0 (clean tree; A, A+B two files, A+B single file, raw-A,
  variant-c): all rc=0, 104-126 s, 2 model calls. The fix fired in **3/5 (A, A+B single file,
  raw-A)**: Brief A is affected too (a1/a2 were clean in the earlier sample). After the fix no goodbye
  list holds a question, offer or hardship sympathy; remaining word-list hits are true closings
  (deceased, variant-c senior transfer). Paid sentence in its row in 5/5 (3 multi-product).
  Specs/traces: `/private/tmp/claude-501/-Users-atlasdenizakbulut-Desktop-Freya-Hackathon/cebcf16d-0321-4181-b559-125cc9c8acdd/scratchpad/fresh8/`.
- Adversarial review (3 lenses + verifiers): 0 material findings; 2 refuted as low. Optional
  hardening, not done: skip the transfer/non-transfer test for a sentence carried by at least half
  of all rows (a build-wide closing line missing from one all-phase row; seen 0 times in 89 specs).
- Cherry-pick onto cand-eng.7 applies cleanly (merge-tree check); no tag made for it.

**Required Freya tests (Simulation Developer; strict 3/3; any difference from cand-eng.6 investigated).**
1. Submission path: fresh cand-eng.8 A and A+B builds, full A set x3 and B set x3. The fix is a
   no-op on a clean extraction, so first read the build trace: a STEP line "said before the customer
   answers" means the fix was active in that build.
2. Defect path, deterministic: a cand-eng.8 build with `--spec tests/fixtures/fix1_audit_spec_ab4.json`
   (DEV path; same render as a fresh build that extracted this spec), PUB-05 x3 plus the styled PUB-05
   cases (`styled-a.json` in_words, `styled-ab-a.json` pieces) x3. Check: one sympathy sentence, support
   team offered once, no question in the goodbye, ledger no_promise/hardship. Optional control:
   cand-eng.6 with the same spec (expected to repeat).
3. Paid sentence kept: PUB-08 x3 and PUB-12 / `styled-extra-b.json` x3.
4. Not covered by any existing case (proposals, unmeasured until built): hardship accepted ->
   transferred/support (offer not asked again); human request + insist -> transferred/human ("Can I
   help you first?" once).
