"""Configuration comparison: scenario variants x exact configurations (read-only).

Built from data.py's run records, the build traces that published each agent, the console logs of runs
that never wrote a result, and the git history of the case files (`git log` / `git show`, read-only).
No network, no writes.

- A configuration is one deployment: the build trace that published the run's agent before the run
  (commit and dirty flag, agent and version, saved spec vs fresh extraction, in-memory experiment
  variants recorded in the trace). A run without a usable trace gets an "untraced" configuration.
- A scenario variant (matrix row) is a case id + its test definition (the case file, and a hash of that
  case in the version committed when the run started) + its speech style. The style comes only from a
  styled case file's `style` field; run-file names never set it, so it is otherwise unknown.
- A cell keeps every run apart. Strict = every rep passed, for complete runs with 3+ reps only.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import data as D

PLATFORM = "Platform errors"
MIN_STRICT_REPS = 3
NEAR_S = 300  # a case-file commit this close before a run's (late) start estimate makes its version uncertain
CASES_DIR = "tests/fixtures/cases/"
UNTRUSTED_DEPLOY = (
    "started before commit"  # data.py: the time-matched trace predates the tested commit
)
BREAKS = (  # run flags that make the run's configuration uncertain: kept out of the comparison buckets
    "redeployed DURING",
    "different agent version",
    "made after this run started",
)
RUN_NOTES = ("File name says", "Score log records", "Tested commit")
STYLE_UNKNOWN = "unknown: run_cases does not record --style, and run-file names are not used"
BUCKETS = (
    "newly_failing",
    "newly_passing",
    "unchanged_pass",
    "unchanged_fail",
    "inconsistent",
    "untested",
    "unmatched_coverage",
)
DEFINITIONS = [
    "Configuration: one deployment, from the build trace that published the agent before the run "
    "(commit, dirty flag, agent and version, fresh extraction vs saved spec, in-memory experiment "
    "variants). Runs on the same deployment share a column.",
    "Scenario variant (row): case id + test definition (case file + hash of that case in the version "
    "committed when the run started) + speech style.",
    "Cell: every run of that configuration on that variant, kept apart. Strict needs a complete run "
    "with 3+ reps; 1-rep and incomplete runs show their reps but no strict result.",
    "Cell status (for comparisons): pass or fail when every comparable run agrees, mixed when they "
    "disagree. Reps of different runs are never added up.",
    "Platform interpretation is reported beside the raw result and never changes it. It uses only "
    "structural evidence: no tool call with 0 s turns, or no judge verdict (data.classify).",
]
LIMITATIONS = [
    "run_cases records neither --cases nor --style. The case file is attributed by the run file's "
    "name (styled*/extraB prefixes, else the kit's public set). A speech style is known only when that "
    "case file gives one; name tokens such as '-talkative' are not used, so those runs show 'unknown'.",
    "Launcher scripts in session scratchpads hold the real --style/--cases arguments, but they live "
    "outside the repo, use shell variables and are not read.",
    "The case definition is the version committed when the run started. Uncommitted edits to a "
    "case file cannot be detected.",
    "Saved-spec builds: the trace does not hash the spec file, so the deployed spec content cannot be "
    "verified. No current spec hash is shown as a deployed one.",
    "Traces from before commit stamping (1a5245f) record neither git= nor the dirty flag.",
    "Runs that never wrote a result JSON are listed apart from the matrix, from their console log: "
    "no agent id and no call ids, never a strict score.",
    "No ranking: columns are ordered by deploy time, and coverage differs between configurations.",
]


class QueryError(ValueError):
    """A bad /api/comparison parameter (HTTP 400)."""


# ---------------------------------------------------------------- configurations


def _trace_extras(deploy_log: str) -> dict:
    """What parse_trace skips: `expNN variant=...` lines (in-memory patches) and START sha256=."""
    try:
        text = (D.ROOT / deploy_log).read_text(errors="replace")
    except OSError:
        return {"variants": [], "input_sha256": None}
    variants = [D.redact(v.strip())[:160] for v in re.findall(r"^exp\w* variant=.*$", text, re.M)]
    start = text.splitlines()[0] if text else ""
    sha = re.search(r"\bsha256=(\S+)", start)
    return {"variants": variants, "input_sha256": sha.group(1) if sha else None}


def _config(run: dict, traces: dict[str, dict], commits: list[dict]) -> dict:
    trace = traces.get(run["deploy_log"]) if run.get("deploy_log") else None
    flags: list[str] = []
    if trace and any(UNTRUSTED_DEPLOY in f for f in run["flags"]):
        trace = None
        flags.append(
            "The build trace matched by time predates the tested commit: this deployment's trace is missing"
        )
    if not trace or not trace.get("created"):
        claimed = run.get("commit")
        impossible = any("made after this run started" in f for f in run["flags"])
        commit = None if impossible else claimed
        flags.insert(
            0,
            "No build trace for this deployment: build mode, spec, version and dirty state unknown",
        )
        flags += [
            f for f in run["flags"] if f.startswith("Tested commit") or "made after this run" in f
        ]
        cfg = {
            "id": f"untraced:{run.get('agent_id') or 'unknown'}:{claimed or 'unknown'}",
            "traced": False,
            "deploy_log": None,
            "deploy_time": None,
            "commit": commit,
            "commit_source": (
                f"none: the claimed {claimed} ({run.get('commit_source')}) was made after this run started"
                if impossible
                else run.get("commit_source") or "unknown"
            ),
            "dirty": None,
            "experiment_variants": [],
            "agent_id": run.get("agent_id"),
            "slot": run.get("slot"),
            "workflow_id": None,
            "version": None,
            "version_source": None,
            "agent_kind": run.get("agent_kind"),
            "build_mode": "unknown (no build trace)",
            "spec": None,
            "spec_status": None,
            "input_sha256": None,
            "briefs": [],
        }
    else:
        created = trace["created"]
        extras = _trace_extras(trace["file"])
        version = created["version"] or trace.get("published_version")
        if trace["git"]:
            commit, csrc = trace["git"], "build trace START git="
        elif trace["label"]:
            commit = trace["label"]
            csrc = "deploy-log file name (not verified as HEAD; dirty state not recorded)"
        else:
            commit, csrc = None, "not recorded by the build trace"
        if not trace["git"]:
            flags.append(
                "The trace predates commit stamping: "
                + ("commit from the deploy-log file name only" if commit else "commit not recorded")
                + "; dirty state not recorded"
            )
        if trace["dirty"]:
            flags.append(
                "Built with uncommitted changes (dirty=True): the commit does not identify the code"
            )
        flags += [
            f"In-memory experiment variant applied at build time (in the trace, not in git): {v}"
            for v in extras["variants"]
        ]
        spec_status = None
        if trace["spec"]:
            spec = D.ROOT / trace["spec"]
            if not spec.exists():
                spec_status = "spec file no longer on disk"
            elif spec.stat().st_mtime > created["ts"]:
                spec_status = "rewritten after this deploy: the deployed spec is not on disk"
            else:
                spec_status = (
                    "file unchanged since this deploy (by mtime); content still not hashed"
                )
            flags.append(f"Saved spec {trace['spec']}: {spec_status}")
            if trace["spec"].startswith("tests/fixtures"):
                flags.append("Hand-written fixture spec: renderer-only, not builder output")
        if version is None:
            flags.append("Agent version not recorded by the trace")
        cfg = {
            "id": f"deploy:{trace['file']}",
            "traced": True,
            "deploy_log": trace["file"],
            "deploy_time": created["time"],
            "commit": commit,
            "commit_source": csrc,
            "dirty": trace["dirty"],
            "experiment_variants": extras["variants"],
            "agent_id": created.get("agent_id") or run.get("agent_id"),
            "slot": trace.get("slot") or run.get("slot"),
            "workflow_id": created.get("workflow_id"),
            "version": version,
            "version_source": (
                "trace CREATED line"
                if created["version"]
                else "trace 'published version' line"
                if version is not None
                else None
            ),
            "agent_kind": run.get("agent_kind"),
            "build_mode": {
                "saved-spec": "saved spec (--spec; no LLM extraction)",
                "full-builder": "fresh extraction (full builder: brief -> LLM -> spec)",
            }.get(trace["mode"], trace["mode"]),
            "spec": trace["spec"],
            "spec_status": spec_status,
            "input_sha256": extras["input_sha256"],
            "briefs": trace["briefs"],
        }
    info = D.resolve(commits, cfg["commit"])
    cfg["commit_subject"] = info["subject"] if info else None
    cfg["label"] = _label(cfg)
    cfg["flags"] = flags
    cfg["run_commit_claims"] = []
    return cfg


def _label(cfg: dict) -> str:
    commit = (cfg["commit"] or "?")[:7] + ("+dirty" if cfg["dirty"] else "")
    who = cfg["slot"] or (cfg["agent_id"] or "?")[:8]
    mode = (
        "fresh"
        if cfg["build_mode"].startswith("fresh")
        else "saved spec"
        if cfg["build_mode"].startswith("saved")
        else "untraced"
    )
    variant = re.search(r"variant=([^\s:]+)", " ".join(cfg["experiment_variants"]))
    return " · ".join(
        x
        for x in (commit, f"{who} v{cfg['version'] if cfg['version'] is not None else '?'}", mode)
        + ((f"variant {variant.group(1)}",) if variant else ())
    )


def _same(a: str | None, b: str | None) -> bool:
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def _claim(cfg: dict, run: dict) -> None:
    """Commit evidence of a run (its own source, the Score log, its file name) that differs from the configuration's."""
    claims = [(run.get("commit"), run.get("commit_source"))]
    claims += [
        (r, "Score log 'Git ref' (human-recorded)") for r in D.score_log_refs(Path(run["id"]).name)
    ]
    claims.append((run.get("label"), "result file name (not verified)"))
    for commit, source in claims:
        entry = {"run": run["id"], "commit": commit, "source": source}
        if commit and not _same(commit, cfg["commit"]) and entry not in cfg["run_commit_claims"]:
            cfg["run_commit_claims"].append(entry)


