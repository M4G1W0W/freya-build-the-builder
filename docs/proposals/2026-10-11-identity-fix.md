# Proposal (NOT implemented): identity-stage fix for I1 (cut-off answers) and I2 ("why do you need that?")

Status: design only, written overnight 11 Oct ~02:15 UTC by a design agent, for the morning review (the plan allows at
most one generic change 09:00-12:00). Base: W = cand-g1 83f8263. Evidence: `runs/dev/r4/analysis-m1.md`,
`analysis-m2.md`, `analysis-identity-history.md`. Regression cases: `tests/fixtures/cases/identity-rd.json` (R1/R2 real
declines -> not_verified/declined; R3 "Why do you need that?" before each answer -> promise; R4 two wrong DOBs then right).

## 1. Root causes (file:line in WG1 = 83f8263)
I1 (complete answer not sent; cut-off loop never ends):
- Completeness is left to model judgement: `render.py:193` (system prompt HOW TO WORK) "A value that may still go on (it
  ends on "the", "and", a number word or a month) is only a part" -> a year said in words counts as a part (79778b2e J7).
  Same input handled differently across calls (d10044ef J11 "21 July 1990. Look, I" -> "Please go on."; b20818a2 sent it).
- The question line never defines complete: `render.py:250` renders only `answer format: date`; `:255` "as soon as
  together they make a complete answer".
- No end state: `:193`/`:255` define only "Please go on." then the cut-off line, then back. `:255` "never ask the whole
  question again for it" and `:193` "Never repeat a question ... because a message was cut off" forbid the one move that
  worked (next message complete after "Please go on." 0/55; after cut-off line 2/21; after a question 2/5).
- Silent exit: identity node `render.py:436-451`, `max_turns=CAPS["identity"]=40` (`:19`, `:449`) ->
  `max_turn_target=ev_{default_rows.identity}` (`:450`) = `ev_not_verified_declined` (silent api_node, `:579-581`,
  `nodes.py:87`).
- Ledger effect: the bank counts only submitted answers and `hooks.py:506-510` says "You may ask that same question
  again", so an unsent answer gives a 4th try (d10044ef: the true DOB -> promise recorded; expected not_verified/failed).
- A fragment ("I have already told you. Just tell me", 79778b2e J11) counted as the 2nd refusal.
I2 (question back counted as refusal): `render.py:257` "If the customer asks a question back (why you need it, what the
call is about) or does not want to answer, explain once" groups "why you need it" with the brief's decline events; the
declined ENDING trigger (rendered from the spec row, `render.py:76-85`) "a second question about the call instead of
answering" then matches it (68d28036 J7).

## 2. Smallest change: prompt only, inside `_identity_task` (render.py:247-260); system prompt unchanged
A1. Completeness test per question, from the spec's answer format (new helpers `_complete_when(fmt)`, `_short_ask(q)`):
`{n}. {ask} (send {qf}={key}; answer format: {fmt}; complete when it has {C}; short question: "{ask} Just {W}, please.")`

| format | C | W |
|---|---|---|
| date | a day, a month and a full year | the day, the month and the year |
| year | a full year | the year, all four digits |
| digits:N | N digits | the N digits |
| alnum / text / unknown | the whole value, followed by a full stop or by more words | the answer |

If any question is date/year, also: "A full year is four digits, in figures or said one by one, or a year in words
followed by a full stop or by more words (a year in words at the very end of a message may still go on)."
A2. Replace the part/"Please go on." sentence in `:255` with:
> join the parts the customer gave since the last verify_identity result; if they correct a part, use the corrected part.
> COMPLETE: an answer is complete when it passes its "complete when" test above, whatever follows it in the message (a
> full stop, a complaint, a question, or words that break off). CALL verify_identity with it at once, before you reply to
> the rest. Only if the words right after it correct it ("sorry", "I mean", "no", "wait", "actually") use the corrected
> value; while that correction is cut off it is a part. In this step these tests decide what is complete, not the word
> list in HOW TO WORK; if a rule below says what to do with an incomplete answer, do that.
> CUT-OFF: count the customer's messages since you last asked a question that hold no complete answer. After the 1st
> reply "Please go on."; after the 2nd, the cut-off line from HOW TO WORK; after the 3rd, ask that question's short
> question (this starts the count again). In this step this replaces the HOW TO WORK rule against repeating a question;
> otherwise never ask the whole question again for a part.
> If the customer says they already answered, look at their messages since the last verify_identity result: if one holds
> a complete answer you did not send, CALL verify_identity with it now. Never send the same answer twice.
B. Replace `:257` with:
> If the customer does not want to answer, or asks what the call is about instead of answering, explain once: {X} Do not
> repeat the security question in that message; they answer next. Only these count toward an ENDING for declining, and
> only as its trigger says. Any other question back (for example why you need it, or whether this is safe) is not a
> refusal and never ends the call unless an ENDING trigger names it: answer it in one short sentence (to "why do you need
> it", say {X}) without repeating the security question, and wait for their answer. A complaint, "I already told you" or
> a cut-off message is not a refusal either.
Why prompt-only: the model calls verify_identity itself; hooks run only on tool calls, so no code node sees the raw
customer message first. A deterministic alternative (extracted answer variable -> api_request node) is a redesign.
C (optional, separate graph change, recommend leaving out): spoken line on the identity cap exit via a `cap_identity`
code node with tts (reuses the ev_notes pattern, `render.py:510-523`); cap still closes as declined (no ledger change).

## 3. Risks; tests that change
- A1: a complete answer about to be corrected gets sent and costs a wrong answer (correction-word exception limits it;
  a correction after a pause is missed). A message ending on a 2-digit year now goes through the cut-off count.
- A2: the judge may count the short question as asking again (PUB-12 "date of birth not asked again"); it fires only
  after 3 incomplete messages in a row. Precedent: a1499a8 re-asked on the 2nd cut-off (negotiate) and was reverted in
  557161d. The "already answered" rule could double-send (guarded).
- B: a real 2nd refusal phrased as a question ("why should I?") may no longer close (40-turn cap still closes declined;
  judge may object); repeating the explanation may read as explaining twice. Two "what is this about" still close.
- Tests: `tests/test_render.py` `test_prompts_handle_customer_speech_styles` (~:385-394) asserts change; with C,
  `test_turn_caps_end_on_the_stage_default_row` (:133-136).

## 4. Test plan
Unit: format-specific renders (spec_a: "a day, a month and a full year", "4 digits", `Just the 4 digits, please.`;
variant-c: "a full year", "5 digits"; alnum fallback; full-year sentence absent without date/year); cut-off count
sentences; I2 sentences, old grouping gone; render all fixture specs + a `--dry` raw-a build.
Matched simulation (saved spec `runs/dev/spec-a-llm.json`; control exp-g1-a; treatment new slot exp-i12-a, exportdiff
first):
| Block | Arm | Cases x reps | Calls |
|---|---|---|---|
| 1 gate | treatment | identity-rd R1, R2 x3 (stop if any is not declined) | 6 |
| 2 target | both, alternated | PUB-03 corrects, PUB-03 in_words, PUB-04 asks_back, PUB-09 asks_back, R3 x3 | 30 |
| 3 guard | treatment | styled-a 10 x3 | 30 |
Ship if: block 1 6/6 declined; block 2 treatment strict 3/3 wherever control is 3/3 and no I1/I2 signature
(`classify_failures.py`); block 3 no new identity-stage failure class. Power is low (control passes PUB-03 corrects 3/3
~34%), so also count I1 signatures per call. PUB-13 asks_back (B) needs an A+B agent.
