> **Adopted 2026-10-10 ~14:50 Istanbul** (design panel: 3 proposals, 2 judges, 1 synthesis; workflow run
> `wf_43cc02df-5b3`). The panel's text follows unchanged except for these **amendments**:
> - **Builder LLM:** OpenAI `gpt-6.1-sol` with fallbacks, through `src/freya_builder/llm.py` (strict json_schema). The
>   Claude-specific notes in §2 do not apply.
> - **Phase 1 LLM front end:** a single extraction pass plus all the deterministic checks (quotes, numeric coverage,
>   enums, grid invariants, worked examples). Two-framing and 3-vote (S4–S6) are added **only if E10 shows drift**.
>   exp02/exp03 showed identical outputs on repeated runs for every candidate model.
> - Already built and tested: `toolapi.py`, `sandbox/calendar_core.py`, `sandbox/flatvars.py`, `nodes.py`, `validate.py`,
>   `trace.py`, `llm.py`, `cli.py`, `platform.py`, `builder/build.py`, plus fixtures variant-c and variant-r.

# Builder design v1: staged graph with facts and bookkeeping in code and rules in the prompt

Status: recommended design, Sat 10 Oct 2026. It replaces the three proposals. Tags: **[V]** means verified in exp01 or in the kit's working builder. **[D]** means documented in `kit/docs` but not verified by us. **[U]** means undocumented and gated by the named experiment (Section 6).

## 1. Decision

**Use Proposal 3 as the backbone, with targeted grafts from Proposals 1 and 2.** Proposal 3 is "facts in code, rules in the prompt", a small staged graph grown from the organiser's base workflow.

**Why Proposal 3.** Both judges ranked it the most feasible (8/10 and 7/10). It was also the best at generalising (7 and 7.5):
- The whole brief stays in front of a model that can act on rules nobody modelled.
- Nothing structural needs patching after Sun 17:00 UTC.
- It reuses mechanics we already verified: exp01, `flatvars.py`, `calendar_core.py`, `toolapi.py`, `validate.py`, `trace.py`.

**The fatal flaws the judges found, and how this design removes them:**

| Flaw found by the judges | Fix |
|---|---|
| The close outcome is picked by the model (Brief B aggregation, p³ erosion) | Exit events plus a `finalize` code node that computes outcome and reason from a ledger mirror and a brief-derived precedence list (from P2/P1). |
| `verify_identity` can be reached while a relative is on the line (a hard fail in `score.py`) | A separate **opening** node with an enum fork and no tools (from P2). |
| `close_call` races, and `wrap_up` relies on an unverified entry turn | Use the exp01-verified pattern: the model says goodbye and fires an exit in the same message, then the close is engine-run [V]. |
| Parallel writes and invented product ids | **Per-product tool slots**, each with its `product_id` baked from code. |
| `response_mapping` on `api_request` nodes does not work (exp01) | Read the flattened node-named keys instead [V]. |
| The LLM layer was mis-specified (temperature, forced tool use) | Strict json_schema through the existing client. We make no "temperature 0" claim. |

**Rejected:**
- **Proposal 1's code brain.** Feasibility was 3 and 2.5. It loses mixed-intent turns. Its regex date parser breaks on `in_words` customers. Its vocabulary cannot be extended after 17:00.
- **Proposal 2's planner, oracle, critic loops and unrolled product nodes.** Feasibility was 2.5 and 2, and organiser reruns would drift.

**Kept from the runners-up:**
- From P1: sentinel initialisation, self-tests on the exact deployed strings, enum cross-checks, a coverage map, and hashes in the trace.
- From P2: the opening fork, the code-composed disclosure TTS, exit-event aggregation, the labelled date table, memo values bounded by date, code-list maps, detection of the verify shape, quote-verified rules, and the build-twice reproducibility check.

Judge 1 estimated this hybrid at about 6.5/10 hidden cases at 3/3, against 5–5.5 for any proposal as written. One paragraph goes into `docs/hackathon_notes.md` → Decision log when this is adopted.

## 2. Builder pipeline

**Command.** `python3 builder/build.py <brief path(s) or dir> <tool_api.json>`. It is stdlib only, like `freya.py`.
- The last argument is the tool API.
- A brief can be one file, several files (A then B), or a directory. A directory is read in sorted order: .md, .txt, .eml, .csv, .json and .html.
- Secrets come from env (`FREYA_API_KEY` and the builder LLM key) and are never printed.
- Every intermediate result goes to `runs/<ts>/`: inputs, rules, raw and voted specs, workflow, test report.

**D2, the builder LLM.** There is one thin module, `src/freya_builder/llm.py`, with strict json_schema output and `additionalProperties:false`.
- The default is the Decision-log choice of 10-10 14:40: gpt-6.1-sol with fallbacks, benchmarked 11/11 with identical outputs.
- Switching to Claude is a change to that one module. Re-run `exp03` on the final schema before switching.
- If we switch to Opus 5.5, the judges report it takes no temperature, rejects forced tool_choice, and needs `output_config.format` json_schema with an explicit effort. **These come from the judges' reading and are not verified here. Re-check them in the claude-api reference first.**
- The served model id and a sha256 of each output are logged.