# ---------------------------------------------------------------- test definitions (git history)

_versions: dict[tuple[str, str], dict[str, dict]] = {}


def _history(path: str) -> list[tuple[str, int]]:
    """Commits touching `path`, newest first: (full hash, commit time)."""
    out = D.git("log", "--format=%H %ct", "--", path)
    return [(h, int(t)) for h, t in (ln.split() for ln in out.splitlines() if ln.strip())]


def _cases_at(commit: str, path: str) -> dict[str, dict]:
    key = (commit, path)
    if key not in _versions:  # a commit's content never changes: cache for the server's lifetime
        try:
            data = json.loads(D.git("show", f"{commit}:{path}") or "null")
        except ValueError:
            data = None
        if isinstance(data, dict):
            data = data.get("cases", [])
        _versions[key] = {c["id"]: c for c in data or [] if isinstance(c, dict) and "id" in c}
    return _versions[key]


def case_hash(case: dict) -> str:
    return hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:10]


def git_definition(path: str, case_id: str, start_ts: float, end_ts: float, history=None) -> dict:
    """The case as committed when the run started (run_cases records no case file or content)."""
    hist = (history or {}).get(path)
    if hist is None:
        hist = _history(path)
        if history is not None:
            history[path] = hist
    flags: list[str] = []
    source = "git version committed at the run's start"
    if not hist:
        commit, source = None, "CURRENT case file (not in git history; not historical)"
        cases = D.load_cases(path.removeprefix(CASES_DIR) if path.startswith(CASES_DIR) else None)
        flags.append("Case file not in git history: the current file is used (not historical)")
    else:
        before = [h for h in hist if h[1] <= start_ts]
        commit = before[0][0] if before else hist[-1][0]
        if not before:
            source = "first committed version (ASSUMED: the file was not yet committed at the run's start)"
            flags.append(
                "Case file not yet committed at the run's estimated start: its first committed version is assumed"
            )
        if any(start_ts - NEAR_S < t <= end_ts for _, t in hist):
            flags.append(
                "The case file was committed within 5 min before the run's estimated start or during "
                "the run: the version the run used is uncertain"
            )
        cases = _cases_at(commit, path)
    case = cases.get(case_id)
    if case is None:
        flags.append(f"{case_id} not found in that version of {path}")
    return {
        "file": path,
        "commit": commit[:7] if commit else None,
        "hash": case_hash(case) if case else None,
        "case": case,
        "flags": flags,
        "source": source,
        "historical": source.startswith("git version"),
    }


