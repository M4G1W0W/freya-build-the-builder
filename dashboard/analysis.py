"""Derived views over data.py records: panels, history, failure intelligence, the snapshot.

Official-style numbers use only complete, full-case-set runs with 3+ reps, scored from all_rows (a case
passes only if every rep passed). Infrastructure-adjusted numbers are computed separately and labelled as
interpretation. Nothing here reads or writes files except through data.py.
"""

from __future__ import annotations

import time

import data as D

PLATFORM = "Platform errors"


def _score(r: dict | None) -> dict | None:
    if not r:
        return None
    return {
        "run": r["id"],
        "strict": f"{r['strict_passed']}/{r['total']}",
        "strict_passed": r["strict_passed"],
        "total": r["total"],
        "rate": round(r["strict_passed"] / r["total"], 3) if r["total"] else None,
        "per_rep_passed": r["per_rep_passed"],
        "commit": r["commit"],
        "commit_source": r["commit_source"],
        "agent_id": r["agent_id"],
        "workflow_id": r["workflow_id"],
        "slot": r["slot"],
        "version": r["version"],
        "style": r["style"],
        "case_file": r["case_file"],
        "reps": r["reps"],
        "build_mode": r["build_mode"],
        "spec": r["spec"],
        "deploy_log": r["deploy_log"],
        "end": r["end"],
        "official_style": r["official_style"],
        "flags": r["flags"],
    }


def _fixture(r: dict) -> bool:
    """A hand-written fixture spec (tests/fixtures): renderer-only, not builder output."""
    return bool(r.get("spec")) and r["spec"].startswith("tests/fixtures")


def panels(runs: list[dict]) -> list[dict]:
    out = []
    for name, _, case_set in D.PANELS:
        all_official = [r for r in runs if r["panel"] == name and r["official_style"]]
        official = [r for r in all_official if not _fixture(r)]  # fixture-spec runs: history only
        other = [r for r in runs if r["panel"] == name and not r["official_style"]]
        latest = official[-1] if official else None
        prev = official[-2] if len(official) > 1 else None
        best = (
            max(official, key=lambda r: (r["strict_passed"] / r["total"], r["end_ts"]))
            if official
            else None
        )
        trend, notes = None, []
        if latest and prev:
            diff = latest["strict_passed"] / latest["total"] - prev["strict_passed"] / prev["total"]
            trend = "improvement" if diff > 0 else "regression" if diff < 0 else "unchanged"
            if latest["case_file"] != prev["case_file"] or latest["style"] != prev["style"]:
                notes.append(
                    "Latest and previous used different case files/styles: not a like-for-like comparison"
                )
        if (
            best
            and latest
            and (best["case_file"] != latest["case_file"] or best["style"] != latest["style"])
        ):
            notes.append(
                f"Best ({best['strict_passed']}/{best['total']}) was measured on {best['case_file']} / {best['style']}, not the latest case set"
            )
        if best and latest and best["build_mode"] != latest["build_mode"]:
            notes.append(
                f"Best came from a {best['build_mode']} agent; latest from {latest['build_mode']}"
            )
        if best and latest and best["slot"] != latest["slot"]:
            notes.append(
                f"Best was a different agent ({best['slot']}, {best['deploy_log']}) than latest ({latest['slot']})"
            )
        if (
            best
            and "human" in best["commit_source"].lower()
            or best
            and "NOT verified" in best["commit_source"]
        ):
            notes.append(f"Best's commit {best['commit']} is only {best['commit_source']}")
        resolvable = bool(
            latest
            and latest["commit"]
            and D.git("rev-parse", "--verify", "--quiet", latest["commit"] + "^{commit}").strip()
        )
        untested = D.code_commits_after(latest["commit"]) if resolvable else None
        if latest and not latest["commit"]:
            notes.append("Latest run has no known tested commit")
        out.append(
            {
                "panel": name,
                "case_set": case_set,
                "latest": _score(latest),
                "previous": _score(prev),
                "best": _score(best),
                "trend": trend,
                "notes": notes,
                "official_runs": len(official),
                "latest_non_official": _score(other[-1]) if other else None,
                "untested_code_commits_since_latest": untested,
                "stale": (
                    bool(untested) if untested is not None else None
                ),  # None = unknown tested commit
                "history": [
                    {
                        "end": r["end"],
                        "rate": round(r["strict_passed"] / r["total"], 3),
                        "strict": f"{r['strict_passed']}/{r['total']}",
                        "commit": r["commit"],
                        "style": r["style"],
                        "run": r["id"],
                        "slot": r["slot"],
                        "build_mode": r["build_mode"],
                        "fixture_spec": _fixture(r),
                    }
                    for r in all_official
                ],
            }
        )
    return out