| Step | Kind | What it does |
|---|---|---|
| S0 | det | Trace START: UTC time, git commit and dirty flag, sha256 and size of each input, builder model ids. |
| S1 | det | **Load the brief.** Split into documents on file boundaries and on mail and memo headers (`From:`, `Subject:`, `Date:`, `MEMO`, `Annex`, code-list headings). Parse tables (pipe, CSV, `CODE - meaning`). |
| S2 | det | **Parse the tool API** (`toolapi.py`, exists): server URL; per tool the request leaves (type, enum, format, description, required) and the 200-response tree including array items. Assert the 7 tool names; they are a kit fact. Derive the *product-scoped* tools: write tools whose request has a field with the same name as the `get_account` item id field. |
| S3 | LLM-1 | **consolidate**: "consolidate brief documents, apply amendments, map code list". Output schema: `source.*` in Section 3. Deterministic checks: (a) every `quote` is a whitespace- and case-normalised substring of its document; (b) every number, date or time token in the source appears in some rule quote, otherwise one retry with the misses, then a warning; (c) every `code_map.api_value` is in its API enum. |
| S4 | LLM-2a and 2b, in parallel | **policy x2**: "extract date/amount policy (two framings)". 2a reads the consolidated rules; 2b reads the raw text plus the amendment list. Output: `policy.*`. |
| S5 | det | **Policy N-version check.** AST-whitelist every expression, then evaluate both versions on a grid: every day for 8 weeks from the brief's example `now` (or the build date), times {09:00, 11:00, 18:30}, times each API product type, times `days_late` at every band edge ±1. Compare deadlines, attempt dates and amounts, floors, valid windows and callback slots. If they differ, **LLM-2c** "adjudicate policy disagreement" gets a diff table plus quotes, and the grid runs again. Invariants: the deadline is ≥ today and a business day; attempt dates are inside the window; floor ≤ past_due; callback slots are inside the window and later than `now`. |
| S6 | LLM-3 x3, in parallel | **design**: "design call structure: opening, identity, outcome rows, precedence, stage tools". Output: `design.*`. Canonicalise (sort, ISO, lower-case enums), then take a field-level majority. Prose fields must be verbatim quotes (substring-checked) or are composed by code templates. A three-way tie goes to **LLM-4** "adjudicate design field". |
| S7 | det | **Validate the spec against the ToolModel** (see the list after this table). Errors go to **LLM-5** "repair spec from validator errors", at most 2 rounds. If an optional part still fails, it is marked `DEGRADED`: the rule stays in the prompt and gets a trace line. A failure in a core part (bands, identity gate, rows) is a hard error with a non-zero exit. |
| S8 | det | **Render** the workflow (Section 4). Code nodes are sandbox modules + `CONFIG = hex_json(spec)` + main (`sandbox/__init__.py::assemble`, exists, rejects double braces). |
| S9 | det | **Self-tests T1–T9** (below). A failure is a loud warning, except T7 and T8, which block the deploy. |
| S10 | net | `freya.validate_workflow` (dry run), then `freya.save_workflow(slot=<brief stem>)`, which updates in place and publishes. Then GET the workflow back and diff its structure (tools, pre_actions, hooks, transitions present). Then a chat smoke test: send "Hello?", expect the opening line with no literal `{{` and no forbidden pre-verification words, then `/chat/end`. Per api.md, chat may skip the initial code node. |
| S11 | det | `freya.export_workflow` → `submission/<stem>.workflow.json`, then trace END. |

S7 checks:
- Every outcome, reason, queue, note reason, identity key and product type used is in its API enum. A free-text reason must be in the brief's table.
- Every required request field of every tool has a binding.
- Response roles name real fields of the right type (boolean or integer).
- The opening line uses only declared call variables.
- Every outcome in the table has a row, and the precedence refers to existing rows.
- Every active rule id is in `coverage` or in `unmodeled`.

**Self-tests:**

| Test | What it checks |
|---|---|
| T1 | Tool and field inventory, plus the bindings. |
| T2 | Consolidation checks (S3). |
| T3 | Policy agreement (S5). |
| T4 | Policy invariants. |
| T5 | Every code-node snippet runs, as the exact deployed string, with a fake `vars` over at least 40 grid samples. The samples include synthetic flattened `load_account_response.data.<list>.<i>.<f>` keys built from the response schema (1–3 products), and a `now` on a weekend, a holiday, a Friday and a month end. Assert: no exception, and every variable a prompt, condition or body reads is set. |
| T6 | Every hook runs against synthetic results: ok true, ok false, a 500 envelope with `data` missing, and each hint value. Assert that `what_to_do_next` is set. |
| T7 | Lint. The kit checklist (`validate.py`), plus: no two transitions of a node share a target (the engine merges them); placeholders in spoken text ⊂ declared call variables; every `{{var}}` in prompts, TTS and bodies is initialised in `setup`; no code or extraction variable has the name of a model-filled default; every path reaches `hang_up`; no `{{` or `}}` in code. |
| T8 | The dry run passes. |
| T9 | The brief's worked examples (`policy.examples`) as date tests. |
| T10 | Optional, Phase 3 only. An outcome oracle: LLM-6 predicts outcome and reason for about 15 generated end-of-call scenario cards from the rules alone. The prediction is compared with the compiled `finalize`. It is never used as a date oracle. |

**Time.** About 6 LLM calls, typically 4–6 min. A soft guard at 15 min skips adjudication (2a and the plain majority win). A hard guard at 22 min deploys the last validated render. No simulations run inside the build.