def _case_path(case_file: str) -> str:
    return case_file if case_file.startswith("kit/") else CASES_DIR + case_file


# ---------------------------------------------------------------- rows and cell entries


def _row(case: dict, run: dict, d: dict) -> dict:
    cdef = d["case"] or {}
    style = cdef.get("style") if cdef else None
    return {
        "id": "|".join(
            (
                case["id"],
                d["file"],
                ("" if d.get("historical", True) else "unverified:") + (d["hash"] or "unknown"),
                style or "style-unknown",
            )
        ),
        "case": case["id"],
        "title": cdef.get("title"),
        "brief": cdef.get("brief") or run.get("brief") or "?",
        "family": cdef.get("family") or case.get("family") or "?",
        "definition": {
            "file": d["file"],
            "hash": d["hash"],
            "hash_of": "sha256 of the case's JSON in the "
            + d.get("source", "git version committed at the run's start"),
            "attributed_by": "run file name convention (styled*/extraB prefix, else the kit public set); "
            "run_cases does not record --cases",
            "commits": [],
        },
        "style": style,
        "style_source": "styled case file 'style' field" if style else STYLE_UNKNOWN,
    }


def _entry(run: dict, case: dict, cfg_id: str, row_id: str, d: dict) -> dict:
    reps = list(case["reps"])
    recorded = [r for r in reps if r is not None]
    strict_ok = run["complete"] and run["reps"] >= MIN_STRICT_REPS and len(recorded) == run["reps"]
    if strict_ok:
        note = None
    elif not run["complete"] or len(recorded) < run["reps"]:
        note = f"incomplete: {len(recorded)} of {run['reps']} reps recorded; no strict result"
    else:
        note = f"{run['reps']}-rep run: no strict result (needs {MIN_STRICT_REPS}+ reps)"
    failed = [
        {
            "rep": f["rep"],
            "category": f["category"],
            "platform_evidence": f["category"] == PLATFORM,
            "call_id": f.get("call_id"),
            "evidence": f"/api/failure-detail?run={quote(run['id'])}&case={quote(case['id'])}&rep={f['rep']}",
        }
        for f in case["failures"]
    ]
    platform = [f["rep"] for f in failed if f["platform_evidence"]]
    interp = None
    if platform:
        real = len(failed) - len(platform)
        valid = len(recorded) - len(platform)
        interp = {
            "label": "INTERPRETATION, not a score: reps with structural platform evidence set aside",
            "reps_with_platform_evidence": platform,
            "failed_reps_without_platform_evidence": real,
            "if_set_aside": "no valid reps left"
            if valid <= 0
            else f"passes on the other {valid} rep(s) (not a strict {len(recorded)}/{len(recorded)})"
            if real == 0
            else "still fails",
        }
    breaks = [f for f in run["flags"] if any(b in f for b in BREAKS)]
    why_not = [] if strict_ok else [note]
    why_not += [f"configuration uncertain: {f}" for f in breaks]
    if d["hash"] is None:
        why_not.append("test definition not found")
    elif not d.get("historical", True):
        why_not.append("test definition not verifiable: " + d.get("source", ""))
    return {
        "row": row_id,
        "config": cfg_id,
        "run": run["id"],
        "run_name": run["name"],
        "end": run["end"],
        "end_ts": run["end_ts"],
        "reps": reps,
        "passes": sum(1 for r in recorded if r),
        "reps_recorded": len(recorded),
        "reps_planned": run["reps"],
        "complete": run["complete"],
        "official_style_run": run["official_style"],
        "strict": all(recorded) if strict_ok else None,
        "strict_note": note,
        "failed_reps": failed,
        "platform_interpretation": interp,
        "attribution_flags": breaks,
        "run_notes": [f for f in run["flags"] if f.startswith(RUN_NOTES)],
        "definition_commit": d["commit"],
        "definition_flags": d["flags"],
        "definition_uncertain": bool(d["flags"]),
        "comparable": not why_not,
        "not_comparable_because": why_not,
    }