def failures(runs: list[dict]) -> dict:
    reps = []
    for r in runs:
        for c in r["cases"]:
            for f in c["failures"]:
                reps.append(
                    {
                        "run": r["id"],
                        "panel": r["panel"],
                        "case_set": r["case_set"],
                        "case": c["id"],
                        "rep": f["rep"],
                        "category": f["category"],
                        "tags": f["tags"],
                        "commit": r["commit"],
                        "end": r["end"],
                        "official_style": r["official_style"],
                        "style": c["style"],
                        "summary": (
                            f["ledger"][0]["field"]
                            + ": "
                            + f["ledger"][0]["actual"]
                            + " vs expected "
                            + f["ledger"][0]["expected"]
                        )
                        if f["ledger"]
                        else (
                            f["judge"][0][:220]
                            if f["judge"]
                            else (f["other"][0][:220] if f["other"] else "")
                        ),
                    }
                )
    official = [x for x in reps if x["official_style"]]

    def count(items, key):
        out: dict[str, int] = {}
        for x in items:
            out[key(x)] = out.get(key(x), 0) + 1
        return sorted(out.items(), key=lambda kv: -kv[1])

    introduced, resolved, awaiting, persistent, adjusted = [], [], [], [], []
    for name, _, _ in D.PANELS:
        off = [r for r in runs if r["panel"] == name and r["official_style"] and not _fixture(r)]
        if not off:
            continue
        latest, prev = off[-1], (off[-2] if len(off) > 1 else None)
        lat = {c["id"]: c for c in latest["cases"]}
        if prev:
            pre = {c["id"]: c for c in prev["cases"]}
            for cid, c in lat.items():
                p = pre.get(cid)
                if p and p["strict"] and not c["strict"]:
                    introduced.append(
                        {
                            "panel": name,
                            "case": cid,
                            "run": latest["id"],
                            "commit": latest["commit"],
                            "category": c["category"],
                        }
                    )
                if p and not p["strict"] and c["strict"]:
                    resolved.append(
                        {
                            "panel": name,
                            "case": cid,
                            "run": latest["id"],
                            "commit": latest["commit"],
                        }
                    )
        newer = D.code_commits_after(latest["commit"]) if latest["commit"] else []
        for cid, c in lat.items():
            if c["strict"]:
                continue
            streak = 0
            for r in reversed(off):
                cc = next((x for x in r["cases"] if x["id"] == cid), None)
                if cc is None or cc["strict"]:
                    break
                streak += 1
            persistent.append(
                {
                    "panel": name,
                    "case": cid,
                    "failing_official_runs_in_a_row": streak,
                    "category": c["category"],
                }
            )
            if (
                newer
            ):  # code changed after the failing run; NOT a claim that a fix exists for this case
                awaiting.append(
                    {
                        "panel": name,
                        "case": cid,
                        "last_failed_in": latest["id"],
                        "tested_commit": latest["commit"],
                        "code_commits_since": [n["commit"] for n in newer],
                        "category": c["category"],
                    }
                )
        # interpretation only: treat reps whose primary category is a platform error as missing
        ok, forgiven = 0, []
        for c in latest["cases"]:
            fails = c["failures"]
            real = [f for f in fails if f["category"] != PLATFORM]
            forgiven += [f"{c['id']} rep {f['rep']}" for f in fails if f["category"] == PLATFORM]
            valid = len(c["reps"]) - (len(fails) - len(real))
            ok += 1 if (not real and valid > 0) else 0
        adjusted.append(
            {
                "panel": name,
                "run": latest["id"],
                "official_strict": f"{latest['strict_passed']}/{latest['total']}",
                "platform_adjusted": f"{ok}/{latest['total']}",
                "forgiven_reps": forgiven,
                "label": "INTERPRETATION: only reps with structural platform evidence (no tool call, 0 s turns) are ignored. Not an official score.",
            }
        )
    persistent.sort(key=lambda x: -x["failing_official_runs_in_a_row"])
    return {
        "classifier": "keyword heuristic over ledger diffs and judge text (dashboard/data.py CATEGORIES); human classification is in the Score log",
        "categories_official_runs": count(official, lambda x: x["category"]),
        "categories_all_runs": count(reps, lambda x: x["category"]),
        "most_frequent_cases": _top(count(official, lambda x: f"{x['case_set']}:{x['case']}"), 12),
        "persistent": persistent,
        "introduced_in_latest": introduced,
        "resolved_in_latest": resolved,
        "awaiting_retest": awaiting,
        "infra_adjusted_latest": adjusted,
        "failed_reps": reps,
    }


