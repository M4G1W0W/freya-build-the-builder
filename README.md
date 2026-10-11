# Freya agent builder: YC "Build the Builder"

Our entry for Y Combinator's **Build the Builder** hackathon on [Freya](https://docs.freyavoice.ai/).
The **builder** reads a bank's collections brief and the bank's tool API (OpenAPI), then creates a phone
agent on Freya: a workflow that the organisers test against simulated customers.

## Run the builder (the submitted command)

Python 3.10+ and the standard library only. No install step is needed.

```bash
export FREYA_API_KEY=fak_...          # Freya workspace key
export FREYA_API_URL=https://staging-app.freyavoice.ai
export OPENAI_API_KEY=sk-...          # the builder's own LLM (reads the brief); the phone agent does not use it

python3 builder/build.py <case_folder> <mock_url> 2>&1 | tee traces/<name>.log      # final form
python3 builder/build.py <brief file(s)> <tool_api.json> 2>&1 | tee traces/<name>.log  # practice form
```

The final form reads every document in the folder (BRIEF.md and README.md first; .md, .txt, .json,
.docx, .xlsx, .pdf) and builds the tools from the folder's service contract, each calling
`<mock_url>` + the contract's path. Files it cannot read are a WARN in the trace, never a stop.

### Organiser re-run (fresh clone)

Only two values are needed. Nothing has to be installed.

| Variable | Needed | What it is |
|---|---|---|
| `FREYA_API_KEY` | yes | the Freya workspace key the agent is created in |
| `OPENAI_API_KEY` | yes | the key for the builder's own model calls (it reads the brief and writes the spec) |
| `FREYA_API_URL` | no | defaults to `https://staging-app.freyavoice.ai` (kit `freya.py`) |
| `BUILDER_MODEL`, `BUILDER_MODEL_FALLBACKS` | no | models tried **before** the built-in chain `gpt-6.1-sol` → `gpt-5.5` → `gpt-5.4`; a model the key cannot use is skipped |
| `OPENAI_BASE_URL` | no | an OpenAI-compatible endpoint instead of `https://api.openai.com/v1` |

`FREYA_BANK_TEAM_KEY` is used only by the kit's `run_cases.py`, not by the builder.

- **Brief files.** Several brief files are read in order. For example, pass `brief-a.md brief-b.md` when the second
  extends the first. The last argument is always the tool API.
- **Optional flags.** `--slot NAME` names the workflow slot; the default comes from the brief file names. The same
  slot is updated in place on later runs. `--export PATH` writes the exported workflow.
- **Output.** stdout gets `{"workflow_id": ..., "agent_id": ...}`. stderr gets the **trace**: start and end time,
  every model call (model and purpose), the checks and self-tests, and what was created on Freya. Secrets are
  redacted.
- **Time.** About 2 minutes per brief: 2 to 4 LLM calls, local and platform validation, deploy and publish, and a
  chat smoke test.

**How it works** (`docs/design.md`):
1. An LLM consolidates the brief. It applies memos and amendments and maps code lists.
2. The LLM extracts a strict **PolicySpec** that is cross-checked against the tool API, with automatic repair.
3. Generic code renders a staged workflow: who answered → third party / identity → engine-run `get_account` →
   code-computed facts (deadlines, floors, attempt plans, what to offer for any named date) → negotiate →
   finalize (the outcome is computed from what was actually recorded) → engine-run transfer and close.
4. Local validation runs, then Freya's dry run, then save and publish, then the smoke test.

## Development

```bash
uv sync                      # dev env (.venv, pytest, ruff)
cp .env.example .env         # fill in locally; never commit .env
make verify                  # format + lint + tests (must pass before every commit)
make help                    # dev loop: check | cases | show | call | chat | credits
```

| Command | What it does |
|---|---|
| `make cases AGENT=<agent_id> BRIEF=A REPS=3` | Practice customers (kit scorer). A case counts only at 3/3 |
| `make show RUN=runs/<file>.json` | Summary plus the failed transcripts, with tool calls and routing |
| `.venv/bin/python builder/build.py ... --spec tests/fixtures/spec_a.json` | DEV ONLY: deploy a hand-written spec (no LLM) |

## Layout

| Path | Contents |
|---|---|
| `builder/build.py` | Entry point (thin launcher) |
| `src/freya_builder/` | `cli`, `pipeline` (LLM front end), `spec`, `expr`, `render`, `codegen`, `hooks`, `nodes`, `toolapi`, `validate`, `llm`, `trace`, `platform` |
| `src/freya_builder/sandbox/` | Python that runs inside Freya code nodes. It is unit-tested exactly as deployed |
| `kit/` | The official kit, unmodified |
| `tests/` | pytest. `tests/fixtures/` holds practice-brief fixtures and synthetic unseen briefs |
| `experiments/` | Platform and model experiments with their findings |
| `docs/` | `design.md`, `hackathon_notes.md` (rules, decisions, score log), API notes, references |
| `submission/` | Exported phone agents (committed) |
| `traces/` | Builder traces (committed) |