# ---------------------------------------------------------------- incomplete runs (console logs)

CASE_LINE = re.compile(r"^(PASS|FAIL) (\S+) +\S+ +(.*?) *\|")
SEP = re.compile(r"^-- run (\d+) of (\d+):")


def parse_partial_log(text: str) -> dict:
    """Per-rep PASS/FAIL lines of a run_cases console log; a rep counts once its '-- run k of N' line is written."""
    reps: list[dict[str, tuple[bool, str]]] = []
    current: dict[str, tuple[bool, str]] = {}
    planned = None
    for line in text.splitlines():
        m = CASE_LINE.match(line)
        if m:
            current[m.group(2)] = (m.group(1) == "PASS", m.group(3).strip())
            continue
        if line.startswith("-- run discarded"):
            current = {}
            continue
        s = SEP.match(line)
        if s:
            reps.append(current)
            current, planned = {}, int(s.group(2))
    ids = sorted({cid for rep in reps for cid in rep})
    return {
        "reps_planned": planned,
        "reps_completed": len(reps),
        "unterminated_case_lines": len(current),
        "cases": [
            {
                "id": cid,
                "family": next(rep[cid][1] for rep in reps if cid in rep),
                "reps": [rep[cid][0] if cid in rep else None for rep in reps],
            }
            for cid in ids
        ],
    }


