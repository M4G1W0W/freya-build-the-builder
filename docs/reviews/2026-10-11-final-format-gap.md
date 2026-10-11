# Final-format gap analysis (read-only, 2026-10-11 16:12 UTC)

**What this is.** A read-only workflow run from the Dashboard Creator session after the page changed the final's
format (see `docs/hackathon_requirements.md` → "FINAL FORMAT, 11 Oct").
- **Code read:** `freeze-final` = b9756fe, which main has carried since 8e251fe.
- **How it ran:** 4 readers (builder input, mock, Turkish, stale docs), then 1 synthesizer and 1 completeness critic.
  The critic re-checked 7 cited lines against b9756fe.
- **What it did not do:** no Freya, Cloudflare or bank calls, and no builds.
- **Status tags:** [C] means confirmed by reading code or a local command; [I] means inferred.
- **Full detail:** the per-finding file:line evidence is in `docs/reviews/2026-10-11-final-format-gap.json`.

**Written after this analysis:**
- 0a8d2ad (16:13 UTC, another session) committed a mock template in `mock/`: Cloudflare Workers + Durable Objects, 6 node
  tests, outside builder/ and src/. The critic's first point calls `mock/` untracked; it is now committed.
- Its concern still stands: if `mock/` is filled from the final zip after 17:00 and committed, the reviewed commit holds
  final-case content. This is a team decision.
- 81714cb added the banners. Report 4's claim that "no doc mentions the new format" predates that commit.

No builder change has been made. Every change below needs the user's decision.

## Plan (synthesizer)

## Top 5 blockers
1. **The builder can't run `{case_folder} {mock_url}`.** It treats the last argument as the tool API file and everything before it as briefs (cli.py:31, 41-43). A folder crashes at `read_bytes` (cli.py:56), the error is caught, and the build exits 1 before any model call (cli.py:187-191). Word, Excel and PDF files are read as binary (cli.py:54-62), and nothing in the builder can parse them (pyproject.toml:7 `dependencies = []`). [C]
2. **Tools only come from an OpenAPI JSON file.** Loading is at toolapi.py:107-108 and the URL comes only from `servers[0]` (toolapi.py:85-86). The practice tool names are required: spec.py:389 checks for them and render.py:638-726 looks them up by name. [C] If the contract names its operations differently, render raises KeyError and no agent is built. [I]
3. **The agent is hard-wired to English.** The system prompt says "Speak English." (render.py:225). Lines it must say word for word are English, and the TTS goodbye is English (render.py:230, 492, 555). [C]
4. **We can't deploy a mock yet.** wrangler isn't installed, there are no Cloudflare credentials, and there is no worker code (report 2). [C] Only the user can log in.
5. **Submission isn't ready.** `git remote -v` is empty, so there is no repo URL [C]. submission.json needs the repo, commit, members and mock_url. RUNBOOK step 6 still describes the old form (RUNBOOK.md:94-100). [C]

## A. Before 17:00
The minimum builder changes (A1–A4a) take about 65 min, which is more than the 48 min left. Do the user items alongside them. Run `uv run pytest`, commit and tag after each step.

