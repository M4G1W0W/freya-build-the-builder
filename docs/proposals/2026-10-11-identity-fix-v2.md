# Proposal v2 (NOT implemented): identity-stage fix (I1 cut-off answers, I2 "why do you need that?")

Status: design only. This is v2 of `2026-10-11-identity-fix.md` after the 3 reviews in `2026-10-11-identity-fix-review.md`
(all ADOPT-WITH-AMENDMENTS), ~02:25 UTC 11 Oct. Base W = cand-g1 83f8263 (WG1). The change is prompt-only plus one renderer
signature change. Unchanged: `system_prompt` (HOW TO WORK, render.py:193), hooks.py, nodes, caps. Generic: every value comes from the
spec (format, ask, decline_explain) or from the verify_identity tool shape; Brief A rules 11-15/43/45 are only the worked example.
v1 §1 (root causes) still holds, but its premise "0/55 complete after Please go on." is withdrawn (replay found at least 10).

## 1. Review points → decision
| Point (severity) | Decision | Reason (one line) |
|---|---|---|
| PJ1 + HB4: the counter counts refusals and questions back; the cut-off line resets it (HIGH/MED) | adopted | T6 counts only partial or broken-off messages, and our own two replies do not restart the count. |
| PJ2 + HB5a + RP5: "never send the same answer twice" stalls rule 12 (HIGH/MED) | adopted | T7: a value given again after its result is a new answer; only the same messages are never sent twice. |
| PJ3: rule 45; "why should I?" (MED) | adopted | T8: declining is whatever the BANK BRIEF and the declining ENDING say, and a refusing question counts as declining. |
| PJ4: a scam or robot question answered with X (MED) | adopted | Other questions back get the brief's answer for that question; only "why do you need it" gets X. |
| PJ5: two-digit year → send the latest such year (MED) | adapted | No 3-turn loop: T4 asks at once for four digits. The year is never sent: variant-c rule 12 forbids it and the century would be a guess. |
| PJ6 + HB6: a hint retry ("March") loops (MED/LOW) | adopted | T3: the new part replaces that part of the answer just checked. |
| PJ7 + RP7a: X said twice reads as explaining twice (LOW) | kept, measured | "Explain once" binds refusals. T8 says an answer to "why" is not the explanation, so R1's check still sees one. |
| PJ8 + RP7b: asks_back "which account?" ×2 closes as declined (LOW) | no change, measured | Literal rule 15. Block 1 adds an asks_back run. |
| PJ9: accepted items; add R1/R2 asks_back to the gate | adopted | §5, block 1. |
| HB1: B hard-codes rule 15; `say ""` when X is empty (HIGH) | adopted | T8 defers to the BANK BRIEF and the ENDING; X clauses render only when decline_explain is non-empty. |
| HB2: "eighty-four." passes as a full year (HIGH) | adopted with RP2 | T4: a year in words must include the century, and two digits alone are never complete. |
| HB3: alnum "SW1A." sends half a code; the override is too wide (HIGH/MED) | adopted with RP3 | T5: text C = "all of it", and a first part or "more follows" is a part. The T3 override covers only date, year and digits. |
| HB5b: an all-at-once verify_identity gets per-answer sentences (MED) | adopted | Shape A renders T2-A and T9 and no per-answer CALL sentences. |
| HB7: parse formats as hooks.py does; letters under digits:N (LOW) | adopted | `_complete_when` uses the hooks.py:367/:291-294 parse. Digits C adds "or all of it, if it has letters". |
| HB8: no render fixture for alnum, 1 or 3 questions, all-at-once, empty X | adopted | §4, tests U4-U7. |
| RP1: "12 July 1991. sorry," is held (b20818a2) (HIGH) | adopted, adapted | T3: correction words count only before any full stop, and only when the message goes on to give another value. |
| RP2: "…nineteen ninety-one" with no full stop is held (235173ce) (HIGH) | adopted with HB2 | T4: a year in words that ends on a number word from one to nineteen after the century is complete. |
| RP3: alnum needs a final full stop, which the simulator often omits (MED-HIGH) | adopted | T5: the message may end right after the value. |
| RP4: counter details; the short ask says the question (MED) | adopted | The short ask is `"Just {W}, please."` without the question (lower PUB-12 risk); our own replies do not reset the count. |
| RP6: the stage rule's "question about the call" invites matching (LOW-MED) | adapted | T8 points to the BANK BRIEF instead of quoting Brief A's wording. |
| RP not fixed: d41ea98c, eabf5674 (no complete message) | acknowledged | The counter is the only lever here. v1 option C (spoken line at the cap exit) stays out: it is a separate graph change, and the window allows one change. |