def partial_runs(incomplete: list[dict], definition_of) -> list[dict]:
    out = []
    for i in incomplete:
        try:
            parsed = parse_partial_log((D.ROOT / i["file"]).read_text(errors="replace"))
        except OSError:
            parsed = parse_partial_log("")
        ts = D.parse_utc(i["time"]) if i.get("time") else 0.0
        name = i["file"].rsplit("/", 1)[-1].removesuffix(".log")
        case_file, _ = D.case_file_for(name)
        path = _case_path(case_file or "kit/public-test-set.json")
        for c in parsed["cases"]:
            d = definition_of(path, c["id"], ts, ts)
            cdef = d["case"] or {}
            c.update(
                brief=cdef.get("brief") or "?",
                style=cdef.get("style"),
                definition={"file": path, "hash": d["hash"], "flags": d["flags"]},
            )
        out.append(
            {
                "file": i["file"],
                "time": i.get("time"),
                "ts": ts,
                "status": i.get("status"),
                "reason": i.get("reason"),
                **parsed,
                "strict": None,
                "strict_note": "incomplete run: never a strict score (no result JSON)",
                "configuration": "Not determinable: the console log has no agent id; the file-name "
                f"label {i.get('label') or 'none'} is not evidence",
                "call_evidence": "Not available: console logs carry no call ids",
            }
        )
    return out


# ---------------------------------------------------------------- base model (computed every refresh)


def build(
    runs: list[dict],
    incomplete: list[dict],
    traces: list[dict],
    commits: list[dict],
    definition_of=None,
) -> dict:
    history: dict[str, list] = {}
    definition_of = definition_of or (lambda p, cid, s, e: git_definition(p, cid, s, e, history))
    by_file = {t["file"]: t for t in traces}
    configs: dict[str, dict] = {}
    rows: dict[str, dict] = {}
    entries: list[dict] = []
    for run in runs:
        cfg = _config(run, by_file, commits)
        cfg = configs.setdefault(cfg["id"], cfg)
        cfg.setdefault("first_run_ts", run["end_ts"])
        _claim(cfg, run)
        path = _case_path(run["case_file"])
        start = run["end_ts"] - (run.get("seconds") or 0)
        for case in run["cases"]:
            d = definition_of(path, case["id"], start, run["end_ts"])
            new = _row(case, run, d)
            row = rows.setdefault(new["id"], new)
            if d["commit"] and d["commit"] not in row["definition"]["commits"]:
                row["definition"]["commits"].append(d["commit"])
            entries.append(_entry(run, case, cfg["id"], row["id"], d))
    return {
        "configs": configs,
        "rows": rows,
        "entries": entries,
        "partial": partial_runs(incomplete, definition_of),
    }