| # | Item | Owner | Time | Risk | Evidence |
|---|---|---|---|---|---|
| A1 | Add a folder + URL mode to the CLI and keep the old brief + JSON mode | agent | 15m | low; after 17:00 this is a grey area | cli.py:29-44, 138-141 |
| A2 | Document reader: .md first; .docx/.xlsx with stdlib zipfile + ElementTree; .pdf through optional pypdf; any other type gets a warning and is skipped; try UTF-8, then cp1254 | agent | 30m | low. **Fixing a crash on an unexpected file type is allowed as a generic fix after 17:00** | cli.py:54-62 |
| A3 | Replace the tool base URL with mock_url, and fail validation if any api_call points elsewhere | agent | 10m | low | toolapi.py:85-86, 97, 138; validate.py:121-126 |
| A4a | Tool source: if the folder has an OpenAPI *.json, use the existing parser | agent | 10m | low | toolapi.py:84-108 |
| A4b | Otherwise, one model call turns the contract into tools and maps each operation to one of the 7 generic roles | agent | 60-90m | high; doesn't fit before 17:00 | toolapi.py:14-32; spec.py:389 |
| A4c | Emergency option: the builder reads `{mock_url}/openapi.json`, a file we write | **user decides** | 15m | grey area under "the builder must work alone" | report 1 |
| A5 | Language: speak the documents' language; lines quoted in the prompt give the meaning and are said in the call's language; goodbye taken from the spec; "never translate" added to the consolidation and spec prompts | agent | 30m + 1 practice build | medium-high; changes behaviour | render.py:225, 230, 555; pipeline.py:48-90 |
| A6 | In folder mode, always use consolidated_rules, and keep test data and example conversations out of the agent prompt [I] | agent | 5m + check | medium | pipeline.py:196, 207; render.py:240-241 |
| A7 | Cloudflare account, then `npx wrangler@4 login` or an API token | **user** | 10m | blocker | report 2 |
| A8 | Generic mock skeleton **outside the repo**: routes on the last path segment; one Durable Object per customer [I]; 200 with ok:false for refusals, 500 for failures; ledger; fault injection; session reset after close or idle [I]; duplicate-write guard; try/catch; /health; xlsx→json and conformance scripts. Deploy it to fix mock_url | agent, after A7 | 35m | medium | report 2; docs/reference/final_case_2026-10-11.json:2 |
| A9 | Add a remote, set visibility, give the team and members list | **user** | 10m | blocker | `git remote -v` is empty |
| A10 | Fix stale doc bodies. 81714cb added banners (CLAUDE.md:15-23, RUNBOOK.md:28-30), but CLAUDE.md:36 still says the agent may call "only the kit's tool API", RUNBOOK.md:31-46 and :94-100 describe the old flow, and there is no mock step | agent | 15m | low; docs only, page wording only | report 4 (its claim that no doc mentions the new format is out of date) |

Run builds with `.venv/bin/python`. /usr/bin/python3 is 3.9.6, which build.py refuses (build.py:14-15). [C]

## B. 17:00–20:00
1. **B1 (17:00–17:15, user + agent).** Unzip outside the repo. Read BRIEF.md, README.md, the service contract and the test customers. Answer the open questions below from them.
2. **B2 (–17:55, agent).** Fill the mock handlers and customers.json in the mock repo only. Field names and types must match the contract exactly. Risk: high.
3. **B3 (–18:10).** Deploy. Run curl and the conformance check. Watch `wrangler tail`.
4. **B4 (start by 18:15, finish by 18:40).** `.venv/bin/python builder/build.py <case_folder> <mock_url> --slot final --export submission/final.workflow.json 2>&1 | tee traces/final.log`. The builder's own time limit is 25 min (llm.py:24).
5. **B5 (–19:10).** Verify:
   - the trace shows dirty=False;
   - one Turkish chat turn works;
   - every tool URL is mock_url;
   - the trace's amendment lines cover each announcement;
   - check_secrets passes.

   **Only generic fixes are allowed:** crash or parsing bugs, never field names, values or announcements. After a fix, rebuild. Submit one run together with that run's trace.
6. **B6 (–19:30).** Reset the mock's state. Commit the export and the trace, then push.
7. **B7 (user, before 20:00).** E-mail submission.json, with run_command naming the interpreter actually used. Keep the mock up. Don't redeploy without a curl test.

## Inferred claims [I], unverified
- A global Map or KV would split state across Worker instances, so Durable Objects are needed.
- The organisers will reuse customer ids across runs, so the mock needs a session reset.
- Differently named contract operations cause a KeyError.
- A "clean" read of the folder copies test data into the agent prompt.
- The consolidator may translate the Turkish lines the agent must say word for word.
- `now` may not be ISO; a Turkish month name falls back to the server clock (facts.py:117).
- The 30-min build limit is not restated on the page.
- Report 2 made one npm registry lookup, breaking the no-network rule.