## 2. Conflicts resolved
- **Year in words.** HB2 alone ("includes the century" plus "at the very end may still go on") holds 235173ce J9 "It is the
  twelfth of July nineteen ninety-one" (no full stop), so that pass breaks. RP2 alone ("ends on one to nine") accepts
  "ninety-one", which breaks variant-c rule 12. T4 combines them: the century is required; the year is complete when a
  full stop or other words follow, or when it ends on a number word from one to nineteen after the century. Result: J9 is
  complete, "nineteen ninety." is complete (79778b2e, 6902b731), and "eighty-four" is never complete.
- **Short ask.** v1 and PJ9 used `"{ask} Just {W}"`; RP4 uses `"Just {W}, please."`. Pick RP4. In 85953f34 the 3rd counted message gets the
  short ask instead of "Please go on."; the full date that follows is sent either way, and PUB-03 has no "not asked again" check. In 235173ce J5
  gets the cut-off line and J7 the short ask; the next full date is sent, so the outcome is unchanged in expectation (block 2 measures it).
  Leaving the question out avoids PUB-12's "date of birth not asked again".
- **Two-digit year.** PJ5 (send the year with a guessed century) loses to HB2 and variant-c rule 12 (never send it).
  Asking at once for the four digits is literally what variant-c rule 12 says, and Brief A does not forbid it.
- **Correction exception.** v1 held "12 July 1991. sorry,". In v2 a full stop before the correction word makes the value
  final, so b20818a2 runs as recorded: J3 → "Please go on.", J5 sent, J7 → "Please go on.", J9 sent, J11 → "Please go on.",
  J13 ("21 July 1990. This is getting") sent.

## 3. Rendered text v2: render.py `_identity_task(spec, t)`
**Call site:** render.py:438 becomes `_identity_task(spec, by["verify_identity"])`. **T1-T8 replace** render.py:249-257 (question list, the parts
sentences of :255, the question-back sentence :257). **Order:** T1-T7, "Obey what_to_do_next in every verify_identity result.", T8, "Never mention
the debt…", stage_rules, ENDINGS (lines not named T-n unchanged). **Shapes:** **P** (per-answer) when `t.field(af) is not None`, the branch
verify_pre takes at runtime (`if _AF and _AF in _b`, hooks.py:595); otherwise **A** (all-at-once: verify_pre normalises each body field named like a
question key, hooks.py:603). qf/af = identity.question_field/answer_field; K = the kinds `_complete_when` returns; `{X}` = `_quote(decline_explain)`,
used only when decline_explain is non-empty after strip.
- **T1** (one per question). P: `{n}. {ask} (send {qf}={key}; answer format: {fmt}; complete when it has {C}; short ask: "Just {W}, please.")`.
  A: the same, with `(field {key}; …` in place of `(send {qf}={key}; …`.
- **T2-P** (replaces the first two sentences of :255): `Whenever the customer's message holds a complete answer to the question you asked (even if
  the same message also asks something, complains or breaks off), CALL verify_identity with that answer FIRST, then reply. CALL verify_identity
  once per complete answer, with {qf} set to the question key and {af} set to the answer in the format above.`
- **T2-A**: `Ask the questions one at a time and keep each complete answer. Once every question has a complete answer, CALL verify_identity once
  with all of them, each in its own field in the format above, FIRST, then reply. If a result asks for an answer again, ask for it, then CALL
  verify_identity again with every answer, the new one in place of the old (an answer the customer gives again after a result, even the same
  value, is a new answer).`
- **T3 COMPLETE** (always). `{since}` = P "since the last verify_identity result", A "since you asked that question". The `[…]` part renders in P
  only. The last sentence renders only if K ∩ {date, year, digits} is not empty. `COMPLETE: join the parts the customer gave {since}; if they correct a
  part, use the corrected part; after a result that asks for one part again (for example the month as a word), the part they give replaces that part
  of the answer just checked. An answer is complete when it passes its "complete when" test above, whatever follows it in the message (a full stop, a
  complaint, a question, or words that break off)[: CALL verify_identity with it at once, before you reply to the rest]. Only if "sorry", "I mean",
  "no", "wait" or "actually" follow it before any full stop, use the value they go on to give; while that value is cut off, it is a part. For a date,
  a year or digits, these tests decide what is complete, not the word list in HOW TO WORK.`
- **T4 YEAR** (only if K ∩ {date, year}): `A full year has four digits: in figures, said one digit at a time, or in words that include the century
  ("nineteen ninety-one", "two thousand and four"). Two digits alone ("ninety-one", "'91") are never a full year: do not send such an answer; ask at
  once "Just the year, all four digits, please." (this is not counted under CUT-OFF; if the BANK BRIEF says more about it, follow that). A year in
  words is complete when a full stop or other words follow it, or when it ends on a number word from one to nineteen after its century ("nineteen
  ninety-one", "twenty fifteen"); at the very end of a message, a year in words that ends on its century, on a tens word ("ninety") or on
  "thousand" or "and" may still go on.`