# ---------------------------------------------------------------- query: filters, matrix, comparison


def _day_bound(text: str, end: bool) -> float:
    text = text.strip().removesuffix("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            ts = float(calendar.timegm(time.strptime(text, fmt)))
        except ValueError:
            continue
        return ts + 86399 if end and fmt == "%Y-%m-%d" else ts
    raise QueryError(f"bad date {text!r}: use YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS]Z (UTC)")


def _one(q: dict[str, list[str]], key: str) -> str:
    vals = q.get(key, [])
    if len(vals) > 1:
        raise QueryError(f"{key} given more than once")
    return vals[0].strip() if vals else ""


def filters(base: dict, q: dict[str, list[str]]) -> dict:
    rows, configs = base["rows"].values(), base["configs"]
    briefs = {r["brief"] for r in rows}
    cases = {r["case"] for r in rows}
    styles = {r["style"] or "unknown" for r in rows} | set(D.STYLES) | {"unknown"}
    f = {k: _one(q, k) for k in ("brief", "case", "style", "from", "to", "a", "b")}
    if f["brief"] and f["brief"] not in briefs:
        raise QueryError(f"unknown brief {f['brief']!r}; known: {sorted(briefs)}")
    if f["case"] and f["case"] not in cases:
        raise QueryError(f"unknown case {f['case']!r}")
    if f["style"] and f["style"] not in styles:
        raise QueryError(f"unknown style {f['style']!r}; known: {sorted(styles)}")
    f["config"] = [c for v in q.get("config", []) for c in v.split(",") if c.strip()]
    for c in f["config"] + [x for x in (f["a"], f["b"]) if x]:
        if c not in configs:
            raise QueryError(f"unknown configuration {c!r}")
    if bool(f["a"]) != bool(f["b"]):
        raise QueryError("a two-version comparison needs both a and b")
    if f["a"] and f["a"] == f["b"]:
        raise QueryError("a and b are the same configuration")
    f["from_ts"] = _day_bound(f["from"], end=False) if f["from"] else None
    f["to_ts"] = _day_bound(f["to"], end=True) if f["to"] else None
    return f


def _row_ok(row: dict, f: dict) -> bool:
    return (
        (not f["brief"] or row["brief"] == f["brief"])
        and (not f["case"] or row["case"] == f["case"])
        and (not f["style"] or (row["style"] or "unknown") == f["style"])
    )


def _time_ok(ts: float, f: dict) -> bool:
    return (f["from_ts"] is None or ts >= f["from_ts"]) and (f["to_ts"] is None or ts <= f["to_ts"])


def status(entries: list[dict]) -> str | None:
    vals = [e["strict"] for e in entries if e["comparable"]]
    if not vals:
        return None
    return "pass" if all(vals) else "fail" if not any(vals) else "mixed"


def _cell(entries: list[dict]) -> dict:
    return {
        "entries": [
            {k: v for k, v in e.items() if k not in ("row", "config", "end_ts")} for e in entries
        ],
        "status": status(entries),
        "runs": len(entries),
        "comparable_strict_runs": sum(e["comparable"] for e in entries),
        "reps_recorded": sum(e["reps_recorded"] for e in entries),
    }


def _row_order(rows: list[dict]) -> list[dict]:
    num = lambda cid: int(m.group(1)) if (m := re.search(r"(\d+)$", cid)) else 999  # noqa: E731
    family_rank: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r["brief"], r["family"])
        family_rank[key] = min(family_rank.get(key, 999), num(r["case"]))
    return sorted(
        rows,
        key=lambda r: (
            r["brief"],
            family_rank[(r["brief"], r["family"])],
            r["family"],
            num(r["case"]),
            r["definition"]["file"],
            r["style"] or "~",
            r["definition"]["hash"] or "~",
        ),
    )


def _side(entries: list[dict]) -> dict:
    return {
        "status": status(entries),
        "runs": [
            {
                "run": e["run"],
                "end": e["end"],
                "result": f"{e['passes']}/{e['reps_recorded']}",
                "strict": e["strict"],
                "comparable": e["comparable"],
                "not_comparable_because": e["not_comparable_because"],
                "failed_reps": [
                    {"rep": x["rep"], "evidence": x["evidence"]} for x in e["failed_reps"]
                ],
                "platform_interpretation": e["platform_interpretation"],
                "definition_flags": e["definition_flags"],
            }
            for e in entries
        ],
    }


