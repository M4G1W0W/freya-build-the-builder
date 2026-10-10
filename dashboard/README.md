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
