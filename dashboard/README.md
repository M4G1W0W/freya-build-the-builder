# Testing Command Center (read-only)

A localhost dashboard over the existing test artefacts. It never launches tests, deploys, edits files, changes git or
calls the network. It writes only `reports/latest_snapshot.{json,md}`.

```bash
.venv/bin/python dashboard/server.py            # http://127.0.0.1:8765 (loopback only)
.venv/bin/python dashboard/server.py --snapshot-only   # just write reports/latest_snapshot.* and exit
```

Data is recomputed every 12 s. The page polls every 12 s.

## Endpoints (GET only; anything else returns 405)

| Path | Content |
|---|---|
| `/api/snapshot` | The review snapshot: HEAD, latest and best strict results per panel, untested commits, regressions, failing cases, pending decisions, integrity flags, provenance |
| `/api/runs` | Every result file with its tested commit, commit source, agent version, build mode, style, per-rep and strict scores, and flags. Also lists runs that never produced a result |
| `/api/failures` | Failed reps by category, persistence, introduced, resolved, awaiting retest, and an infra-adjusted interpretation |
| `/api/overview`, `/api/builder` | Overview panels; build traces |
| `/api/case?run=<run id>&case=<PUB-xx>` | Per-rep detail: ledger diff, judge text, tools, a transcript when a call dump exists locally, and the case history |
| `/api/comparison?...` | Configuration comparison: scenario variants × exact configurations, plus a two-version diff (see below) |

## How numbers are derived

**Strict score.** The score comes from `all_rows`: a case passes only when every rep passed.

**Official-style runs.** A run counts as official-style only when all of these hold:
- it is complete;
- it covers the full case set (10 for Brief A, 3 for B or extra-B);
- it has 3 or more reps.

1-rep and subset runs are shown but never headline.

**Tested commit.** The dashboard looks up the latest build trace that published the run's agent before the run
started. The commit comes from these sources, best first, and the source used is shown with every result:
1. the trace's `START git=` (authoritative);
2. the deploy-log file name;
3. the Score log's "Git ref" (written by a person);
4. the result file name (unverified, and flagged).

It is never taken from the current HEAD.

**Agent version.** The version comes from the trace's CREATED line. Where call dumps are saved locally, their
`entityVersionNumber` is used to cross-check it.

**Failure categories.** Each failure is categorised from the ledger diff first, then by a keyword heuristic over
the judge text. The category is labelled "auto". The human classification lives in the Score log, which the case
detail quotes.

**Infra-adjusted numbers.** These are labelled INTERPRETATION and are kept apart from the strict scores.

## Known limits

- **Style and case set.** These are not recorded in the result JSON, so they are read from the file name and the
  case file (`styled*`, `extraB`, `style/<x>-<style>-`). The case file is read in its current version.
- **Transcripts.** Only calls already saved under `runs/` are shown; nothing is fetched from Freya.
- **Judge text.** It is cut at 400 characters by the kit's `run_cases.py`.
- **Older deploy traces.** Traces from before commit stamping (1a5245f) have no `git=`. Their commit falls back to
  a weaker source, and that is flagged.
- **Saved-spec inputs.** The trace does not hash the spec file. A run whose spec file was rewritten after its deploy
  is flagged "the deployed spec is not on disk".
- **Platform errors.** These need structural evidence: no tool call and 0 s turns. Sandbox output failures are
  builder-side and get their own category. Judge text that says "technical issues" only adds a tag.
- **Fixture-spec runs.** Runs from `tests/fixtures/spec_a.json` appear in the history as hollow points but are left
  out of best and trend, because they are not builder output.
- **Other files written.** Python writes its usual gitignored `__pycache__/`. `.claude/launch.json` holds the
  desktop-app preview entry (`testing-dashboard`).

## Claude session monitor (`/api/claude-activity`, `/api/claude-conversation`)

A passive, read-only view of the Claude Desktop (Code tab) session working on this repo. The session runs
**locally**: the desktop app starts a local `claude --output-format stream-json` agent and writes the transcript to
`~/.claude/projects/<project>/<cliSessionId>.jsonl` (entries tagged `entrypoint: claude-desktop`). Desktop-only
metadata (title, turns, last activity, which transcript is current) is in
`~/Library/Application Support/Claude/claude-code-sessions/*/*/local_<id>.json`. Cloud sessions keep no local data
and are not visible.