DIFF_FIELDS = (
    "commit",
    "dirty",
    "experiment_variants",
    "build_mode",
    "spec",
    "agent_kind",
    "slot",
    "agent_id",
    "workflow_id",
    "version",
    "deploy_time",
)


def compare(base: dict, f: dict, rows: list[dict], scope: list[dict]) -> dict:
    """Two-version comparison over `rows` (every filter applied). Only same case + definition + known
    style match. `scope` = the rows of the brief/case filters under any style: coverage the style
    filter hides is still reported as unmatched, never as untested."""
    a, b = f["a"], f["b"]
    pick: dict[str, dict[str, list[dict]]] = {"a": {}, "b": {}}
    tested: dict[str, dict[str, list[str]]] = {"a": {}, "b": {}}  # side -> case -> rows with runs
    shown = {r["id"] for r in rows}
    for side, cfg in (("a", a), ("b", b)):
        for r in scope:
            runs = [
                e
                for e in base["entries"]
                if e["row"] == r["id"] and e["config"] == cfg and _time_ok(e["end_ts"], f)
            ]
            if r["id"] in shown:
                pick[side][r["id"]] = runs
            if runs:
                tested[side].setdefault(r["case"], []).append(r["id"])
    out: dict[str, list] = {k: [] for k in BUCKETS}
    for r in rows:
        ea, eb = pick["a"][r["id"]], pick["b"][r["id"]]
        if not ea and not eb:
            continue
        item = {
            "case": r["case"],
            "row": r["id"],
            "family": r["family"],
            "brief": r["brief"],
            "definition": f"{r['definition']['file']} #{r['definition']['hash']}",
            "style": r["style"] or "unknown",
            "a": _side(ea),
            "b": _side(eb),
        }
        sa, sb = item["a"]["status"], item["b"]["status"]
        if ea and eb and not r["style"]:
            item["reason"] = (
                "speech style not recorded for this variant: a style match cannot be verified, so it "
                f"is not counted (raw statuses: a={sa or 'no strict result'}, b={sb or 'no strict result'})"
            )
            out["unmatched_coverage"].append(item)
        elif ea and eb:
            if sa is None or sb is None:
                why = sorted({w for e in ea + eb for w in e["not_comparable_because"]})
                missing = " and ".join(s for s, v in (("a", sa), ("b", sb)) if v is None)
                item["reason"] = f"no comparable strict result in {missing}: " + "; ".join(why)
                out["untested"].append(item)
            elif "mixed" in (sa, sb):
                item["reason"] = "runs of one configuration disagree: no single status"
                out["inconsistent"].append(item)
            elif sa == sb:
                out[f"unchanged_{sa}"].append(item)
            else:
                out["newly_passing" if sb == "pass" else "newly_failing"].append(item)
        else:
            side, other = ("a", "b") if ea else ("b", "a")
            elsewhere = tested[other].get(r["case"], [])
            if elsewhere:
                item["reason"] = (
                    f"{other} ran this case only under another test definition or speech style"
                    + (" (possibly outside the style filter)" if f["style"] else "")
                )
                item["other_variants"] = elsewhere
                out["unmatched_coverage"].append(item)
            else:
                item["reason"] = f"tested only in {side}"
                out["untested"].append(item)
    universe = {
        c["id"]
        for c in D.load_cases(None).values()
        if (not f["brief"] or c.get("brief") == f["brief"])
        and (not f["case"] or c["id"] == f["case"])
    }
    touched = set(tested["a"]) | set(tested["b"])
    ca, cb = _cfg_out(base["configs"][a]), _cfg_out(base["configs"][b])
    return {
        "a": ca,
        "b": cb,
        "rule": "Rows match only on the same case, the same test definition hash and a known, equal "
        "speech style. A side's status uses comparable strict runs only (complete, 3+ reps, no "
        "configuration flag); runs that disagree make it 'mixed'. Reps of different runs are never "
        "added up.",
        "differences": [
            {"field": k, "a": ca.get(k), "b": cb.get(k)}
            for k in DIFF_FIELDS
            if ca.get(k) != cb.get(k)
        ],
        "unknown_on_both_sides": [
            k for k in DIFF_FIELDS if ca.get(k) is None and cb.get(k) is None
        ],
        "compared_fields": list(DIFF_FIELDS),
        "provenance_warnings": {"a": ca["flags"], "b": cb["flags"]},
        "counts": {k: len(v) for k, v in out.items()},
        **out,
        "untested_by_both": sorted(universe - touched),
        "untested_by_both_source": "case ids in kit/public-test-set.json (brief and case filters "
        "applied) that neither configuration ran under any test definition or style in the date range",
    }