def _top(items: list, n: int) -> list[dict]:
    """The top n, plus every item tied with the n-th (no silent cut inside a tie)."""
    if len(items) > n:
        items = [kv for kv in items if kv[1] >= items[n - 1][1]]
    return [{"case": k, "failed_reps": v} for k, v in items]


def overview(
    git: dict, runs: list[dict], incomplete: list[dict], procs: list[dict], ws: dict
) -> dict:
    complete = [r for r in runs if r["complete"]]
    latest = complete[-1] if complete else None
    measured = [
        r for r in complete if r["commit_order"] is not None and r["official_style"]
    ]  # 3-rep full sets only
    newest = min(measured, key=lambda r: (r["commit_order"], -r["end_ts"])) if measured else None
    untested = D.code_commits_after(newest["commit"]) if newest else []
    flags = [
        {"run": r["id"], "flag": f}
        for r in runs
        for f in r["flags"]
        if "rep run" not in f and "Subset" not in f
    ]
    now = time.time()
    return {
        "head": git["head"],
        "tree": "clean" if not git["tracked_changes"] and not git["untracked"] else "dirty",
        "tracked_changes": git["tracked_changes"],
        "untracked": git["untracked"],
        "builder_code_dirty": git["code_dirty"],
        "latest_measured_commit": newest["commit"] if newest else None,
        "latest_measured_commit_subject": newest["commit_subject"] if newest else None,
        "latest_measured_commit_source": newest["commit_source"] if newest else None,
        "running": procs,
        "running_note": "Verified from the live process list only (run_cases.py / build.py / chain*.sh). Old logs are never treated as running.",
        "latest_completed": _score(latest),
        "latest_completed_panel": latest["panel"] if latest else None,
        "seconds_since_last_result": int(now - latest["end_ts"]) if latest else None,
        "untested_code_commits": untested,
        "incomplete_runs": _mark_in_progress(incomplete, procs),
        "integrity_flags": flags,
        "working_state": ws,
    }


def _mark_in_progress(incomplete: list[dict], procs: list[dict]) -> list[dict]:
    """A log a live run_cases process is writing is 'in progress', not 'incomplete'."""
    out = []
    for i in incomplete:
        stem = i["file"].rsplit("/", 1)[-1].removesuffix(".log")
        live = any(p["kind"].startswith("simulation") and stem in p["what"] for p in procs)
        out.append({**i, "status": "in progress (live process)"} if live else i)
    return out