- **T5 TEXT** (only if "text" ∈ K): `An answer in letters or words (a code, a name) is complete when the customer has said all of it: the message may
  end right after it, unless it ends on half a word or on "and", "the" or "of". A first part of a code, or words saying more follows, is a part.`
- **T6 CUT-OFF** (always): `CUT-OFF: count only the customer's messages that break off or hold only part of an answer, since you last asked this
  security question or got a verify_identity result; your "Please go on." and the cut-off line do not restart the count. A whole message that is a
  question back, a refusal or a complaint is not counted: the rules below decide it. After the 1st counted message reply "Please go on."; after the
  2nd, the cut-off line from HOW TO WORK; after the 3rd, say only that question's short ask (not the question itself), which restarts the count. In
  this step this count replaces the HOW TO WORK rules for "Please go on." and against repeating a question; never ask the whole question again for a
  part.`
- **T7 RESEND** (P only): `If the customer says they already answered, look at their messages since the last verify_identity result: if they hold
  a complete answer you did not send, CALL verify_identity with it now. Never send again an answer from messages you already sent it from; an answer
  the customer gives again after its result, even the same value, is a new answer: send it.`
- **T8 DECLINING, X non-empty** (replaces :257): `DECLINING: what counts as declining the security questions, and how often it ends the call, is only what the
  BANK BRIEF and the ENDING for declining say; a question that refuses ("why should I?") is declining. When the customer declines and no ENDING
  applies yet, explain once: {X} (an earlier answer to why you need it is not this explanation). Do not repeat the security question in that message;
  they answer next. A question that only asks why you need the answer is not declining unless the BANK BRIEF says so: say {X} without repeating the
  security question, and wait for their answer. Any other question back that the BANK BRIEF does not count as declining (for example whether you are
  a robot, or whether this is a scam) is not declining: answer it in one short sentence as the brief says for that question, without repeating the
  security question, and wait for their answer. Such questions never end the call unless another ENDING's trigger names them. A complaint, "I
  already told you" or a cut-off message is never declining.`
- **T8 DECLINING, X empty**: the same first sentence, then `When the customer declines, do what the BANK BRIEF says for it. A question back that the
  BANK BRIEF does not count as declining (for example why you need the answer, whether you are a robot, or whether this is a scam) is not declining:
  answer it in one short sentence as the brief says for that question, without repeating the security question, and wait for their answer.`
  It ends with the same last two sentences as the non-empty version.
- **T9** (A only; the render.py `_verify_tool` description, which stays unchanged in P): `Check the security answers. CALL it once the customer has
  given a complete answer to every security question, each in its own field.`

**Walk-through (Brief A):** R1 refusal → X, 2nd refusal → declined ENDING. R2 "What is this call about?" → X (rule 15 counts it as declining), 2nd →
ENDING. R3 "Why do you need that?" → X, no ending, then the date is sent. T8 fixes 68d28036 J7; T3/T4 fix d10044ef J11 and the "nineteen ninety."
calls. A 1-question spec renders the same blocks; "SW1A." as the first half of a code is a part under T5.

## 4. Helper (render.py, next to `_field_desc`) and tests
`_complete_when(fmt: str) -> tuple[str, str, str]` returns (kind, C, W), parsed like hooks.py: `f = str(fmt).strip().lower()` (:367); `f == "date"`
(:208), `f == "year"` (:333); `f.startswith("digits")` → `int(f.split(":")[1])`, 0 on any error (:291-294); anything else → text.
| fmt (after parsing) | kind | C ("complete when it has …") | W (`Just W, please.`) |
|---|---|---|---|
| date | date | a day, a month and a full year | the day, the month and the year |
| year | year | a full year | the year, all four digits |
| digits:N, N > 0 | digits | N digits (or all of it, if it has letters) | the N digits |
| alnum, text, time, digits, digits:0, digits:x, "", unknown | text | all of it | the whole answer |

Unit tests to add in tests/test_render.py (no network):
- **U1** `test_complete_when_parses_formats_like_the_hooks`: "date", " Date ", "year", "digits:4", "DIGITS:5", "digits", "digits:x", "digits:0", "alnum", "text",
  "time" and "" each give the row in the table.
- **U2** SPEC_A: "complete when it has a day, a month and a full year", 'short ask: "Just the 4 digits, please."'; T4, T6, T7 present, T5 absent;
  the negotiate task still has 'but if your previous reply was already "Please go on.", use the cut-off line'.