**Trace format.** Plain text on stdout, run as `2>&1 | tee traces/<name>.log`. `trace.py` redacts `fak_*`, `sk-*` and the env key values.
```
[2026-10-11T17:05:02Z] START brief=hidden-2/ (4 docs) sha256=… tool_api=… sha256=… git=abc123 clean
[…] LLM #1 model=<id> served=<id> purpose="consolidate brief documents, apply amendments, map code list" in=6.1k out=2.3k 41.2s out_sha=…
[…] TEST T3 policy two-framing agreement on 1344 grid points: PASS
[…] DEGRADED rule R31 "…" not enforced by code; carried in prompt (stage negotiate)
[…] FREYA POST /api/v2/workflow?dryRun=true 200 0.8s
[…] CREATED workflow_id=… agent_id=… nodes=27 (conversation 4, code 18, api_request 3, end_call 1) bank tools: model-called 4 (+6 slots), engine-run 3
[…] END 2026-10-11T17:09:40Z duration=278s spec_sha=… workflow_sha=…
```

## 3. PolicySpec schema (v1)

Sources: **[T]** tool API (deterministic), **[B]** brief (via LLM), **[D]** derived by code. Every leaf from the brief carries `src_rule_ids`.

```
meta:     kind clean|raw [B1]; bank_name [B]; now_var [B]
          call_vars[{name, example, role: customer_id|now|addressing|other}] [B]
          (a customer_id-role name must equal a request field [T]; examples → test_variables)
source:   documents[{id, kind: spec|email|policy|memo|code_list|other, date}] [B1]
          rules[{id, doc, quote, topic, status: active|superseded, superseded_by, effective_from, effective_until}] [B1]
          code_map[{brief_term, tool, field, api_value}] [B1, api_value ∈ enum T]
          prompt_brief [D]
policy:   (Python expressions over the helper vocabulary, AST-whitelisted)
          calendar{business_weekdays[0-6], holidays[{date, from?, until?}], this_weekday, next_weekday: following_week|next_occurrence,
                   numeric_date_order: dmy|mdy|ymd}
          products{list_field [T], id_field [T], type_field [T], past_due_field [T], days_late_field [T]
                   (roles chosen by [B], names validated against [T]);
                   types[{api_value [T enum], label_template [B] e.g. "<kind> ending {card_last4}", floor_expr [B]}];
                   max_products [B, default 3 = kit README]}
          bands[{name, min_days, max_days, deadline_expr, attempts:int}]
          attempts[{n, bands[], amount: full|floor|<expr>, date_expr, condition: always|after_too_much|<expr>}]
          promise_window{min_expr, max_expr, business_days_only}
          callback{enabled, day_exprs[], start "HH:MM", end "HH:MM", inclusive, after_now}
          examples[{now, inputs, expect}]                      (only worked examples quoted in the brief)
design:   opening_line (quotes + {{call var}} only); confirm_criteria (quote); forbidden_before_verified[]
          identity{shape: per_answer|all_at_once [D from T], questions[{key [T enum value or field], ask [B], format: date|digits:N|year|alnum|text}],
                   gate{field [T boolean], value}, remaining_field [T integer or ""],
                   hints[{field, value [T enum], instruction, counts_as_wrong}], lines{failed, decline_explain} (quotes)}
          rows[{id, outcome [T enum], reason [T enum or brief table], phases[opening|third_party|identity|negotiate],
                trigger (<= 25 words), say_before_end[quotes], queue [T enum or ""]}]
          close_precedence[{when: transferred|promise_recorded|notes_all:<r>|notes_any|always,
                            then: event_row|row:<id>|first_note_reason_not:<r>:<outcome>}]
          default_row{opening, third_party, identity, negotiate}       (turn caps, an unresolved "done")
          notes{used, reason_field [T], on_transfer: bool}; stage_tools{third_party[], identity[], negotiate[]}
          disclosure{intro, product_sentence (template), first_ask_single, first_ask_multi}   (quotes and templates)
          success_lines{tool: quote}; failure_rules{tool: quote}
          bindings{tool: {field: call_var:<n>|slot_id|const:<v>|model|computed}}
          unmodeled[{rule_id, stage}]; coverage{rule_id: [spec paths]}
```

**Helper vocabulary.** Sandbox-safe, unit-tested, and the same file is embedded in the code nodes. It extends `calendar_core.py`:
- names: `today`, `now`, `p` (the product dict), `deadline`;
- `date(y,m,d)`, `add_days`, `add_business_days(d,n)`, `next_business_day`, `business_day_on_or_after` and `…_before`;
- `last_business_day_of_week`, `last_business_day_of_month`, `end_of_month`, `weekday_in_week(d,wd,k)`, `is_business_day`;
- `min`, `max`, `round`, comparisons, and `x if c else y`.

**`prompt_brief`.**
- `kind=clean` (spec documents only, including A+B): the original text verbatim, concatenated.
- `kind=raw`: the consolidated active rules grouped by topic, with amendments applied and codes replaced by API values. Then an "Amendments applied" appendix, then "Mandatory sentences (verbatim)". The raw text is never included, because it contradicts the memo.

**An amending memo.**
- LLM-1 marks the rules it supersedes, which are then dropped deterministically.
- A change "effective from or until a date" becomes a runtime condition in an expression (`12 if today < date(…) else 15`) or a dated holiday. This matters because hidden cases run on several calendar days.
- Two-framing extraction (S4 and S5) catches a memo applied in one reading but not the other.

**A code list.** It becomes `code_map` (brief term → API enum value), validated against the hidden `openapi.json`. Rows, prompts and the appendix use API values only.