def builder(traces: list[dict], runs: list[dict]) -> dict:
    rows = []
    for t in sorted(traces, key=lambda t: t["start_ts"]):
        rows.append(
            {
                "file": t["file"],
                "start": t["start"],
                "inputs": t["inputs"],
                "briefs": t["briefs"],
                "mode": t["mode"],
                "git": t["git"],
                "dirty": t["dirty"],
                "model_calls": len(t["models"]),
                "build_seconds": (t["end"] or {}).get("build_seconds"),
                "ok": (t["end"] or {}).get("ok"),
                "complete": t["complete"],
                "tests": t["tests"],
                "unresolved": t["unresolved"],
                "not_enforced": t["not_enforced"],
                "spec": t["spec"],
                "created": {k: v for k, v in (t["created"] or {}).items() if k != "ts"} or None,
                "submission_path": t["submission_path"],
            }
        )
    by_mode: dict[str, list] = {}
    for r in runs:
        if r["official_style"]:
            by_mode.setdefault(r["build_mode"], []).append(
                {
                    "run": r["id"],
                    "panel": r["panel"],
                    "strict": f"{r['strict_passed']}/{r['total']}",
                    "commit": r["commit"],
                    "end": r["end"],
                }
            )
    synthetic = sorted({b for t in traces for b in t["briefs"] if "kit/briefs" not in b})
    return {
        "traces": rows,
        "official_results_by_build_mode": by_mode,
        "note": "full-builder = brief -> LLM extraction -> checks -> Freya workflow (the submission path). saved-spec = an existing PolicySpec rendered with --spec (skips the LLM, check_spec and the date self-test). Never combine them.",
        "synthetic_briefs_seen": [
            {
                "brief": b,
                "traces": [t["file"] for t in traces if b in t["briefs"]],
                "deployed": any(t["created"] for t in traces if b in t["briefs"]),
                "simulated": any(
                    r["deploy_log"] in [t["file"] for t in traces if b in t["briefs"]] for r in runs
                ),
            }
            for b in synthetic
        ],
    }


def snapshot(state: dict) -> dict:
    ov, pn, fl = state["overview"], state["panels"], state["failures"]
    return {
        "generated_at": D.iso(time.time()),
        "purpose": "Read-only testing status for the Freya Build-the-Builder project. Official-style scores are strict (a case passes only if all 3 reps pass) and computed from all_rows.",
        "git": {
            "head": ov["head"],
            "tree": ov["tree"],
            "tracked_changes": ov["tracked_changes"],
            "untracked": ov["untracked"],
            "builder_code_dirty": ov["builder_code_dirty"],
        },
        "test_status": {
            "running": ov["running"],
            "running_note": ov["running_note"],
            "latest_completed": ov["latest_completed"],
            "seconds_since_last_result": ov["seconds_since_last_result"],
            "latest_measured_commit": ov["latest_measured_commit"],
            "incomplete_runs": len(ov["incomplete_runs"]),
        },
        "latest_verified_results": {p["panel"]: p["latest"] for p in pn},
        "best_verified_results": {p["panel"]: p["best"] for p in pn},
        "trends": {
            p["panel"]: {
                "trend": p["trend"],
                "previous": (p["previous"] or {}).get("strict"),
                "notes": p["notes"],
                "stale": p["stale"],
            }
            for p in pn
        },
        "untested_changes": ov["untested_code_commits"],
        "regressions": [p["panel"] for p in pn if p["trend"] == "regression"]
        + [f"{x['panel']}: {x['case']} newly failing" for x in fl["introduced_in_latest"]],
        "critical_failures": fl["persistent"],
        "awaiting_retest": fl["awaiting_retest"],
        "infra_adjusted_interpretation": fl["infra_adjusted_latest"],
        "failure_categories_official_runs": fl["categories_official_runs"],
        "pending_engineering_decisions": {
            "source": f"{ov['working_state'].get('file')} (snapshot: {ov['working_state'].get('snapshot')}; human-written, may be stale)",
            "open_problems": ov["working_state"].get("open_problems"),
            "user_actions": ov["working_state"].get("user_actions"),
        },
        "integrity_flags": ov["integrity_flags"],
        "provenance": {
            "results": "runs/**/*.json with all_rows (kit/tools/run_cases.py --out)",
            "end_times": "kit/results/log.jsonl (machine-local time, converted to UTC)",
            "tested_commit": "build trace START git= > deploy-log file name > Score log Git ref > result file name (each labelled)",
            "transcripts": "only call dumps already saved under runs/; no network",
            "counts": {
                "result_files": len(state["runs"]),
                "build_traces": len(state["builder"]["traces"]),
                "incomplete_runs": len(ov["incomplete_runs"]),
            },
        },
    }


