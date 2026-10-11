# RUNBOOK: Sunday 11 Oct, final case (17:00–20:00 UTC = 20:00–23:00 Istanbul)

The requirements come from `docs/hackathon_requirements.md` → "FINAL FORMAT, 11 Oct" (official page re-read 16:00 UTC).
Times are UTC. **The section "FINAL (current)" below replaces the older sections, which assumed two hidden briefs.**

## FINAL (current, written 17:10): one Turkish case folder + our own mock

Pre-flight (done 17:05): builder frozen as `freeze-final-2` = cand-final.4 e2635e9, merged into `main` (builder code
identical); private repo https://github.com/M4G1W0W/freya-build-the-builder (main + tag pushed); mock live at
`https://teampistalogic.atlasreyiz.workers.dev` (`MOCK_URL`, `MOCK_ADMIN_TOKEN`, `MOCK_TEAM_KEY` in `.env`);
`pdftotext` installed (Homebrew poppler 26.09). Team: **Pistalogic**.

**HARD RULE: nothing from the case goes into `src/`, `builder/`, `tests/`, fixtures or prompts.** Only generic bug fixes.
The mock (`mock/`) is not builder code; whether its filled-in version is committed is the user's call.

1. Unzip the case **outside the repo** (e.g. `~/Desktop/FreyaBank-final/`). Read BRIEF.md first, then README, the
   service contract, the test customers, the Q&A and the 6 example conversations. Note the `now` format: worded Turkish
   months in upper case or without diacritics need the prepared fix `cand-final-dates` (385b326, user decision).
2. Adapt the mock from the contract and the test customers: `mock/src/bank.js` (`HANDLERS`, field names, outcomes,
   errors), `mock/data/customers.json` (`mock/tools/xlsx_rows.py <file.xlsx>` turns a workbook into rows). Every tool
   URL the builder makes is `mock_url` + the contract's path, with the contract's method and field names: the mock must
   serve exactly those. `cd mock && npm test && CI=1 npx --yes wrangler@4.149.0 deploy`, then curl-smoke it.
3. Choose `mock_url`: the base under which the contract's paths sit (paths `/v1/x` -> the bare worker URL; paths `/x`
   -> the URL the mock serves them under). The same value goes into `submission.json`.
4. Dry build (no Freya writes), from the repo root:

```bash
export PATH="$PWD/.venv/bin:$PATH"; python3 --version   # 3.10+
set -a && . ./.env && set +a
python3 builder/build.py ~/Desktop/FreyaBank-final/<folder> "<mock_url>" --dry --slot final 2>&1 | tee runs/final-dry.log
```

   Check: one `tool <name> <METHOD> <url> request=[...]` line per contract operation, each URL served by the mock;
   `WARN` lines (unreadable files, `consolidated rules are N chars`); `STEP    call language: Turkish`;
   `BANK BRIEF in the prompt = the consolidated rules`; spec check and local validation PASS.
5. Real build (the submitted run; keep everything it prints):

```bash
mkdir -p traces submission && set -o pipefail
python3 builder/build.py ~/Desktop/FreyaBank-final/<folder> "<mock_url>" --slot final --export submission/final.workflow.json 2>&1 | tee traces/final.log
grep -E "END +ok=True|spec check .*PASS|validation: PASS|chat smoke test: opening reply: PASS|CREATED +workflow_id=" traces/final.log
```

   Exit 3 with only a 503/504 smoke failure = deployed (see the table below). A re-run replaces the agent and the trace;
   submit the agent and trace of ONE run.
6. Test against our mock: cases written from the 6 example conversations (kept under `runs/`, gitignored; case ids =
   `customer_id`s in `mock/data/customers.json`), one simulation each via `runs/dev/r4/harness/suite_once.py` with
   `FREYA_BANK_HOST=https://teampistalogic.atlasreyiz.workers.dev` and `FREYA_BANK_TEAM_KEY=$MOCK_TEAM_KEY`
   (maxRetries 0, no reruns; the user approves the call count; ledger `runs/dev/r4/calls.tsv`, cap 789).