**Unanticipated rules.**
1. They always reach the model, because `prompt_brief` is in the `system_prompt` of every node.
2. They are listed in `unmodeled` with their stage, and the trace prints them as `NOT ENFORCED BY CODE`.
3. A required field the template cannot bind becomes **model-filled** from its OpenAPI leaf (type, enum, description), so the model reads it naturally. If it is on an engine-run tool, that tool is rendered as a model tool in the relevant node and marked `DEGRADED`.
4. The coverage map makes every gap visible.

## 4. Workflow graph template

Top level:
- `initial_node: setup`, `global_nodes: {}`.
- No `agent_config` and no `context_variables`: the API drops them [D].
- `test_variables` come from `call_vars` examples. `tools: []`, unless E6 selects the lifecycle close.

`system_prompt`, a generic template:
- Identity and English, 1–2 short sentences per turn.
- **TOOL MAP**, generated: for each of the 7 tools, "you call it" or "runs automatically", plus when. For example, "get_account and close_call run automatically; never try to call them."
- Discipline:
  - when a rule says to use a tool, call it;
  - obey `what_to_do_next`;
  - something happened only if the result says ok;
  - after every result, speak or call the next tool;
  - never call a `transition_to_` tool in the same message as a bank tool;
  - never compute dates or amounts, use FACTS;
  - say "I do not have that information" for unknowns.
- Then `BANK BRIEF` + `prompt_brief`, and `API CODES` from `code_map`.

| # | Node | Type | Purpose |
|---|---|---|---|
| 1 | `setup` | code, passthrough, initial [V] | Calendar facts and sentinels |
| 2 | `opening` | conversation | Who is on the line; no tools |
| 3 | `third_party` | conversation | Someone else; callback only |
| 4 | `identity` | conversation | Security questions |
| 5 | `load_account` | api_request [V] | get_account, engine-run |
| 6 | `account_facts` | code [V] | Per-product facts and disclosure |
| 7 | `negotiate` | conversation | Disclosure → promise → read-back → record |
| 8 | `ev_<row>`, `ev_done`, `ev_cap_<stage>` | code (one per exit) | Set `end_event` |
| 9 | `finalize` | code | Ledger mirror → outcome and reason |
| 10 | `xfer` | api_request | transfer_to_agent, engine-run |
| 11 | `close` | api_request [V pattern] | close_call, engine-run |
| 12 | `hang_up` | end_call, `message_mode none` [V] | |

A typical brief has about 12 + R ≈ 27 nodes.

**1. `setup`.**
- Reads `vars.get(now_var)` with a robust parse. It writes:
  - `today_facts`: "Today is Wednesday 14 October 2026 (2026-10-14), 11:00".
  - `date_table`: today up to the largest possible deadline + 14 days, one line per date. Each line gives the weekday, business day / weekend / holiday → the next business day, and the "this" and "next <weekday>" resolutions per `calendar`.
  - `callback_slots`.
  - `end_event='none'`, `xfer_queue='none'`, `close_outcome=<default opening row>`.
  - `account_facts='(not loaded)'`, `disclosure_text=''`.
- It **never sets `close_reason`**, so that an unset reason is dropped from the close body (E2).
- `try/except` everywhere. Transition: `always → opening`.

**2. `opening`.**
- `on_enter {tts: opening_line}`, `on_enter_first_entry_only: true` [V].
- `task_message`:
  - "You do not know why the bank is calling; reveal nothing beyond the opening sentence";
  - the brief's opening quotes;
  - the exit list ("To end as <outcome>/<reason> (<trigger>): first say <say_before_end>, then thank, say goodbye, and call transition_to_ev_<id> in the same message");
  - "No bank tool is available in this step."
- `extraction_schema`: `who_answered` string, enum [confirmed, someone_else, wrong_number, deceased]. Its description is `confirm_criteria` plus "empty for a greeting, a question or an unclear reply". `min_confidence` 0.7 [D, E4].
- `max_node_turns` 8 → `ev_cap_opening`.
- Transitions, in order:
  1. `who_answered equals confirmed` → `identity`;
  2. one grouped OR over `someone_else` | `wrong_number` | `deceased` → `third_party`;
  3. `is_tool_call` exits for rows whose phases include `opening`, for example unclear, declined, human.

  There is no `always` self-transition: when nothing matches, the node stays [D].

**3. `third_party`.**
- `on_enter llm`, first entry only.
- `task_message`: the third-party quotes, `{{callback_slots}}`, the exits.
- `tools`: `schedule_callback`, if it is in `stage_tools`. `customer_id` is baked; date and time are model-filled from the API leaves [V pattern].
  - Pre-hook: "11", "11am" or "11.00" → `HH:MM`; dates → ISO [D].
  - Post-hook [V]: on ok, "Booked for <d> <t>. Thank the person, say goodbye and call `transition_to_ev_<callback row>` in the same message, with no other tool". On failure, the brief rule.
- `maxRetries 0`. Exits: rows with phase `third_party`. Cap 12 → `ev_cap_third_party`.

**4. `identity`.**
- `on_enter llm` (asks question 1).
- `task_message`: the identity quotes; the questions in order with their format; "CALL verify_identity once per *complete* answer; if part of an answer is given, ask for the rest first"; "obey what_to_do_next"; the exits.
- `tools`: `verify_identity`, rendered from the API, so either shape works.
  - Pre-hook: a format normaliser (digits-only, `year` → 4 digits, `alnum` → upper case without spaces, `date` → ISO zero-padding only). The model applies the brief's day/month order, so the bank's swap hint still works.
  - Post-hook from response roles:
    - all verified → "verified";
    - this answer correct → "Correct. Now ask: <next question>";
    - a hint value → the brief's instruction;
    - ok false → "Could not be read, ask again";
    - wrong with answers left → the brief's rule;
    - none left → "The check failed. Say <failed line>, thank, goodbye, call `transition_to_ev_<failed row>`".
