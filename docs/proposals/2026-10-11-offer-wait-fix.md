# Proposal (NOT implemented): never repeat a pending offer after small talk or a cut-off

Status: design only (design agent, 11 Oct ~09:15 UTC), for the user's decision. Base: G1 83f8263. Trigger: M4 r3 PUB-06
talkative (call 3f5a442c), agent-caused, which blocks G1's promotion under binding condition 1. Brief A rule 26: "offer
the floor, once".

## 1. Evidence
Same pattern in every failure: the floor is offered once (with its note); then a message holds **no reply** (complete
but only chatter, or a fragment) right after "Please go on." or the cut-off line; the model has no third kind of reply
and re-asks the offer.
- 3f5a442c (G1 fresh, M4 r3): J11 "My cousin's wedding is on the 30th" -> J12 "I'm sorry, I don't have any information
  about your cousin's wedding. Would you like to make the payment of 637.50 on Friday...?" (offer repeated without the
  overdue note; rule-44 line used on a statement).
- bfe80eb8 (G1): after the cut-off line, a whole small-talk sentence -> "Can you make the payment of 637.50 on Friday...?".
- e5d24c34 (F2): small-talk-only messages at 30.5 s, 39.0 s, 43.6 s each -> "Can you make the minimum payment of 637.50 today?".
- 704c184a (F2): one-word fragment "thought" -> "not sure I understand. Would you like to make the minimum payment...?".
- The "passing" 2d7141d4 (M4 r1) is not clean: at 87.3 s a leaked simulator line got "I need to know if you can make
  the payment of 637.50 on Friday... Do you confirm?" (a re-offer the judge passed). Pass rates understate the defect.
- M3 PUB-06 calls (2f322b2c, d8854a6f, 54624750) never reach this path (the customer answers right away).
Root cause: the ATTEMPTS clause (render.py:281-284) covers only "a first reply to an offer that is only small talk";
nothing covers the 2nd or later. The cut-off alternation (:193) does not fit a complete message; the rule-44 line
(:199 "If you are asked something...") is read as "respond to anything I can't place". facts.py needs no change.

## 2. Change (render.py only; generic)
**E1 (HOW TO WORK, :199, global):** `- If the customer asks a question or asks for information that the brief and the facts do not answer, say that you do not have that information. Never say it to a remark that asks for nothing.`
**E2 (new negotiate-task line after PARTS :304, always rendered):** `WAITING: after your question or offer, until the customer answers it, a message with no reply to it is not an answer, a refusal or a non-answer: small talk or a remark about something else (it says nothing about paying, money, the debt, your offer or this call, and describes no situation a brief rule names), or a cut-off message without a reply. However many such messages come in a row, reply only "I see. Please go on." (to a cut-off one, use the cut-off rule in HOW TO WORK): never repeat the offer, its amount or its date, never ask again whether they can pay, and add no sympathy. If the customer asks what you offered, say what you offered as a statement (the same amount, date and required sentences) without asking again. A yes, a no, a date, an amount, "too much", a reply about paying with none of these (such as "I don't know"), a question or a situation is handled with the brief and FACTS as usual.`
**E3 (ATTEMPTS clause :281-284; keeps tested substrings):** `(not answering is a complete reply about paying with no yes, no, date or amount, such as "I don't know"; a cut-off message that holds no yes, no, date or amount is no reply, and neither is small talk (see WAITING): such a message uses no attempt)`
Render conditions: E2 always (offers exist without attempts); must not contain "ATTEMPTS:" (test :150). E3 only when
spec["attempts"]. Opening, third-party and identity tasks untouched (the identity fix is separate).
Restating on request: the brief is silent (rules 26, 31, 44): chose the safer judge reading, restate only on an explicit
request, as a statement without a new question.

## 3. Risks
1. Real non-answers read as small talk ("we'll see", "things are hard") -> no attempt used, stall (guard: PUB-09 talkative).
2. Hardship/restructuring inside chatter swallowed (mitigated by "describes no situation a brief rule names"; guards PUB-05/09).
3. A never-answering simulator loops on "I see. Please go on." until the negotiate cap or a hang-up (accepted).
4. A requested restatement may still be judged a 2nd offer (optional asks_back arm).
5. E1 is global: a statement-form request may lose its rule-44 answer ("asks for information" covers it).

## 4. Tests
- `test_prompts_handle_customer_speech_styles` (test_render.py:360): add `"a first reply to an offer" not in nego`;
  `'However many such messages come in a row, reply only "I see. Please go on."' in nego`; `"never repeat the offer, its
  amount or its date" in nego`; `"If the customer asks what you offered" in nego`; `"WAITING" not in ident`; keep
  `"uses no attempt"` and `"a cut-off message that holds no yes, no, date or amount is no reply"`.
- `test_negotiate_has_no_attempt_procedure_without_an_attempt_plan` (:150): add `"WAITING:" in task`.
- New `test_unknown_information_answers_questions_only`: `"Never say it to a remark that asks for nothing" in system`;
  `"If you are asked something" not in system`.
- Render scope (script): `--dry` G1 vs patch on spec-a-llm, spec-raw-w, spec-ab1-w, variant-C: only the system prompt
  and negotiate task_message differ.

## 5. Matched measurement (saved spec, so only the prompt changes)
Treatment: branch off the promoted base (G1 or cand-id), `--spec runs/dev/spec-a-llm.json` into new slot exp-g1w-a;
export check vs exp-g1-a (only system prompt + negotiate task differ).
- Primary (12 calls): PUB-06 talkative, 6 reps per arm, interleaved; score strict passes AND a deterministic transcript
  count of re-offers (agent turn after the first floor offer and before the read-back naming the floor amount or asking
  again whether they can pay, unless the customer asked what was offered) and of rule-44 lines to non-questions.
  Adopt only if treatment has 0 re-offers, 0 rule-44 misuses, 6/6 strict, and >= 8 no-reply messages after an offer
  across its 6 calls (else +3 reps per arm).
- Guard 1 (30): styled-a x3 on treatment vs M3 (10/10); any newly failing case re-run x3 on both arms and classified.
- Guard 2 (6): o1-a PUB-09 ("refuses attempt 1, accepts attempt 2") talkative x3 per arm.
- Optional (6): PUB-06 asks_back x3 per arm (restatement).
Totals: 48 core (54 with optional), cap 78 with contingencies; ~20-30 min. Brief B: re-check on the next A+B build.
