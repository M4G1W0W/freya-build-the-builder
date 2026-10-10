# Diff review of 3a55e6d..a3e6c77, 2026-10-10 ~17:50 UTC

4 adversarial lenses (code, prompts, generalisation, runtime) with a skeptic each. Fixed in the commit after this file: 1, 2, 3, 4, 5 (in part: notes never on a transfer that is or must be), 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 19, 20. Open: 13 (engine_fields typed as strings), 17 (EVERY DAY capped at 8 weeks), 18 (Freya calls after the model budget), 5 (a mandatory band transfer with notes: finalize keeps only the event row's queue).

**Defect list (ranked by severity)**

Shared root cause: commit e233cb8 takes the note rows out of the negotiate ENDINGS (render.py:42-43). Defects 1, 2, 3, 5, 9 and 11 come from that change.

---

**1. HIGH: the NOTES line tells the model to say goodbye before each note, then tells it to note "BEFORE any goodbye"**
- Where: src/freya_builder/render.py:233-237 builds `says` from rows[rid]["say_before_end"] with no filter. The contradiction is at render.py:239-251. The rows come from _note_rows at render.py:47-65.
- Repro: render tests/fixtures/spec_variant_r.json with tests/fixtures/briefs/variant-r.openapi.json.
  - The negotiate task contains: `paid: say "Thank you. Goodbye."; refused: say "Thank you. Goodbye."; ... service_error: say "The promise could not be recorded." "Thank you. Goodbye."`
  - It is followed by: `After every product is settled and BEFORE any goodbye ... call add_note_pN`.
  - In a 3-product call where P1 is paid or disputed, the agent says goodbye in the middle of the call. The kit simulator persona then replies "Thank you, goodbye." and stops. P2, P3, add_note and close_call never run, so the ledger fails.
  - ev_notes and ev_notes_p add another GOODBYE on top.
  - This depends on extraction. runs/dev/spec-variant-r-dcb3915.json has a goodbye in 16 of 16 rows. Brief A rule 47 has the same clause, although spec_a happened to extract without it.
- Fix: in `says`, drop closing lines: sentences shared by every row or by the promise row, or that match /goodbye|thank you for your time/i. Keep only sentences specific to the row. Add a test that renders spec_variant_r and asserts the NOTES line contains no "Goodbye".

**2. HIGH: notes have two timings, and the note_post hook orders a goodbye plus an ENDING that no longer exists**
- Where:
  - render.py:239-251 says both "then note it with that reason" and "After every product is settled and BEFORE any goodbye".
  - hooks.py:741-746 (note_post SUCCESS) is unchanged.
  - The add_note description at render.py ~455 says "CALL it only as the last step".
- Repro: render spec_a with notes.used=True against the kit openapi.
  - Two products. The customer says P1 is already paid, and P2 has not been discussed. The model notes P1; Brief B rule 9 also pushes this.
  - P2 has no record, so the notes-done route does not fire.
  - note_post then returns: "Otherwise your next message must say the closing lines and goodbye ... call the transition tool of the matching ENDING". Negotiate only has [ev_notes_p, ev_notes, ev_promise, ev_transferred_*], so the result is a goodbye mid-call (P2 is lost) or a wrong ev_promise.
  - Second path: P1 is noted early, then P2 asks for a payment plan and gets a transfer. A transfer after a note breaks Brief B rule 10 ("no notes at all, before or after it").
  - Not yet measured in a simulation.
- Fix: defer notes.
  - Remove "then note it with that reason". The model says the sentence, remembers the reason, and writes notes only after every product is settled and only when no transfer happens.
  - Rewrite note_post SUCCESS: "Note saved. If another product still needs a note, call its add_note tool now; otherwise continue with the next unsettled product; do not say goodbye. The call closes by itself once every product has a promise or a note."
  - Align the add_note tool description with this.

**3. MEDIUM: notes variant has no legal way to end refused before the attempt ladder runs out**
This covers "says twice they don't want to talk" and bands with 0 attempts.
- Where:
  - render.py:42-43 (no_promise_refused is dropped from negotiate).
  - render.py:241-243 ("a refusal only after that product's last listed attempt was refused").
  - render.py:255-263 (ATTEMPTS: each refusal leads to the NEXT attempt).
  - render.py:282 ("close ... at once").
- Repro: render spec_ab (spec_a with max_products=3 and notes.used=true).
  - The ENDINGS are promise and transferred_restructuring/human/support. "twice" appears nowhere in the task.
  - Late-band P1, P2 not started: "I don't want to talk about this." The agent makes attempt 1. "I said I don't want to talk."
  - Brief A rule 45, variant C rule 48 and variant R 4.10.7 say to close refused. The task instead pushes the full ladder on every product, up to 5 offers, so the judge fails the policy check.
  - spec_variant_r and spec_variant_c behave the same.
- Fix: change the clause to: "a refusal when that product's last listed attempt was refused, when it has no listed attempt, or when a brief rule ends the call as a refusal (e.g. the customer repeatedly declines to talk): then note every unpromised product refused". Or append each dropped row's trigger to the NOTES line.

**4. MEDIUM: NOTES opens with a rule the brief may not have: "a product without a promise gets a note"**
- Where: render.py:239-251. Later in the same paragraph it says "only where the brief requires a note", which contradicts the opener.
- Repro:
  - The opener is printed for every spec with notes.used. It is Brief B rule 8 hard-coded, against CLAUDE.md rules 3 and 11.
  - The spec has no field saying which products need notes.
  - Take a hidden brief that uses add_note only for disputes, with one product, and a customer who refuses. The model is told to note it refused.
  - kit/tools/score.py:24 compares notes exactly, so the extra note fails the ledger.
- Fix: drop the opener and keep only "the call closes by itself once every product has a recorded promise or a note". Move rows into _note_rows only when the brief notes every unpromised product. Otherwise keep the ending for reasons the brief does not note.

**5. MEDIUM: a transfer the band requires is skipped; NOTES pushes notes and the notes-done route closes as the default row**
- Where:
  - render.py:239-243 (the opener with no condition).
  - render.py:282 ("only after the customer has described that situation").
  - render.py:471-477 (the notes-done transitions come first).
  - sandbox/facts.py:577 (MANDATORY TRANSFER).
  - facts.py:757 (finalize checks only rows[event_row].queue).
- Repro: tests/fixtures/spec_variant_c.json with P1 70 days late (senior band, 0 attempts).
  - variant-c.md:85 rule 33 says: transfer to collections_senior, no notes.
  - FACTS shows "tools: create_promise_p1, add_note_p1" and "MANDATORY TRANSFER: end with transition_to_ev_transferred_senior".
  - The customer refuses, and the prompt says to note it. Once every product is noted, the notes-done route fires and ev_notes runs no_commitment_refused, which has no queue.
  - The call closes no_commitment/refused with notes instead of transferred/senior.
- Fix:
  - Make NOTES conditional: "unless the call will be transferred (a MANDATORY TRANSFER in FACTS or an accepted transfer)".
  - Exempt transfers that FACTS makes mandatory from the "described that situation" sentence.
  - Guard the notes-done route: skip it, or have finalize keep the band's transfer_row, when any slot's band has a transfer_row.

**6. MEDIUM: the system cut-off bullet says to act on a partial date or amount; PARTS says to wait, using that same kind of message as its example**
- Where: render.py:160 (system bullet), render.py:280 (negotiate PARTS), render.py:222 (identity).
- Repro: kit `--style pieces`.
  - "I can pay four hundred and": the system bullet says act on 400, PARTS says "Please go on." If the floor is at most 400, the agent reads back the wrong amount, and the repeat counts as another offer. If the floor is above 400, it uses up the one floor offer early (rule 27).
  - "Monday the": the system rule picks next Monday, PARTS waits for "26th". Commit 96c37ad fixed PARTS but did not change the bullet.
  - A partial date of birth can trigger verify_identity, which counts toward the 3 wrong answers.
- Fix: the system bullet acts only on a complete yes/no or on a value that cannot continue. A value ending on "the", "and", a number word or a month is a part, and the step's parts rule applies. Keep one definition of "complete".

**7. MEDIUM: "transfer or close at once" overrides the brief's hardship-first rule when hardship and restructuring come together**
- Where: render.py:282 (557161d). The spec_a transferred_restructuring trigger has no precedence clause.
- Repro: Brief A negotiate task, verified customer: "I lost my job last month, can you lower my instalments?"
  - The restructuring trigger matches, while the support ending needs acceptance. "Do it at once" pushes an immediate restructuring transfer.
  - Rule 32 ("comes before rules 30 and 41") expects sympathy and a support offer, ending in transferred/support or no_promise/hardship. Both the ledger and the policy check fail.
  - The variant C and R extractions kept the precedence only by luck.
- Fix: append "...unless a brief rule says another situation the customer also described comes first; then follow that rule first". Or append the precedence wording to transfer rows that another rule outranks.

**8. MEDIUM: a repair call that runs out of budget or models crashes the build and throws away the valid best spec**
- Where:
  - pipeline.py:153-170 (the repair chat_json has no try).
  - llm.py:111-112 (re-raises the last model's ModelUnavailable).
  - llm.py:129-132 and 152-154 (left<20 raises LLMError).
- Repro:
  - Stub pipeline.chat_json so the first call returns spec_a with default_rows.opening='nope' and the repair call raises LLMError; set budget_left=400. The output is "CRASH LLMError repair policy spec (round 1): build time budget used up", while `best` holds a valid spec.
  - Real path: REPAIR_MIN_S=300 and CALL_TIMEOUT_S=240. Model 1 stalls for 240 s. Model 2 gets about 60 s, against 57-78 s for a typical call. Model 3 sees left<20. cli.run returns 1 with no agent.
- Fix: wrap the call as `try: ... except LLMError as e: trace.warn(...); break`, so the final check and the best-spec deploy still run. Optionally set REPAIR_MIN_S to at least CALL_TIMEOUT_S plus one normal call.

**9. LOW: the ACCOUNT NOT AVAILABLE facts name an exit tool that was removed, so the call cannot close**
- Where: codegen.py:110-114 (_unavailable) against render.py:42-43; facts.py ~608-609 and 669-671.
- Repro:
  - _unavailable(spec_variant_r) returns "...end with transition_to_ev_no_promise_refused". variant_c names no_commitment_refused, and A+B behaves the same. None of these are negotiate transitions, because the default row is a note row.
  - This path is reached when get_account fails, ok is false, the product list is empty, or account_main raises.
  - Every p<k>_id is then none, so notes-done cannot fire. The only exit is the 120-turn cap, and close_call never runs.
  - The new test checks task_message, not account_facts.
- Fix: exempt default_rows.negotiate from the note-row filter in _rows_for. Or route ev_<default> in code when account_status != ok, and stop naming a tool in _unavailable.

**10. LOW: close_reason is never set for rows with an empty reason; a required reason, or engine_fields that use {{close_reason}}, get dropped or sent literally, and the checks pass**
- Where:
  - spec.py:229-237 (engine_sent always counts reason_field as sent).
  - spec.py:225 and 259 (LATE_VARS are allowed in engine_fields).
  - facts.py:776-777 (only set `if chosen.get("reason")`).
  - codegen.py setup_config defaults; render.py:513-518.
- Repro:
  - (a) Set close_call.required=[customer_id, outcome, reason]. check_spec(spec_a)==[] and unsent_required(...)==[]. finalize with end_event='promise' and p1_recorded='yes' gives close_reason=None. The field is dropped (kit workflow-format.md:202, tools-and-code.md:115), so the bank rejects the close on promise and paid cases.
  - (b) Add a required 'summary' field with engine_fields value '{{close_outcome}} {{close_reason}}'. check_spec==[], and the bank receives the literal "promise {{close_reason}}".
  - The literal ev_ path sends '' instead, so the two paths disagree. {{xfer_queue}} on close_call is sent as the literal 'none'.
- Fix:
  - setup defaults close_reason to '', and finalize always assigns it.
  - engine_sent counts reason_field only when every row that can close has a non-empty reason; otherwise it reports the rows.
  - check_spec rejects {{close_reason}} and {{xfer_queue}} in mixed engine_fields values.

**11. LOW: the promise-failure hook tells the model to end as no_promise/service_error, which is no longer a negotiate ending in notes variants**
- Where: hooks.py:637-650 (FAIL_TAIL plus failure_rules.promise), with render.py:42-43.
- Repro: spec_ab with a second create_promise failure. what_to_do_next says "...end the call as no_promise / service_error". That ending has been removed, and the NOTES examples for spec_ab do not name service_error.
- Fix: when notes are used, the fail tail says "note this product service_error (add_note_pN) and continue with the other products". Or add service_error to the NOTES examples.

**12. LOW: engine_fields are merged last, so they override fields the engine owns; a redundant entry costs a repair round**
- Where: render.py:431, 522, 530, 564, 574 (`... | _engine_extra(...)`); spec.py:257-258.
- Repro:
  - engine_fields=[{close_call, outcome, 'no_promise'}] renders the finalize close with 'no_promise' instead of '{{close_outcome}}'. It is still deployed if the repair fails or is skipped.
  - {get_account, customer_id, '{{customer_id}}'} raises "the engine already sends this field".
- Fix: merge engine_fields first, so the engine's own values win. An entry equal to the engine's value is not a problem.

**13. LOW: engine_fields values are always declared as strings, and their type is never checked (impact unverified)**
- Where: toolapi.py:190-192 (engine_call); spec.py _engine_field_problems.
- Repro: a required integer close_call field 'attempts' with value 'abc'. check_spec==[], and the body declares {'type':'string','default':'abc'}. Model-run tools keep f.type through _leaf. Whether the mock bank rejects the wrong type has not been checked.
- Fix: pass the Field type into engine_call and emit typed defaults. Check that a literal parses as the declared type.

**14. LOW: the PARTS example is a Brief A practice-case value ("Monday the 26th", from PUB-07, a Brief A holiday)**
- Where: render.py:280.
- Repro: see kit/public-test-set.json:288 and kit/briefs/brief-a.md:53; commit 96c37ad names PUB-07.
  - This is against CLAUDE.md rule 11 and can inflate the PUB-07 measurement.
  - The example also pairs a weekday with a date, which the next sentence forbids.
- Fix: use a neutral example with no weekday-date pair (for example "the", then "fifth").

**15. LOW: the loop breaker and the parts rules give different replies to a second incomplete piece**
- Where: render.py:160 against render.py:222 and 280.
- Repro: DOB "the fourteenth of" gets "Please go on.", then "March, nineteen".
  - Identity says "Please go on."; the system bullet says "Sorry, your message was cut off. Could you answer in a few words?"
  - A restated answer can then be joined with the earlier fragments.
- Fix: make the loop breaker the parts rules' second step, and state that a restated full answer replaces the earlier parts.

**16. LOW: the new floor line is printed when the product has no floor**
- Where: sandbox/facts.py:536-544.
- Repro: spec_a plus {api_value: overdraft, floor_field: '', floor_percent: 0}, 6 days late. FACTS reads "offer exactly the floor not available on 2026-10-16 ...; this IS attempt 1". This needs a spec deployed with a check_spec problem (spec.py:411), or a null floor in the returned product.
- Fix: add `and floor is not None` to the condition at facts.py:536.

**17. LOW: the EVERY DAY table stops at 8 weeks while the table can run to today+134 days; the prompt forbids weekdays from memory**
- Where: facts.py:281-296 (`for _ in range(8)`), facts.py:300-315 (_table_end), render.py:281.
- Repro: with a promise window longer than 8 weeks, valid business days past week 8 have no weekday row. FACTS gives weekdays only for the window bounds and non-business days.
- Fix: loop until start > _table_end, with a size cap tied to it.

**18. LOW: the 25-minute budget only limits model calls; the Freya calls after it can push the run past 30 minutes**
- Where: llm.py:22 (BUILD_BUDGET_S), cli.py:119-177; kit/freya.py:17 (urlopen timeout 120 s, no budget check).
- Repro: model stalls use about 25 minutes. Then dry-run, save/publish, the smoke test (2 chat calls, 5 s sleep, chat/end) and export can each take up to 120 s.
- Fix: track a wall-clock deadline for the whole run in cli.py. Below a threshold, skip the smoke-test retry and sleep. kit/ cannot be edited, so check the budget before each Freya call.

**19. LOW: the RUNBOOK step 4 commit check can never pass, and re-running with tee reports dirty=True**
- Where: docs/RUNBOOK.md:64-65 against 70 and 77; cli.py:96-106 (code_version).
- Repro:
  - Step 5 commits the traces and submission. Step 6 then sets commit = HEAD, which is the new commit, so it never equals the trace's git=.
  - Once traces/hidden-N.log is tracked, `| tee traces/hidden-N.log` truncates it before `git status --porcelain --untracked-files=no` runs. The run reports dirty=True and the "uncommitted changes" WARN with clean code.
- Fix: check that the trace's git= is the parent of the submission commit, or that `git diff <git=> HEAD -- src builder` is empty. Scope code_version to `-- src builder pyproject.toml`.

**20. LOW: the RUNBOOK spec-check grep misses "spec check (final): PASS"**
- Where: docs/RUNBOOK.md:44; pipeline.py:171-172.
- Repro: rounds 1 and 2 fail and the second repair fixes the spec. The log says "(final): PASS", the grep prints nothing, and a good build looks failed and gets re-run (2-25 min).
- Fix: `grep -E "TEST +spec check \((round [0-9]+|final)\): PASS"`.

---

Dropped as refuted: "Floor offer: the ATTEMPTS parenthetical has no scope, while the new FACTS line applies only 'before your first offer'".