- Transitions:
  1. `<gate.field>` equals "true" or "True" → `load_account` [V exp01, fires in the same turn];
  2. tool-call exits (failed, declined, human).
- Cap 20 → `ev_cap_identity`.
- `get_account` is never available to the model. This fixes PUB-03.

**5. `load_account`.**
- `pre_actions`: `get_account`, every field baked from `bindings`; `maxRetries 2` (read-only); `connect_retries 2`.
- `suppress_tool_results: true`, because the facts carry everything. No `response_mapping`: exp01 showed the node-level mapping fails.
- Transition: `always → account_facts`.

**6. `account_facts`.**
- `flatvars.collect_list(vars, 'load_account_response.data.<list_field>')` [V], with fallbacks for a list or JSON text. Products keep the bank's order. For each product k it computes:
  - slot `Pk`, `product_id`, label (template), past_due, days_late, band, `deadline` (ISO and spoken), floor;
  - the attempt plan with concrete amounts and dates, for example "attempt 1: 420.00 (or the floor 126.00 if the full amount was called too much) on Fri 16 Oct 2026 (2026-10-16); no attempt 2";
  - the valid date window.
- It writes:
  - `pK_id` for every slot k ≤ K. An unused slot gets `'none'` and the facts say "not in use".
  - `product_count`.
  - `account_facts`: multi-line, and it labels dates after each product's deadline ("after P2's deadline → P2 on 2026-10-23").
  - `disclosure_text`: the intro, one `product_sentence` per product, then `first_ask_single` or `first_ask_multi`.
- On a failure (`load_account_failure_count > 0`, or no products), `account_facts` says "ACCOUNT NOT AVAILABLE: say you cannot access the details now, then end with transition_to_ev_<default negotiate row>". That row is chosen by the design and logged as an ASSUMPTION.
- Transition: `always → negotiate`.

**7. `negotiate`.**
- `on_enter {tts: "{{disclosure_text}}"}`, first entry only. Every product is stated before any ask (from P2).
- `task_message`:
  - "Identity verified; the account is loaded (never call get_account)";
  - `FACTS (computed by code from the brief, use exact values): {{today_facts}} {{account_facts}} DATE TABLE: {{date_table}}`;
  - "follow the brief from the first ask to recording";
  - "read back as the brief says; after a clear yes call `create_promise_pK` for each agreed product";
  - "write notes only as the very last step, after every product is settled and only if the brief requires them";
  - the exits, plus `transition_to_ev_done` ("everything the brief requires is done; say the closing lines and goodbye in the same message").
- `tools`, generated from S2:
  - `create_promise_p1..K`: same URL, `function.name` per slot, `product_id` baked `"{{pK_id}}"`, amount and date model-filled [U, E1]. Pre-hook rounds to 2 decimals and pads the ISO date. Post-hook: on success, "Recorded. Say exactly: <success_line>"; on failure, "NOT recorded. Do not say it was. Per the brief: <failure_rule>". `maxRetries 0`.
  - `add_note_p1..K`, only if `notes.used`. The reason enum comes from the API.
  - `schedule_callback`, only if the brief allows a callback after verification.
- Cap 60 → `ev_cap_negotiate`.

**8. Exit nodes.**
- Each exit node has a snippet like `vars['end_event']='<row id>'` and `always → finalize`.
- A distinct node per exit avoids the merge of transitions that share a target [D]. Exit tool-call transitions are verified for closing in exp01 [V].

**9. `finalize`.** It builds the **ledger mirror** from the flattened keys [V/U]:
- `promise_ok[k]`: `create_promise_pK_response.data.<ok>` is true and `pK_id ≠ none`;
- `note[k]`: `add_note_pK_args.<reason_field>` when `add_note_pK` succeeded ([U] `_args` was only "seen in a trial", E1);
- `transferred`: the event row has a queue.

It then evaluates `close_precedence` from top to bottom. For example, for A+B, as data:
1. transferred → the event row;
2. a promise was recorded → promise;
3. every note is "paid" → paid;
4. there are notes → no_promise with the first non-paid note reason;
5. otherwise → the event row.

`done` with nothing recorded falls back to `default_row.negotiate`. It writes `close_outcome`, writes `close_reason` **only if the row has one**, and writes `xfer_queue` and `finalize_debug`. Transitions: `xfer_queue not_equals none → xfer`, then `always → close`.

**10. `xfer`.**
- `transfer_to_agent`, `queue "{{xfer_queue}}"` (baked at entry [D]).
- `maxRetries 1`: per the API, a 500 records nothing and may be repeated.
- Transition: `always → close`.

**11. `close`.**
- `close_call`: `outcome "{{close_outcome}}"`, `reason "{{close_reason}}"`. An unset single placeholder means the field is dropped [D, E2].
- `maxRetries 1`. Transition: `always → hang_up`.
- Fallback if E2 fails: one close node per row with literal values [V exp01], with `finalize` routing on `close_key equals`. The always-fallback goes to a distinct `close_default` node.