7. Secret check, commit, push (user go given for this repo 16:59):

```bash
.venv/bin/python scripts/check_secrets.py traces/final.log submission/final.workflow.json
git add traces/final.log submission/final.workflow.json && git commit -m "Submission: final case agent + trace"
git push origin main && git rev-parse HEAD
```

8. The user e-mails `submission.json` to the address in the kit e-mail **before 20:00 UTC** (aim for 19:00):

```json
{
  "team": "Pistalogic",
  "members": [{"name": "<name>", "email": "<email>"}],
  "repo": "https://github.com/M4G1W0W/freya-build-the-builder",
  "commit": "<git rev-parse HEAD after step 7>",
  "run_command": "python3 builder/build.py {case_folder} {mock_url}",
  "workflow": "submission/final.workflow.json",
  "trace": "traces/final.log",
  "mock_url": "<the mock_url used in step 5>"
}
```

9. Invite the organisers' GitHub account to the private repo. Keep the mock running until the results are out.

## Before 17:00 (STALE: two-brief format)

- [ ] **15:30 freeze.** `make verify` is green, then `git tag freeze-final`. After this, only generic crash and bug
      fixes are allowed.
- [ ] **Which code is submitted: the commit tagged `freeze-final`.** The user decides which candidate gets the tag
      (on 11 Oct morning the candidate is branch `cand-final`, ca80d52; not yet merged to `main`). Build from a
      checkout of that commit and check it before step 2: `git describe --tags` prints `freeze-final`
      (`git tag --points-at HEAD` if the commit has several tags; after a generic fix, step 4, it prints
      `freeze-final-N-g<commit>`), `git status --porcelain` prints nothing, and each trace's START line then shows
      `git=<that commit> dirty=False`.
- [ ] `git status` is clean. `date -u` is checked.
- [ ] `set -a && source .env && set +a`. FREYA_API_KEY and OPENAI_API_KEY are set (BUILDER_MODEL and
      BUILDER_MODEL_FALLBACKS are optional: the chain gpt-6.1-sol → gpt-5.5 → gpt-5.4 is in code).
- [x] Team name: **Pistalogic**. Repo: **private for now**; the user will make it public or share it later (it must be
      cloneable by the organisers at the submitted commit).
- [ ] The OpenAI key question for the organisers' re-run (see Open questions; the README's "Organiser re-run"
      section lists exactly what they need).
- [ ] Rehearse steps 2–5 once on `kit/briefs/brief-a.md` with `--slot rehearsal` and `traces/rehearsal.log`,
      including the secret check on the log and the exported JSON. Delete the rehearsal files afterwards.

## 17:00: the hidden briefs arrive

> **STALE (official page re-read 2026-10-11 ~16:00 UTC).** The steps below assume two brief files with tool API
> files and `--slot hidden-1/2`. The final is now ONE Turkish case as a zip FOLDER (md/docx/pdf/xlsx), the command is
> `python3 builder/build.py {case_folder} {mock_url}`, we must deploy OUR OWN mock on Cloudflare Workers first, and
> we send `submission.json` (with `mock_url`) by e-mail. See `docs/hackathon_requirements.md` → "FINAL FORMAT,
> 11 Oct" and `docs/WORKING_STATE.md` (top) before following anything here.

**HARD RULE: write nothing from a hidden brief into the repo except `traces/` and `submission/`.** That means no
rule, value, name, date or code in `src/`, `builder/`, `tests/`, fixtures or prompts. Only generic bug fixes, which
must make sense for any brief.

1. Save the files **outside the repo** (for example `~/hidden/`). Note the file names. Each hidden brief is **one
   file** (FAQ); build each from exactly its own file.