def view(base: dict, q: dict[str, list[str]]) -> dict:
    f = filters(base, q)
    keep = [
        e
        for e in base["entries"]
        if _row_ok(base["rows"][e["row"]], f)
        and (not f["config"] or e["config"] in f["config"])
        and _time_ok(e["end_ts"], f)
    ]
    cells: dict[tuple[str, str], list[dict]] = {}
    for e in keep:
        cells.setdefault((e["row"], e["config"]), []).append(e)
    cfg_ids = sorted(
        {e["config"] for e in keep},
        key=lambda c: (
            base["configs"][c]["deploy_time"] or D.iso(base["configs"][c]["first_run_ts"]),
            c,
        ),
    )
    rows = _row_order([base["rows"][r] for r in {e["row"] for e in keep}])
    all_rows = _row_order([r for r in base["rows"].values() if _row_ok(r, f)])
    scope = [r for r in base["rows"].values() if _row_ok(r, {**f, "style": ""})]
    every = sorted(
        base["configs"].values(),
        key=lambda c: (c["deploy_time"] or D.iso(c["first_run_ts"]), c["id"]),
    )
    ends = [e["end_ts"] for e in base["entries"]]
    return {
        "endpoint": "GET /api/comparison?brief=&case=&style=&config=<id>[,<id>]&from=YYYY-MM-DD&to=YYYY-MM-DD&a=<id>&b=<id>",
        "definitions": DEFINITIONS,
        "limitations": LIMITATIONS,
        "filters": {k: f[k] for k in ("brief", "case", "style", "config", "from", "to", "a", "b")},
        "options": {
            "briefs": sorted({r["brief"] for r in base["rows"].values()}),
            "cases": sorted({r["case"] for r in base["rows"].values()}),
            "styles": sorted({r["style"] or "unknown" for r in base["rows"].values()}),
            "configs": [{"id": c["id"], "label": c["label"]} for c in every],
            "date_min": D.iso(min(ends)) if ends else None,
            "date_max": D.iso(max(ends)) if ends else None,
        },
        "configurations": [_cfg_out(base["configs"][c]) for c in cfg_ids],
        "rows": [
            {
                **r,
                "cells": {c: _cell(cells[(r["id"], c)]) for c in cfg_ids if (r["id"], c) in cells},
            }
            for r in rows
        ],
        "incomplete_runs": _partials(base["partial"], f),
        "comparison": compare(base, f, all_rows, scope) if f["a"] else None,
        "no_ranking": "Columns are ordered by deploy time. No overall ranking: coverage differs "
        "between configurations.",
    }


def _cfg_out(cfg: dict) -> dict:
    return {k: v for k, v in cfg.items() if k != "first_run_ts"}


def _partials(partial: list[dict], f: dict) -> list[dict]:
    """Incomplete runs in the date range; with a brief/case/style filter, only those with a matching case."""
    narrowed = bool(f["brief"] or f["case"] or f["style"])
    out = []
    for p in partial:
        cases = [c for c in p["cases"] if _partial_ok(c, f)]
        if _time_ok(p["ts"], f) and (cases or not narrowed):
            out.append({**p, "cases": cases})
    return out


def _partial_ok(c: dict, f: dict) -> bool:
    return (
        (not f["brief"] or c["brief"] == f["brief"])
        and (not f["case"] or c["id"] == f["case"])
        and (not f["style"] or (c["style"] or "unknown") == f["style"])
    )
