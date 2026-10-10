# RUNBOOK: Sunday 11 Oct, hidden briefs (17:00–20:00 UTC = 20:00–23:00 Istanbul)

The requirements come from `docs/hackathon_notes.md` → Submission (official page + kit README). Times are UTC.

## Before 17:00

- [ ] **15:30 freeze.** `make verify` is green, then `git tag freeze-final`. After this, only generic crash and bug
      fixes are allowed.
- [ ] `git status` is clean. `date -u` is checked.
- [ ] `set -a && source .env && set +a`. The FREYA_* vars, OPENAI_API_KEY, BUILDER_MODEL and
      BUILDER_MODEL_FALLBACKS are set.
- [ ] Decisions from the user are in: the **team name**, **repo visibility** (public, or private with organiser access)
      and the **OpenAI key question for the organisers' re-run** (see Open questions).
- [ ] Practice the commands below once on `kit/briefs/brief-a.md` with slot `rehearsal`, so the steps are warm.

## 17:00: the hidden briefs arrive

**HARD RULE: write nothing from a hidden brief into the repo except `traces/` and `submission/`.** That means no
rule, value, name, date or code in `src/`, `builder/`, `tests/`, fixtures or prompts. Only generic bug fixes, which
must make sense for any brief.

1. Save the files **outside the repo** (for example `~/hidden/`). Note the file names and check whether a brief says it
   builds on another brief.
2. The official run command is `python3 builder/build.py {brief_path} {tool_api_path}`. Here the system `python3` is
   3.9, so put the venv first on PATH. The command stays the same:

```bash
export PATH="$PWD/.venv/bin:$PATH"
python3 --version   # must be 3.10+
python3 builder/build.py ~/hidden/<brief-1> ~/hidden/<api-1> --export submission/hidden-1.workflow.json 2>&1 | tee traces/hidden-1.log
python3 builder/build.py ~/hidden/<brief-2> ~/hidden/<api-2> --export submission/hidden-2.workflow.json 2>&1 | tee traces/hidden-2.log
```

   Each build takes about 2 minutes. They can run one after the other or in two terminals (separate slots, no
   simulation slot needed).
3. Read each trace. Check for:
   - `END ok=True`;
   - `spec check: PASS`;
   - `local workflow validation: PASS` and `platform dry-run validation: PASS`;
   - `chat smoke test: PASS`;
   - the number of steps and tools;
   - for the raw-material brief, the `amendment:` lines. **Every memo change must be listed.**
4. If a build fails or looks wrong, **re-run the same command.** That updates the same slot in place and the new
   trace replaces the old one. Never edit the agent by hand. If it fails again, read the error. A **generic** fix to
   the builder is allowed: commit it, then re-run.
5. Secret check, then commit:

```bash
.venv/bin/python scripts/check_secrets.py traces/hidden-*.log submission/hidden-*.workflow.json
git add traces/ submission/ && git commit -m "Submission: hidden briefs 1-2 agents + traces"
git tag submission-final
```

6. **Push only with the user's go-ahead.** Then send the form (JSON) to the address in the kit email, with these fields:
   - `team`;
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
| `python3` is 3.9 | Run `export PATH="$PWD/.venv/bin:$PATH"` (`build.py` exits with a clear message on < 3.10). |
| A brief builds on another brief | The run command takes one brief. Pass both brief files in order: the builder accepts several briefs before the tool API, as with A+B. Note it in the form. |

## Open questions (for the user, before Sunday)

- The organisers re-run the top 10 builders. Ours needs an `OPENAI_API_KEY` ("You pay for your builder's own model
  calls"). How will they get a key? Options: we give them one with a spending limit, or we ask the organisers how
  they want it.
- Repo visibility and team name (for the form).