2. The official run command is `python3 builder/build.py {brief_path} {tool_api_path}`. Here the system `python3` is
   3.9, so put the venv first on PATH. The command stays the same:

```bash
export PATH="$PWD/.venv/bin:$PATH"
python3 --version   # must be 3.10+
mkdir -p traces submission && set -o pipefail   # tee writes nothing into a missing folder
python3 builder/build.py ~/hidden/<brief-1> ~/hidden/<api-1> --slot hidden-1 --export submission/hidden-1.workflow.json 2>&1 | tee traces/hidden-1.log
python3 builder/build.py ~/hidden/<brief-2> ~/hidden/<api-2> --slot hidden-2 --export submission/hidden-2.workflow.json 2>&1 | tee traces/hidden-2.log
```

   Each build takes about 2 minutes (longer while Freya is degraded: the builder then retries its platform calls
   itself, see step 3). Run them **one after the other** in one terminal. The explicit `--slot` names keep the two
   agents in separate workflows.
3. Read each trace. These greps must each print a line (except END and the smoke test after an exit 3 with only a
   503/504 smoke failure: see the table):

```bash
grep -E "END +ok=True" traces/hidden-N.log
grep -E "TEST +spec check \((round [0-9]+|final)\): PASS" traces/hidden-N.log
grep -E "TEST +local workflow validation: PASS|TEST +platform dry-run validation: PASS" traces/hidden-N.log
grep -E "TEST +chat smoke test: opening reply: PASS" traces/hidden-N.log
grep -E "CREATED +workflow_id=" traces/hidden-N.log   # steps= and tools= are on this line
```

   For the raw-material brief, read the `amendment:` lines. **Every memo change must be listed.**

   New since 10 Oct evening, so grep the trace for each:
   - `UNRESOLVED spec problem (deployed anyway)`: the LLM could not repair it. Read each one. If it is a builder bug,
     make a generic fix and re-run; if the brief really cannot be expressed, keep the agent (better than none) and
     note it.
   - `date check:`: the date self-test found an expression that gives past, missing or after-deadline dates on some
     call day. A repair round normally fixes it; if it is still listed as UNRESOLVED, read it carefully.
   - `engine call: … sent without required field(s)`: the bank's API requires a field that engine-run calls do not
     send. This is a builder gap; decide quickly whether a generic fix is possible.
   - `falling back to`: the primary model was unavailable; fine, but note it.
   - `attempt N failed (…); retrying in Ns`: a Freya platform call (dry run, save, export or the smoke chat) got a
     429, 5xx or network error and the builder retried it (5–60 s waits, up to about 6 min of waiting per call; the
     smoke chat waits only 5 and 15 s; it stops retrying when the 30-minute limit is near: `giving up: 30-minute
     build limit near`). Fine if the step then passed.
   - `this retry can leave a stray workflow`: a failed first create may have been processed, so one unrecorded
     extra workflow can exist. Harmless (one of 200); ignore it.
4. If a build fails or looks wrong, **re-run the same command.** Exception: **exit 3 with only a 503/504 smoke
   test** (see the table) means the agent is deployed; do not re-run. After an `ERROR` on a platform call, check
   Freya first (outage row in the table), wait a few minutes and re-run **once**. A re-run updates the same slot
   in place and the new trace replaces the old one. Never edit the agent by hand. If it fails again, read the
   error. A **generic** fix to the builder is allowed: commit it, then **re-run both briefs**, so both agents come
   from the same commit.
   Every trace's START line has `git=<commit> dirty=<flag>` (the flag covers `src`, `builder` and
   `pyproject.toml` only). Before submitting, both traces must show `dirty=False`, and the builder code of the
   form's commit must equal theirs. The submission commit only adds traces and exports, so for each trace's commit
   C this prints nothing: `git diff --stat C HEAD -- src builder pyproject.toml`
   (`grep -o "git=[0-9a-f]* dirty=[A-Za-z]*" traces/hidden-*.log` lists them).