- **Which session.** `?session=<desktop or cli id>` or `DASHBOARD_SESSION`, else the non-archived session for this
  repo with the most completed turns. The choice is sticky until the server restarts.
- **Activity feed.** Tool names, Claude's own action descriptions (allowlisted fields only), outcomes, error kinds
  from a fixed vocabulary, live background processes (basenames only), and Claude's latest text. It never contains
  your prompts, thinking, tool inputs or tool output.
- **Conversation.** Your prompts (every one is kept, in full; never cut), Claude's replies (in full), and one-line background-task events.
  System reminders, thinking and tool content are left out. Secrets are redacted and e-mails masked. It is written
  to `reports/latest_conversation.{json,md}` for an external reviewer (`reports/` is gitignored).
- **Safety.** Files are opened read-only. The only subprocess is `ps`. Requests whose Host is not
  `127.0.0.1:<port>` or `localhost:<port>` get 403 (DNS-rebinding guard).
- **Limits.**
  - Only the session's current transcript is read. Prompts from before a context save are in older transcripts.
  - "Open tasks" are background launches with no recorded completion. Only the live processes prove that work is
    running.

## Failure evidence (`/api/failure-details`, `/api/failure-detail`)

A per case-and-rep evidence view for independent review. It uses local artefacts only and makes no Freya calls.

| Endpoint | Content |
|---|---|
| `GET /api/failure-details` | Every failed rep, grouped as completed official-style runs vs completed non-official runs (1-rep or subset). Incomplete runs are listed separately. Each rep shows which evidence exists locally (raw call dump, formatted transcript, or the result row only). |
| `GET /api/failure-detail?run=<run id>&case=<PUB-xx>&rep=<n>` | The full evidence for one rep (passing reps work too); see the sections below. Without `rep`, the first failed rep is shown and `case.rep_note` says so. Status codes: 400 if `rep` is not a positive integer, 404 for an unknown run or case or a rep out of range, 500 for an internal error (never 200 with an error inside). |

Sections returned by `/api/failure-detail`:
- **`result`:** raw rep pass/fail, all reps, the strict pass of the case in this run, call id, tools, end reason.
- **`classification`:** the auto category plus its evidence (structural check, ledger diff, the matched keyword
  with context). **`platform_adjusted_interpretation`** is reported separately.
- **`judge`:** the result-row text (cut at 400 characters by the kit), plus the full verdict and the messages it
  cites, taken from the raw call record.
- **`bank_records`:** ledger differences (actual vs expected), the expected ledger from the case file, and the bank
  writes seen in the call (arguments and bank responses). The final ledger itself is marked *Not available*,
  because run_cases does not save it.
- **`transcript`:** customer and agent messages, numbered from 0 as the judge counts them, with tool calls, routes
  and errors. The headers of tool requests are never included.
- **`date_chain`** (date failures): customer wording → runtime date facts (`today_facts`, `date_table`,
  `account_facts` from the workflow snapshot) → proposed dates → confirmation → recorded promise. It covers the
  negotiation step only; messages are selected by keyword, not interpretation.
- **`multi_product`** (multi-product cases): for each product, what the bank loaded, the agent messages that name
  it, notes and promises recorded, and the expected records. Attempts are *not* counted for you.
- **`provenance`:**
  - commit and its source;
  - the agent version that was deployed and the version that answered the call;
  - the deploy trace;
  - fresh extraction vs saved-spec build;
  - the input sha256 from the trace;
  - the current spec hash, with a note when the spec was rewritten after the deploy;
  - the assigned speech style. The actual style is *Not available*: the call record does not carry the persona.
- **`timestamps`:** simulation id, estimated simulation start, run end, and the call's created, started, ended and
  updated times. Verdict arrival is *Not available*: Freya does not record it.

Evidence strength depends on what was saved. A raw call dump (`runs/**/<call>.json`, written by
`freya.get_call`) gives everything above. Without one, only the result row, the case file and the deploy trace are
used, and every other field says *Not available*.

More detail on the evidence fields:
- **Bank writes.** Engine-run bank calls appear as `api_call:<endpoint>` (for example `api_call:close_call`).
- **Transcript sources.** A `.txt`-only transcript is parsed too (labelled as such). It has no runtime variables,
  and its tool text is cut at 300 characters.