**Closing, deterministic and in order.**
- The model never holds `close_call`, `get_account` or `transfer_to_agent`.
- Every ending runs: the model's goodbye together with an exit tool in the same message [V] → `ev_*` → `finalize` → (`xfer`) → `close` → `hang_up`.
- So the goodbye comes before the transfer, the transfer before the close, and the close is the last call, exactly once.
- Caps route to `ev_cap_*`. That path is silent but still closed.
- **E6 alternative:** the organiser's workflow-level lifecycle `close_call` (`alwaysRunsAt end_of_call`), which also survives a customer hang-up. Under it, `setup` must set `close_reason='_'` and the pre-hook must pop `'_'` and empty values. An unresolved lifecycle parameter triggers a model fill [D].

**Honesty after tool failures.**
1. Every model tool has a post-hook that pops `header` and writes `what_to_do_next`. Failure is detected from `status_code ≥ 400`, `status ≠ success`, `ok` false, or missing `data`, and the line names the brief's failure rule [V mechanism, E7 for the 500 case].
2. Writes use `maxRetries 0`, so the brief's "try once more" is the model's visible action and never a hidden duplicate.
3. The close outcome comes from the mirror, that is from actual ok flags, never from the model's memory.
4. Account figures come only from code facts. Raw product results are suppressed.
5. The system prompt carries "ok means done; otherwise say it could not be done" and "I do not have that information".

## 5. Generalisation guarantees

| Generic code (identical for every brief) | From the brief (LLM, validated) | From the tool API (deterministic) |
|---|---|---|
| The node template, stage notes, TOOL MAP template, exit-list template | Call variables and examples, opening line, confirmation criteria, forbidden words | Base URL, paths, the 7 tools |
| Helper vocabulary, `flatvars`, normaliser menu, hook templates | Calendar, holidays, this/next semantics, numeric date order | Request leaves: type, enum, format, description, required |
| Lint, validators, voting, grid tests, trace | Bands, deadline, floor and attempt expressions, windows, callback rules | Response roles' fields and types (gate, remaining, hint, ok, product list) |
| K = 3 default (kit README fact, not a brief value) | Identity questions, formats, hint instructions, lines | Product-scoped tools (id-field name match), enums for every value we send |
| LLM prompts use invented generic examples only | Outcome rows, precedence, notes policy, stage tools, success and failure sentences, code_map | |

**Guards:**
- A pytest test (`test_no_brief_values.py`) scans `src/` and `builder/` for a denylist of public A/B tokens: holiday dates, `phone_last4`, `minimum_payment`, `restructuring`, `collections`, rule numbers. A/B fixtures live only in `tests/fixtures/`, and `build.py` never reads `tests/`.
- After 17:00 UTC, only crash or parser fixes are allowed, never new vocabulary.
- Generality is tested on `variant-c` (perturbed), `variant-r` (raw material), a raw rewrite of A, and mutated OpenAPI copies (renamed fields and enums, postcode or birth_year identity, `all_at_once` shape).

## 6. Experiments to run first (cheap first; the chat route does not use the simulation slot)

| # | Question | Cheap test | Fallback |
|---|---|---|---|
| E1 [U] | Do per-slot tools (different `function.name`, same `/create_promise` URL, `product_id` baked from code-set `{{pK_id}}`) land in the ledger as `create_promise` for the right product? Do `create_promise_p1_response.data.ok` and `add_note_p2_args.reason` appear in the variable table? | Chat route on a PUB-11 practice session (scripts/chat.py), then read `variable_table` from `get_call` and the ledger via `score.http`. | One tool with a model-filled id, a pre-hook id guard, and a pre/post-hook mirror (E7b). |
| E2 [D] | Is a close body field holding exactly `"{{close_reason}}"`, with the variable never set, dropped? Is it sent when set? | Chat on PUB-08 (paid) and PUB-09; read the ledger. | Literal close node per row [V]. |
| E3 [U] | Can an `on_enter llm` entry turn fire a tool-call exit (third party says "she passed away")? | Chat, 2 turns. | None needed if the customer replies. Measure `customer-ended-call`. |
| E4 [D] | Is the `who_answered` fork reliable? | 8 scripted chat openings ("Speaking", "Who is this?", "Yes, what's it about?", "Her husband", "Wrong number", "Hello?", "Go ahead", "That's me but busy"); check `route_evaluated`. Pass if 8/8. | Lower `min_confidence`, or turn the forks into tool-call exits. |
| E5 [D] | Does `max_node_turns` + `max_turn_transition` fire, and on the Nth user message? | Chat with a cap of 2. | A model exit plus the platform default cap. |
| E6 [D] | Lifecycle close in a simulation: is it the last ledger call, and does it fire on a hang-up? | Only if Phase-1 runs show an unclosed `customer-ended-call` or E2 fails: one `--only PUB-02,PUB-09` simulation. | In-graph close (default). |
| E7 [V-partial] | On a fault (PUB-10 `fail_first_n:1`), is it a 500 or ok false? Does the post-hook run and reach the model? Do failure counters increment? (b) Do hook-written vars reach later code nodes? | Rides along with the Phase-1 A run; inspect events. | Prompt rule plus mirror from counters. |
| E8 [V-partial] | Do 20–40 KB code nodes (helpers + hex spec) run under `timeout_ms` 10000, and do multi-line facts render? | `setup_success_count` and `variable_table` in the first A run. | Split helpers by node, trim the date table. |
| E9 [U] | How often does the model fire an exit in the same message as a bank write? | A script over every Phase 1–3 transcript (`function_call_start` order). Free. | Exit nodes check `*_response` and retry engine-side from `<tool>_args`. |
| E10 | Builder reproducibility. | `build.py --dry` twice each on A, A+B, variant-r, variant-c: spec hash, grid outputs, typed design fields, workflow hash. | More votes or verbatim-only prose. |

