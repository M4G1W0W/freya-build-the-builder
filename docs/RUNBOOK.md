# RUNBOOK: Sunday 11 Oct, hidden briefs (17:00–20:00 UTC = 20:00–23:00 Istanbul)

The requirements come from `docs/hackathon_notes.md` → Submission (official page + kit README). Times are UTC.

## Before 17:00

- [ ] **15:30 freeze.** `make verify` is green, then `git tag freeze-final`. After this, only generic crash and bug
      fixes are allowed.
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

   Each build takes about 2 minutes. Run them **one after the other** in one terminal. The explicit `--slot` names
   keep the two agents in separate workflows.
3. Read each trace. These greps must each print a line:

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
4. If a build fails or looks wrong, **re-run the same command.** That updates the same slot in place and the new
   trace replaces the old one. Never edit the agent by hand. If it fails again, read the error. A **generic** fix to
   the builder is allowed: commit it, then **re-run both briefs**, so both agents come from the same commit.
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
| Freya 5xx or 429 | Wait a minute and re-run. Do not hammer the platform. |
| `build time budget` in the trace | Model calls stop after 25 min (the page allows 30 per brief). A skipped repair round deploys the best spec so far; `build time budget used up` fails the build. Re-run; the fallback models are tried when one stalls (`timed out after`). |
| `END ok=False`, exit code 3 | The agent was saved and exported, but its chat smoke test failed (the TEST line says why). Re-run the same command; if it fails again, read the reply in the TEST line. |
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