- **U3** spec_variant_c.json with briefs/variant-c.openapi.json: "a full year", "5 digits", 'ask at once "Just the year, all four digits, please."'; T5 absent.
- **U4** SPEC_A copy with 3 questions (year / alnum "postcode" / text "the name of your first school"): lines "1. ", "2. ", "3. "; C "all of it";
  T5 present ('unless it ends on half a word or on "and", "the" or "of"', "A first part of a code"); the override present; `validate(...) == []`.
- **U5** 1-question spec (date only): exactly one numbered line; T3, T4, T6 and T7 present; T5 absent; it validates.
- **U6** all-at-once (tmp_path copy of kit/tools/openapi.json; verify_identity request = customer_id + one string field per question key, no
  field/answer): T2-A, T9, "(field date_of_birth;" present; "CALL verify_identity with it at once" and T7 absent; validates.
- **U7** empty decline_explain: 'say ""' and "explain once" absent; "do what the BANK BRIEF says for it" and "Such questions never end the call
  unless another ENDING's trigger names them" present.
- **U8** SPEC_A: present "is only what the BANK BRIEF and the ENDING for declining say", 'say "These questions protect your account." without
  repeating', "is not this explanation", "as the brief says for that question", "even the same value, is a new answer: send it", "before any full
  stop", "replaces that part of the answer just checked"; absent "(why you need it, what the call is about)", "Never send the same answer twice".
- **U9** spec_a, variant_r, variant_c and U4-U7 render deterministically and validate. `test_no_brief_values` must still pass: the new source holds
  no denied token.

Existing asserts to change in `test_prompts_handle_customer_speech_styles` (test_render.py:385-394): the `for task in (ident, nego0)` cut-off-line
assert keeps only nego0; "never ask the whole question again for it" → "…for a part"; the "join the parts … since the last verify_identity result"
and "Do not repeat the security question in that message" asserts stay. `test_turn_caps_end_on_the_stage_default_row` is untouched (C stays out).

## 5. Matched simulation plan (updated)
**Pre-flight (no simulation):** (1) `uv run pytest`, ruff, a raw-a `--dry` build, all fixture renders. (2) Deploy the treatment with `--spec
runs/dev/spec-a-llm.json` to a new slot exp-i12-a. (3) `runs/dev/r4/exportdiff.py` against control exp-g1-a: only the identity task_message may
differ; first confirm exp-g1-a equals W's render, else redeploy W to a control slot. (4) Optional, `scripts/chat.py <wf> --case PUB-03 --say "Yes."
--say …`: "12 July 1991. sorry," → verify call; "It is the twelfth of July nineteen ninety-one" → call; "…nineteen ninety." → call; "14 March
eighty-eight." → no call + the year ask; "Why do you need that?" → X, no ending.

| Block | Arm | Cases × reps (`python3 kit/tools/run_cases.py <agent> …`) | Calls |
|---|---|---|---|
| 1 gate | treatment | `--cases tests/fixtures/cases/identity-rd.json --only PUB-08,PUB-06` (R1, R2) ×3, then the same with `--style asks_back` ×3 | 12 |
| 2 target | both, alternated | PUB-03 `corrects`, `in_words`, `pieces`; PUB-04 `asks_back`; PUB-09 `asks_back`; R3 (identity-rd `--only PUB-01`) ×3 | 36 |
| 2b regression | treatment | R4 (identity-rd `--only PUB-04`: two wrong answers, then the right one) ×3 | 3 |
| 3 guard | treatment | styled-a, 10 cases ×3 | 30 |

**Totals:** 81 calls, about 25-90 min. **Stop** after block 1 if any ledger is not not_verified/declined, or the judge fails "explains once" or
"closes". **Ship if all hold:** block 1 12/12; block 2 treatment strict 3/3 wherever control is 3/3, R3 3/3, no I1/I2 signature; block 2b 3/3
promise; block 3 no new identity-stage failure class.

**I1/I2 signatures, counted per call:** a complete answer not sent; the same cut-off reply twice in a row; a 40-turn cap exit; "Please go on." in
reply to a question back; an ending right after "why".
`classify_failures.py` (cited in v1) is not in the repo: count these from the transcripts (scripts/show_call.py) or with a small script.
PUB-13 asks_back (Brief B) needs an A+B agent and is left out.

## 6. Residual risks
A correction after a full stop ("1990. Sorry, I mean 1991") now costs a wrong answer. A refusal phrased as an unusual question may never close and
runs to the silent 40-turn cap (C is out). X said twice is a judge risk. The short ask is new behaviour in 235173ce-like calls. The all-at-once
post-hook text (verify_post) is not reviewed. d41ea98c/eabf5674-type loops still depend on the model obeying the counter.