## 7. Phased plan (about 19 working hours plus 2 h buffer; freeze Sun 15:30 UTC)

All scores use `python3 kit/tools/run_cases.py <agent> --brief X --reps 3`, where a case counts only at 3/3. Every run is logged in the Score log, and every failure becomes a regression test before it is fixed.

**Phase 1: MVP end-to-end on Brief A (≈8 h, until about Sat 21:00 UTC)**

1. (3 h) Write:
   - `spec.py`: schema, validator, canonicaliser;
   - `tests/fixtures/spec_a.json`, hand-written and test-only;
   - the helper vocabulary in `sandbox/` plus the facts main;
   - `expr.py`: AST whitelist;
   - `render.py`: the Section 4 graph;
   - `hooks.py`;
   - T7 lint additions in `validate.py`;
   - the T5/T6 local harness.

   Unit tests: 26 Oct 2026 → 2026-10-27; early deadline 2026-11-02; late deadline 2026-10-23; attempt 1 on 2026-10-16; callback 2026-10-15; plus weekend, holiday and month-end `now`.
2. (1 h) Run E1, E2, E4, E5 and E8 by chat on the agent built from the fixture. Record [C]/[I] in `docs/freya_api_notes.md` and pick the fallbacks.
3. (2 h) A at reps 1 → read transcripts → fix → reps 3.
4. (2 h) LLM front end S3–S7 in `build.py`. The extracted spec must be grid-equal to the fixture, with typed design fields equal. Then score at reps 3.

**Exit:** both the fixture-built and the LLM-built A agents reach **≥ 8/10 at reps 3**. Tag `good-p1`.

**Phase 2: Brief B (≈4 h, until about Sun 01:00 UTC)**
- K slots, `add_note` slots, `finalize` precedence, multi-product disclosure, `spec_ab.json`, then the LLM build from A+B.

**Exit:** the B agent is at **3/3 at reps 3**. The A+B agent on `--brief A` scores at least Phase 1's score minus 1. Tag `good-p2`.

**Phase 3: Robustness (≈5 h, Sun 07:00–12:00 UTC, after sleep)**
- (a) `--style pieces | corrects | talkative | asks_back | in_words` at reps 1 on A and B; the two worst at reps 3.
- (b) Write `tests/fixtures/briefs/raw-a/`: a mail, a policy extract with other values, a memo restoring A's values, and a code list. Build it and score PUB-A at reps 3.
- (c) `variant-r` and `variant-c` builds with `--dry`: specs must match the answer keys on typed fields, then a dry run and a chat smoke test.
- (d) E10.
- (e) If time allows: T10 oracle, and moving notes to the engine if E9 or the B runs show notes written before a transfer.

**Exit:**
- each style scores at least the clean score minus 1 per brief;
- raw-a scores within 1 of clean A at reps 3;
- the variant specs match the answer keys;
- two builds are grid-equal with the same workflow hash.

**Phase 4: Submission hardening (≈2.5 h, Sun 12:00–15:30 UTC)**
- Trace completeness and a redaction test.
- The README run command.
- A fresh-clone build of A and A+B in the scratchpad, timed.
- `export_workflow` to `submission/`, commit, tag `freeze-final`.
- A runbook for 17:00–20:00: run, check the trace, export, commit. Code edits only for generic crash fixes, reviewed against the hard rules.

**Exit:** each fresh-clone build takes under 10 minutes, its score is within 1 of the tagged build, and the trace has every required element and no `fak_` or `sk-` strings.

**Cut order if behind:** T10 oracle → three votes in L3 (fall back to one) → variant-c → E6.

## 8. Top risks and mitigations

1. **Systematic extraction error.** One wrong band edge or a misread memo fails a whole family 3/3. Mitigation: two-framing grid agreement, quote verification, numeric coverage, the design vote, the raw-a and variant tests, and the brief's worked examples as self-tests.
2. **Model-driven negotiation variance (p³).** Mitigation: concrete per-product plans, a labelled date table, fixed disclosure TTS, post-hook steering, and style runs. Move one phase into code (for example a deterministic read-back or recording) **only** when transcripts show a repeated model failure class, and never by adding brief-shaped vocabulary.
3. **Unverified mechanics.** Per-slot tools, unset-field drop, entry-turn exits, caps and `_args` persistence (E1–E5) each have a named fallback, and are all tested on day 1 by chat before the graph is relied on.
4. **Hang-up before close, or an exit racing a write.** Mitigation: E9 scanning; ride-along counts of `customer-ended-call`; the lifecycle close (E6) as a switch; prompt rule 5.
5. **Notes written before a later transfer** (Brief B rule 10 class). Mitigation: the "notes last" stage rule, measured on B. The upgrade path is engine-run notes from per-slot status exits, but only on evidence.
6. **Hidden structure outside the schema.** Examples: a new required field, three identity questions, a new notes policy. Mitigation: model-filled tools straight from the OpenAPI, the full brief in every node, DEGRADED tracing, and tests on mutated OpenAPI. No vocabulary additions after 17:00.
7. **Organiser rerun drift.** Mitigation: strict schemas, voting, verbatim-only prose, the code-composed facts and graph, spec and workflow hashes in the trace, and E10. We submit a run whose spec equals the modal one.
8. **Time and latency.**
   - Time: phase gates with tags, a freeze at 15:30 UTC, and the cut list.
   - Latency: a large system prompt plus the date table can slow turns. Watch the median slowest turn printed by `run_cases` and keep it under 10 s; trim the date table window first.
   - "pieces"-style partial identity answers count as wrong at the bank. The prompt rule is "complete answers only"; measure with `--style pieces`.