## Open questions for the organisers
1. Do you read a ledger or results endpoint on our mock? If so, which path and shape?
2. Are the hidden customers' ids in the zip's test-customers file? Which call variables do you pass (customer_id, now, …)?
3. Will the same customer be tested repeatedly or at the same time? Should the mock reset its state per call?
4. What format does `now` have in the final?
5. Does the 30-min build limit still apply?
6. May run_command use `.venv/bin/python` or `uv run`?
7. Is a private repo with access acceptable, and whom do we grant access to?
8. May the builder read a machine-readable contract we derive from the documents, or must the tools come only from the bank's documents?

## Completeness critic

- **The mock is already inside the repo, which goes against A8.** `git status` lists `?? mock/`, and `.gitignore` has no entry for `mock/`, `node_modules` or `.wrangler`. [C] The folder holds practice customers (`mock/data/customers.json` `_note`: "EXAMPLE data from the public practice set") and practice handlers (`mock/src/bank.js:103` `close_call`). [C] If it is filled after 17:00, a `git add -A` at B6 commits final-case content into the reviewed commit. Move it out or gitignore it before 17:00.
- **A4b is the real blocker; A4a will probably never fire.** The FAQ lists Markdown, Word, PDF and Excel, not JSON. Even with an OpenAPI file, `spec.py:389` requires the literal names `verify_identity`, `get_account`, `create_promise` and `close_call`. [C] So without role mapping, a final agent is unlikely. A4c should be rejected, not left as "user decides": a team-written contract at `mock_url` would be human-translated case content fed to the builder. [I]
- **The prompts assume an outbound collections call.** `render.py:225` says "on an outbound phone call" and `pipeline.py:48` says "outbound collections phone calls". [C] A "statement-debt line" may be an inbound call. [I] A5 should change this wording too, and the example conversations should show who speaks first.
- **`now` and the call variables come from the model.** The spec model extracts them (`spec.py:38`), and `check_spec` fails without a customer-id variable (`spec.py:391`). [C] Add to B5: check that the spec's variable names match the example conversations and README. The worded-date fallback to the server clock (`facts.py:88` regex `[a-z]+`, `facts.py:117`) is confirmed. [C] Fix it before 17:00 rather than leaving it in the [I] list.
- **The clean path puts the whole folder into the agent prompt.** `pipeline.py:196,207` [C] In A6, keep the Q&A and the announcements in consolidation, because they are rules. Only the test customers and example conversations should stay out.
- **The trace redacts only four names.** `trace.py:14` [C] Run the build in a shell without `CLOUDFLARE_API_TOKEN`, or add it to the list. The `START` line prints the mock URL as `tool_api=` (`trace.py:37`). [C]
- **The export matches submission.json.** `export_workflow` writes `{workflow_id, agent_id, updated_at, workflow}` to the `--export` path (`kit/freya.py:65-68`). It runs before the self-test, so it is written even when the run exits with code 3 (`cli.py`). [C] Tool URLs are baked into the workflow (`toolapi.py:138`), so never rename or delete the worker after the build.
- **The self-test reaches our mock.** It uses example values chosen by the model (`pipeline.py:218-233`), and its forbidden-word check uses `lower()`. [C] Keep the mock reset in B6.
- **The 200-workflow limit is fine.** `.freya-agents.json` has 47 slots, and `save_workflow` updates a slot in place (`kit/freya.py:43-46`). [C] Reuse `--slot final`, and build only from the main checkout: worktrees have their own state file (`platform.py:23-24`). [C]
- **Adding pypdf touches tracked code.** It changes `pyproject.toml`, which the builder's clean-tree check (`dirty=False`) covers (`cli.py:41`); commit before the run. [C] A fresh-clone `python3` rebuild without pypdf would skip PDFs silently. If the flow drawing is an image, skipping it loses the flow. [I]
- **B5 conformance should compare more than URLs.** Diff each workflow tool's body field names against the mock's handlers.
- **The time estimate leaves out a practice simulation.** A5 changes behaviour, so it needs one practice simulation: only one runs at a time, at 3–11 minutes per 10 cases.

I checked these claims against the freeze-final code (b9756fe): `cli.py:41-43,56`, `toolapi.py:85-86,108`, `render.py:225`, `spec.py:389`, `llm.py:24` and `pipeline.py:196,207`.