5. Secret check, then commit:

```bash
.venv/bin/python scripts/check_secrets.py traces/hidden-*.log submission/hidden-*.workflow.json
git add traces/ submission/ && git commit -m "Submission: hidden briefs 1-2 agents + traces"
git tag submission-final
```

6. **Push only with the user's go-ahead.** Then send the form (JSON) to the address in the kit email, with these fields:
   - `team`: `Pistalogic`;
   - `repo` (the GitHub URL);
   - `commit` (`git rev-parse HEAD`);
   - `run_command`: `python3 builder/build.py {brief_path} {tool_api_path}`;
   - `workflows`: `submission/hidden-1.workflow.json` and `submission/hidden-2.workflow.json`;
   - `traces`: `traces/hidden-1.log` and `traces/hidden-2.log`.
7. Deadline: the form must be in before **20:00 UTC**. Aim for 18:30 to leave a margin.

## If something goes wrong

| Symptom | Action |
|---|---|
| LLM error or timeout | The fallback chain (gpt-5.5, gpt-5.4) runs automatically. Re-run the same command. |
| `spec check` still has problems after 2 repair rounds | Read the problem list. If it is a builder bug, make a generic fix and re-run. |
| Freya 5xx or 429 | The builder already retried it (`attempt N failed … retrying in Ns` WARN lines). If the trace still ends with an `ERROR` on a platform call (dry run, save, export): check Freya with one GET (next row), wait a few minutes and re-run **once**. Do not hammer the platform. |
| Freya outage? | Before blaming the builder, send **one** GET: `.venv/bin/python scripts/credits.py "outage check"` (or `make credits`). If it also hangs and returns 504, the platform is down: wait and re-run once it answers. The 11 Oct 09:38–10:08 UTC outage looked like this: GETs and POSTs returned 504 after about 60 s each. The chat endpoint can be degraded on its own (11 Oct morning: `/chat/message` 504 while other calls worked). |
| `build time budget` in the trace | Model calls stop after 25 min (the page allows 30 per brief). A skipped repair round deploys the best spec so far; `build time budget used up` fails the build. Re-run; the fallback models are tried when one stalls (`timed out after`). |
| `END ok=False`, exit code 3 | **Agent saved, smoke test failed.** The agent was saved and exported, but its chat smoke test failed (the TEST line says why). If the trace shows `CREATED` and `saved slot`, `platform dry-run validation: PASS`, and the only failure is `chat smoke test: workflow starts: FAIL` with a 503/504, the agent **is deployed: do not re-run** (build time is a tie-break; a re-run adds nothing). Otherwise (a wrong or empty opening reply, `forbidden=[…]`, a 500, or any other failure in the trace) re-run the same command; if it fails again, read the reply in the TEST line. |
| `python3` is 3.9 | Run `export PATH="$PWD/.venv/bin:$PATH"` (`build.py` exits with a clear message on < 3.10). |
| A brief seems to depend on another document | The FAQ says each hidden brief is one file and `{brief_path}` is that file. Build from that one file only. If in doubt, ask the organisers by replying to the login mail. |

## Open questions (for the user, before Sunday)

- The organisers re-run the top 10 builders. Ours needs an `OPENAI_API_KEY` ("You pay for your builder's own model
  calls"). How will they get a key? The user is asking the organisers (draft in the 10 Oct chat). Options: we send one
  privately with a spending limit and an expiry, or they use their own. Never put a key in the repo.
- Answered on 10 Oct: team Pistalogic; the repo stays private until the user shares it or makes it public.
- The user asked whether the builder could use Freya instead of OpenAI. Our recommendation is no. The Freya API has no
  completion endpoint, model names are undocumented free strings, `llmConfig.maxTokens` is capped at 4000 while our
  extraction outputs are about 4.2–4.6k tokens, and long chat turns can return 504. Details are in the Decision log.