def snapshot_markdown(s: dict) -> str:
    L = [f"# Testing snapshot ({s['generated_at']})", "", s["purpose"], ""]
    g = s["git"]
    L += [
        f"- **HEAD** `{g['head']}`; tree {g['tree']}; builder code dirty: {g['builder_code_dirty']}",
        f"- **Latest measured commit:** `{s['test_status']['latest_measured_commit']}`",
        f"- **Running now (process-verified):** {', '.join(p['kind'] + ' ' + p['elapsed'] for p in s['test_status']['running']) or 'nothing'}",
    ]
    cs = s.get("claude_session") or {}
    if cs.get("available"):
        L.append(
            f"- **Claude engineering session (local, read-only monitor):** {cs['title']} — {cs['state']}; last write {cs['last_write']}; {cs['recent_errors']} recent tool error(s)"
        )
    lc = s["test_status"]["latest_completed"]
    if lc:
        L.append(
            f"- **Latest completed run:** {lc['run']} — {lc['strict']} strict, {lc['reps']} reps, commit `{lc['commit']}`, ended {lc['end']}"
        )
    L += [
        "",
        "## Official-style results (strict 3/3, from all_rows)",
        "",
        "| Panel | Latest | Previous | Trend | Best | Tested commit (source) | Style | Agent v | Stale |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for panel, latest in s["latest_verified_results"].items():
        best, tr = s["best_verified_results"][panel], s["trends"][panel]
        if not latest:
            L.append(f"| {panel} | Not available | | | | | | | |")
            continue
        L.append(
            f"| {panel} | **{latest['strict']}** | {tr['previous'] or '–'} | {tr['trend'] or '–'} | {best['strict']} ({best['commit']}, {best['slot']}, {best['style']}; commit from {best['commit_source'].split(' (')[0]}) | `{latest['commit']}` ({latest['commit_source'].split(' (')[0]}) | {latest['style']} | {latest['slot']} v{latest['version']} | {'unknown' if tr['stale'] is None else 'yes' if tr['stale'] else 'no'} |"
        )
    L += ["", "Notes:"] + [f"- {p}: {n}" for p, t in s["trends"].items() for n in t["notes"]]
    L += ["", "## Code commits not yet measured (after the latest official-style 3-rep run)", ""]
    L += [f"- `{c['commit']}` {c['subject']}" for c in s["untested_changes"]] or ["- none"]
    L += ["", "## Failing cases in the latest official runs", ""]
    L += [
        f"- {x['panel']}: **{x['case']}** ({x['category']}), failing {x['failing_official_runs_in_a_row']} official run(s) in a row"
        for x in s["critical_failures"]
    ] or ["- none"]
    L += ["", "## Infrastructure-adjusted (INTERPRETATION, not official)", ""]
    L += [
        f"- {x['panel']}: official {x['official_strict']}, platform-adjusted {x['platform_adjusted']} (ignored: {', '.join(x['forgiven_reps']) or 'none'})"
        for x in s["infra_adjusted_interpretation"]
    ]
    L += [
        "",
        "## Pending decisions (from WORKING_STATE, human-written)",
        "",
        s["pending_engineering_decisions"]["source"],
        "",
        s["pending_engineering_decisions"]["open_problems"] or "Not available",
        "",
    ]
    L += (
        ["## Integrity flags", ""]
        + [f"- {f['run']}: {f['flag']}" for f in s["integrity_flags"]]
        + [""]
    )
    return D.redact("\n".join(L))