- **Speech style.** It comes from the styled case file, or from the run's file name, with the source labelled.
  Otherwise it is *not recorded*: run_cases does not save `--style`.
- **Judge field.** A missing judge verdict ("analysis never arrived") is classified as a platform error. A failed rep
  without a judge line means the judge passed and the failure is in the ledger.
- **Simulation id.** run_cases records only the last rep's simulation id, so earlier reps report *Not available*.

## Configuration comparison (`/api/comparison`, tab "Config Comparison")

A matrix of scenario variants (rows) × exact configurations (columns), plus a two-version comparison. It is built
from the same run records as the other views (`dashboard/compare.py`), the build traces, and `git log`/`git show`
of the case files. It makes no Freya calls and writes nothing.

```
GET /api/comparison?brief=A&case=PUB-06&style=talkative&config=<id>,<id>&from=2026-10-10&to=2026-10-11&a=<id>&b=<id>
```

Every parameter is optional; `a` and `b` go together. `style` takes a style name or `unknown`. `from`/`to` are UTC
`YYYY-MM-DD` (inclusive days) or `YYYY-MM-DDTHH:MM[:SS]Z` and filter on the run's end time. Configuration ids are in
`options.configs`. A bad parameter returns 400 with `{"error": ...}`.

**Configuration (column).** One deployment: the build trace that published the agent before the run. Its id is
`deploy:<trace path>`. It carries:
- the commit and its source, and the dirty flag;
- the in-memory experiment variants written in the trace (`exp07 variant=...`);
- the agent, slot and version (with source);
- fresh extraction vs saved spec, the spec path and its status;
- the input sha256 recorded by the trace at build time.

A run without a usable trace gets `untraced:<agent>:<claimed commit>`, and so does a run whose time-matched trace
predates the tested commit. No current spec hash is shown: the trace does not hash the spec, and the current file
is not evidence of what was deployed.

**Scenario variant (row).** It is grouped by brief and policy family and made of:
- the case id;
- the test definition: the case file, plus a sha256 of that case's JSON in the version committed when the run
  started (`git log`/`git show`);
- the speech style.

The style comes only from a styled case file's `style` field. Run-file name tokens (`-talkative`, `-asks`) are
never used, so those runs show `unknown`.

**Cell.** Every run of that configuration on that variant stays a separate entry. Each entry has:
- passes/reps;
- strict (complete run, 3+ reps, every rep passed), or `null` with the reason;
- the failed reps, with `/api/failure-detail` links;
- the configuration and definition flags;
- whether the run is comparable;
- the platform interpretation, beside the raw result and never changing it.

The cell `status` (pass, fail or mixed) uses comparable runs only. Reps of different runs are never added up, and
no retry is preferred over another.

**Two-version comparison (`a`, `b`).** Rows match only on the same case, the same definition hash and a known,
equal style. The buckets are:
- `newly_failing`, `newly_passing`, `unchanged_pass`, `unchanged_fail`;
- `inconsistent`: the runs of one configuration disagree;
- `untested`: tested on one side only, or no comparable strict result on one side (1-rep, incomplete, or a
  configuration flag such as a redeploy during the run or an agent-version mismatch);
- `unmatched_coverage`: shown, never counted. The case ran under another definition or style, or the style was not
  recorded on either side.

`untested_by_both` lists the case ids of the involved briefs that neither side ran. `differences` and
`provenance_warnings` show what differs between the two configurations and what is uncertain about each. There is
no ranking: columns are ordered by deploy time.

**Incomplete runs.** These are runs with no result JSON. They are listed separately with the per-case reps parsed
from their console log: a rep counts once its `-- run k of N` line is written. They are never strict, and their
configuration is not determinable (the log has no agent id).

**Limits.**
- `run_cases` records neither `--cases` nor `--style`. The case file is attributed by the run file's name
  (`styled*`/`extraB`, else the kit's public set).
- The real arguments sit in launcher scripts in session scratchpads, outside the repo, and are not read.
- Uncommitted edits to a case file cannot be detected.

Tests: `uv run pytest dashboard/test_compare.py` (synthetic records, no network).