## 9. Implementation contract v1 (binding for all modules)

Spec: `src/freya_builder/spec.py` (`SPEC_SCHEMA`, `check_spec`), and the fixture `tests/fixtures/spec_a.json` (Brief A, test-only).
Slots: `K = spec.meta.max_products`; slot k is 1..K. Row ids come from `spec.rows[].id`.

**Node names.** `setup`, `opening`, `third_party`, `identity`, `load_account`, `account_facts`, `negotiate`,
`ev_<row_id>`, `ev_cap_<stage>` (no `ev_done`: decided 15:20; finalize recomputes the outcome from what was recorded, so the specific endings suffice, and a vague 'done' would pull the model away from them), `finalize`, `xfer`, `close`, `hang_up`.
The model fires an exit with the tool `transition_to_ev_<row_id>`; the engine names it after the target node.

**Model-called tool names.**
- `verify_identity`
- `schedule_callback`
- `create_promise_p<k>`: per slot; same URL; `<promise product_field>` baked to `{{p<k>_id}}`
- `add_note_p<k>`: per slot; only if `notes.used`

All of them have `customer_id` (the call var whose role is `customer_id`) baked.

**Variables.** All variables are strings unless noted.

| Written by | Variables |
|---|---|
| `setup` | `today_iso`, `today_facts`, `date_table`, `callback_slots`, `end_event`=`none`, `xfer_queue`=`none`, `close_outcome`=outcome of the `default_rows.opening` row, `account_facts`=`(not loaded)`, `disclosure_text`=`""`, `product_count`=`0`, `p<k>_id`=`none` for all k, `finalize_debug`=`""`. It NEVER sets `close_reason`. |
| `account_facts` | Reads `load_account_response.data.<products.list_field>` via `flatvars.collect_list`. Writes `product_count`, `p<k>_id` (bank order; unused slots stay `none`), `account_facts` (multi-line, see below), `disclosure_text` (intro + one product sentence per product + first ask, single or multi), `account_status` (`ok` or `unavailable`). |
| `ev_<x>` | `end_event` = `<x>` (a row id, `done`, or `cap_<stage>`). |
| `finalize` | Reads `end_event`, `create_promise_p<k>_response.data.ok`, `add_note_p<k>_response.data.ok`, `add_note_p<k>_args.<notes.reason_field>` (fallback `add_note_p<k>_args.reason`), and `p<k>_id`. Writes `close_outcome`, `close_reason` (ONLY when the chosen row has a non-empty reason), `xfer_queue` (`none` or the row's queue), `finalize_debug`. |

**The `account_facts` text, per product line block:**
- slot, id, label (from the type label template with `{field}` from the product);
- past due, days late, band;
- deadline (ISO and spoken);
- floor (field and value);
- each attempt that applies to the band, with concrete amount and date;
- the valid promise window;
- a "MANDATORY TRANSFER: end with transition_to_ev_<row>" line when the band has a `transfer_row`.

**`finalize` rules.**
- `done` maps to `default_rows.negotiate`, and `cap_<stage>` maps to `default_rows[<stage>]`. Either is used only when no precedence rule fires on recorded facts.
- `close_precedence` is evaluated top-down:
  - `transferred`: the event row has a queue → that row.
  - `promise_recorded`: any `create_promise_p<k>` ok.
  - `all_notes_reason`: there are notes and all of them have that reason.
  - `any_note`: → `first_note_reason_not` (`note_reason`) in slot order, with the given outcome.
  - `always`: → the event row.

**Code rules.**
- Code nodes = `sandbox.assemble([...modules], main, CONFIG)`.
- Spec expressions are INLINED as Python functions at build time: `def _x0(today, now_date, deadline, p_days_late): return <expr>`. There is no `eval` at run time.
- The helper vocabulary in `sandbox/policy_helpers.py` uses the module globals `WORKDAYS` and `HOLIDAYS`, set from CONFIG:

| Helper | Meaning |
|---|---|
| `add_days(d, n)` | `n` calendar days later |
| `add_business_days(d, n)` | the n-th business day strictly after `d`; `n == 0` gives `d` |
| `next_business_day(d)` | strictly after `d` |
| `business_day_on_or_after(d)`, `business_day_on_or_before(d)` | |
| `last_business_day_of_week(d)` | the Mon–Sun week |
| `last_business_day_of_month(d)`, `end_of_month(d)` | |
| `weekday_in_week(d, wd, k)` | |
| `is_business_day(d)` | |
| `date(y, m, d)` | |

**Hooks** (`hooks.py`, returning code strings):

| Function | What it writes |
|---|---|
| `verify_post(spec)` | `result['data']['what_to_do_next']` from the response roles: gate, answer_ok, remaining, hint |
| `verify_pre(spec)` | Normalises the answer by question format: `date` → ISO zero-pad, `digits:N` → digits only, `year` → 4 digits, `alnum` → upper case without spaces |
| `promise_post(spec, k)` | On success: "Recorded. Say exactly: <success line>"; on failure: "NOT recorded…" + failure rule |
| `promise_pre(spec)` | Amount rounded to 2 decimals, ISO date padded |
| `note_post(spec)`, `callback_post(spec)` | |
| `callback_pre(spec)` | Normalises HH:MM |

Every hook: try/except, pops `header`, detects failure from `status_code` ≥ 400, `status` ≠ success, `ok` false or missing `data`, and contains no double braces.
