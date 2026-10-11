"""Read-only data layer for the testing dashboard.

Every value shown on the dashboard comes from a local file or a read-only git/ps command, and keeps its
provenance. Nothing here writes, deletes or calls the network. Sources:

- result files: any runs/**/*.json with `all_rows` (kit/tools/run_cases.py --out)
- run end times and briefs: kit/results/log.jsonl (local time, written by run_cases.py)
- deployed version and tested commit: build traces runs/**/*.log (START/CREATED/END lines, src/freya_builder/trace.py)
- transcripts: call dumps saved under runs/ (freya.get_call output), formatted by scripts/callview.py
- human interpretation: the Score log table in docs/hackathon_notes.md, and docs/WORKING_STATE.md
"""

from __future__ import annotations

import ast
import calendar
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
KIT_LOG = ROOT / "kit" / "results" / "log.jsonl"
SLOTS_FILE = ROOT / ".freya-agents.json"
CASES_DIR = ROOT / "tests" / "fixtures" / "cases"
PUBLIC_CASES = ROOT / "kit" / "public-test-set.json"
NOTES = ROOT / "docs" / "hackathon_notes.md"
WORKING_STATE = ROOT / "docs" / "WORKING_STATE.md"
CODE_PATHS = ["src", "builder"]  # agent-affecting code (render, prompts, sandbox, cli)

sys.path.insert(0, str(ROOT / "scripts"))
from callview import format_messages  # noqa: E402  (existing pure formatter, no network)

# ---------------------------------------------------------------- redaction

SECRET_ENV = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "OPENAI_API_KEY", "FREYA_WORKSPACE_ID")
# same patterns as scripts/check_secrets.py; the bearer one is split so this file never matches itself
PATTERNS = [
    re.compile(p)
    for p in (
        r"\bfak_\w{8,}",
        r"\bsk-[A-Za-z0-9_-]{16,}",
        "Bear" + r"er \S{8,}",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_\w{20,}",
        r"\bxox[abprs]-[\w-]{10,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
        r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token)\s*[=:]\s*[^\s,;]{6,}",
    )
]


def _secret_values() -> list[str]:
    """Secret values, only so they can be redacted (same names as scripts/check_secrets.py)."""
    values = {os.environ.get(n, "") for n in SECRET_ENV}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(errors="replace").splitlines():
            key, _, value = line.strip().removeprefix("export ").partition("=")
            if key.strip() in SECRET_ENV:
                values.add(value.strip().strip("'\""))
    return sorted((v for v in values if len(v) >= 8), key=len, reverse=True)


_SECRETS = _secret_values()


def redact(text: str) -> str:
    for value in _SECRETS:
        text = text.replace(value, "[REDACTED]")
    for pat in PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def redact_obj(obj: object) -> object:
    """Redact every string inside a JSON-like value. Redact before json.dumps, never after: a pattern
    run over serialised JSON can swallow a closing quote and make the body unparseable."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {redact(k) if isinstance(k, str) else k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj


def dumps(obj: object, **kw) -> str:
    """json.dumps with every string redacted first (and non-JSON values redacted as strings)."""
    return json.dumps(redact_obj(obj), default=lambda o: redact(str(o)), **kw)


# ---------------------------------------------------------------- small helpers

_cache: dict[str, tuple[float, int, object]] = {}


def load_json(path: Path) -> object | None:
    """Parse a JSON file, cached by (mtime, size). None if unreadable."""
    try:
        st = path.stat()
    except OSError:
        return None
    hit = _cache.get(str(path))
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    try:
        value = json.loads(path.read_text(errors="replace"))
    except (OSError, ValueError):
        value = None
    _cache[str(path)] = (st.st_mtime, st.st_size, value)
    return value


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iso(ts: float | None) -> str | None:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None


def parse_utc(text: str) -> float:
    return float(calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")))


def git(*args: str) -> str:
    """Read-only git; --no-optional-locks so `status` never rewrites the index."""
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout if out.returncode == 0 else ""


# ---------------------------------------------------------------- git


def git_state() -> dict:
    head = git("rev-parse", "--short", "HEAD").strip()
    tracked = [ln for ln in git("status", "--porcelain", "--untracked-files=no").splitlines() if ln]
    untracked = [ln[3:] for ln in git("status", "--porcelain").splitlines() if ln.startswith("??")]
    code_dirty = git("status", "--porcelain", "--untracked-files=no", "--", *CODE_PATHS).strip()
    commits = []
    for line in git("log", "--format=%H%x09%h%x09%ct%x09%s", "-n", "500").splitlines():
        full, short, ct, subject = line.split("\t", 3)
        commits.append({"full": full, "short": short, "ts": int(ct), "subject": subject})
    return {
        "head": head,
        "tracked_changes": tracked,
        "untracked": untracked,
        "code_dirty": bool(code_dirty),
        "commits": commits,
    }


def resolve(commits: list[dict], prefix: str | None) -> dict | None:
    if not prefix:
        return None
    for i, c in enumerate(commits):
        if c["full"].startswith(prefix):
            return {**c, "order": i}  # order 0 = HEAD (linear history on main)
    return None


def code_differs(commit: str) -> list[str]:
    """Builder-code files (src/, builder/) that differ between `commit` and HEAD: a tree diff, so it also
    sees a tested commit that is not on main."""
    return [
        f for f in git("diff", "--name-only", commit, "HEAD", "--", *CODE_PATHS).splitlines() if f
    ]


def is_ancestor(commit: str) -> bool:
    full = git("rev-parse", "--verify", "--quiet", commit + "^{commit}").strip()
    return bool(full) and git("merge-base", full, "HEAD").strip() == full


def code_commits_after(commit: str) -> list[dict]:
    """Commits touching src/ or builder/ after `commit` (exclusive) up to HEAD."""
    out = git("log", "--format=%h%x09%ct%x09%s", f"{commit}..HEAD", "--", *CODE_PATHS)
    rows = []
    for line in out.splitlines():
        short, ct, subject = line.split("\t", 2)
        rows.append({"commit": short, "time": iso(int(ct)), "subject": subject})
    return rows


# ---------------------------------------------------------------- build traces

LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (\w+)\s+(.*)$")
TEST = re.compile(r"^(.*?):\s+(PASS|FAIL)\b(.*)$")


def parse_trace(path: Path) -> dict | None:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None
    parsed = [m.groups() for m in (LINE.match(ln) for ln in lines) if m]
    if not parsed or parsed[0][1] != "START":
        return None
    start_ts, _, start_msg = parsed[0]
    t: dict = {
        "file": _shown(path),
        "start": start_ts,
        "start_ts": parse_utc(start_ts),
        "briefs": [],
        "git": None,
        "dirty": None,
        "spec": None,
        "models": [],
        "tests": [],
        "unresolved": 0,
        "not_enforced": 0,
        "warnings": 0,
        "created": None,
        "slot": None,
        "end": None,
        "label": None,
    }
    b = re.search(r"briefs=(\[.*?\])", start_msg)
    if b:
        try:
            t["briefs"] = ast.literal_eval(b.group(1))
        except (ValueError, SyntaxError):
            pass
    g = re.search(r"\bgit=(\S+)", start_msg)
    t["git"] = g.group(1) if g and g.group(1) != "unknown" else None
    d = re.search(r"\bdirty=(\w+)", start_msg)
    t["dirty"] = d.group(1) == "True" if d else None
    lab = re.search(r"-([0-9a-f]{7})\.log$", path.name)
    t["label"] = lab.group(1) if lab else None
    for ts, kind, msg in parsed[1:]:
        if kind == "MODEL":
            m = re.search(r"model=(\S+) purpose=(.*?) took=", msg)
            t["models"].append(m.groups() if m else (msg, ""))
        elif kind == "TEST":
            m = TEST.match(msg)
            if m:
                t["tests"].append(
                    {"name": m.group(1), "result": m.group(2), "detail": m.group(3)[:160]}
                )
        elif kind == "WARN":
            t["warnings"] += 1
            if "UNRESOLVED" in msg:
                t["unresolved"] += 1
            if "NOT ENFORCED" in msg:
                t["not_enforced"] += 1
            s = re.search(r"DEV: using provided spec (.+?); the brief", msg) or re.search(
                r"DEV: using provided spec (\S+?);", msg
            )
            if s:
                t["spec"] = relpath(s.group(1))
        elif kind == "STEP":
            s = re.search(r"saved slot '([^']+)'", msg)
            if s:
                t["slot"] = s.group(1)
            pv = re.search(r"published version (\d+)", msg)
            if pv:
                t["published_version"] = int(pv.group(1))
        elif kind == "CREATED":
            kv = dict(re.findall(r"(\w+)=(\S+)", msg))
            version = kv.get("version")
            t["created"] = {
                "ts": parse_utc(ts),
                "time": ts,
                "workflow_id": kv.get("workflow_id"),
                "agent_id": kv.get("agent_id"),
                "steps": kv.get("steps"),
                "tools": kv.get("tools"),
                "version": int(version) if version and version.isdigit() else None,
            }
        elif kind == "END":
            kv = dict(re.findall(r"(\w+)=(\S+)", msg))
            t["end"] = {
                "time": ts,
                "ok": kv.get("ok") == "True",
                "build_seconds": int(kv["build_seconds"])
                if kv.get("build_seconds", "").isdigit()
                else None,
                "model_calls": kv.get("model_calls"),
            }
    t["briefs"] = [relpath(b) for b in t["briefs"]]
    t["variants"] = [ln.strip()[:160] for ln in lines if re.match(r"exp\w* variant=", ln)]
    if t["spec"]:
        t["mode"] = "saved-spec"
    elif t["models"] and t["created"]:
        t["mode"] = "full-builder"
    elif t["models"]:
        t["mode"] = "full-builder (dry, not deployed)"
    else:
        t["mode"] = "unknown"
    t["complete"] = t["end"] is not None
    t["inputs"] = sorted(
        {"public" if "kit/briefs" in b else "synthetic fixture" for b in t["briefs"]}
    ) or ["unknown"]
    t["multi_product_build"] = any("brief-b" in b for b in t["briefs"]) or len(t["briefs"]) > 1
    t["submission_path"] = t["mode"] == "full-builder" and t["complete"]
    return t


def relpath(p: str) -> str:
    """A path as written by a script, repo-relative when it points inside the repo."""
    p = p.strip().strip("'\"")
    return p[len(str(ROOT)) + 1 :] if p.startswith(str(ROOT) + "/") else p


def all_traces() -> list[dict]:
    out = []
    for path in sorted(RUNS.rglob("*.log")):
        t = parse_trace(path)
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------- results

STYLED = [  # longest prefix first: styledABA before styledA
    ("styledABA", "styled-ab-a.json"),
    ("styledXB", "styled-extra-b.json"),
    ("styledB", "styled-b.json"),
    ("styledA", "styled-a.json"),
]
STYLES = ("talkative", "pieces", "corrects", "asks_back", "in_words")
EXPECTED_TOTAL = {"A": 10, "B": 3, "extra-B": 3, "A+B": 13}
B_IDS = {"PUB-11", "PUB-12", "PUB-13"}
PANELS = [
    ("A agent · Brief A cases", "A-only", "A"),
    ("Multi-product agent · Brief B cases", "multi-product", "B"),
    ("Multi-product agent · extra-B cases", "multi-product", "extra-B"),
    ("Multi-product agent · Brief A cases", "multi-product", "A"),
    ("Multi-product agent · A+B cases (all 13)", "multi-product", "A+B"),
]


def kit_log() -> list[dict]:
    rows = []
    try:
        lines = KIT_LOG.read_text().splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            r = json.loads(line)
            r["end_ts"] = time.mktime(time.strptime(r["at"], "%Y-%m-%d %H:%M:%S"))  # machine-local
            rows.append(r)
        except (ValueError, KeyError):
            continue
    return rows


NO_STYLE = "not recorded (run_cases does not save --style; no style in the file name)"
STYLE_TOKENS = {
    "talkative": "talkative",
    "pieces": "pieces",
    "corrects": "corrects",
    "asks_back": "asks_back",
    "asks": "asks_back",
    "in_words": "in_words",
    "words": "in_words",
}


def case_file_for(name: str) -> tuple[str | None, str]:
    for prefix, file in STYLED:
        if name.startswith(prefix):
            return file, "styled case file (one style per case)"
    if "extraB" in name or "extra-b" in name:
        return "extra-b.json", NO_STYLE
    return None, NO_STYLE


def case_set_for(case_file: str | None, ids: list[str]) -> tuple[str, str]:
    """(case set, how it was decided): the extra-B files by name, otherwise by the case ids."""
    if "extra-b" in (case_file or "").rsplit("/", 1)[-1]:
        return "extra-B", "case file name (extra-b)"
    b = [i for i in ids if i in B_IDS]
    if ids and len(b) == len(ids):
        return "B", "case ids"
    return ("A+B" if b else "A"), "case ids"


def _calls_rows(d: Path) -> dict[str, dict]:
    """The launcher's per-run ledger (calls.tsv): run name -> row; later rows win."""
    try:
        lines = (d / "calls.tsv").read_text(errors="replace").splitlines()
    except OSError:
        return {}
    head, rows = None, {}
    for ln in lines:
        if not ln.strip() or ln.startswith("#"):
            continue
        cells = ln.split("\t")
        if head is None:
            head = cells
        elif len(cells) > 1:
            rows[cells[1]] = dict(zip(head, cells, strict=False))
    return rows


def _ended_before(end_utc: object, written: float | None) -> bool:
    """A record that ended well before the file was last written belongs to an earlier attempt."""
    if not written or not isinstance(end_utc, str) or not end_utc.endswith("Z"):
        return False
    try:
        return parse_utc(end_utc[:19] + "Z") < written - 60
    except ValueError:
        return False


def launch_record(path: Path, written: float | None = None) -> dict | None:
    """What the launcher wrote when it started this run: <name>.meta.json beside the result (case file
    and its sha256, slot, agent, version, build, spec and its sha256), else the run's calls.tsv row.
    `written` (a console log's mtime) drops a record from an earlier attempt of the same name."""
    meta_path = path.with_name(path.stem + ".meta.json")
    meta = load_json(meta_path)
    if (
        isinstance(meta, dict)
        and meta.get("cases")
        and not _ended_before(meta.get("end_utc"), written)
    ):
        return {**meta, "source": _shown(meta_path)}
    row = _calls_rows(path.parent).get(path.stem)
    if row and _ended_before(row.get("end_utc"), written):
        return None
    if row and str(row.get("casefile", "")).endswith(".json"):
        return {
            "cases": row["casefile"],
            "slot": row.get("slot"),
            "exit": row.get("exit"),
            "source": f"{_shown(path.parent / 'calls.tsv')} (row {path.stem})",
        }
    return None


def _shown(path: Path) -> str:
    try:
        return rel(path)
    except ValueError:  # outside the repo (tests)
        return str(path)


def case_ref(p: str) -> str:
    """How a case file is named in run records: a bare name inside tests/fixtures/cases, else a path."""
    p = relpath(p)
    inner = p.removeprefix("tests/fixtures/cases/")
    return inner if inner != p and "/" not in inner else p


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def spec_products(
    spec: Path, launch_sha: str | None, deployed_ts: float | None
) -> tuple[int | None, str]:
    """meta.max_products of the deployed spec, only when its content is shown to be the deployed one."""
    if launch_sha:
        if sha256_file(spec) != launch_sha:
            return None, "spec file differs from the launch record's sha256"
        how = "spec content verified by the launch record's sha256"
    elif deployed_ts and spec.exists() and spec.stat().st_mtime <= deployed_ts:
        how = "spec file unchanged since the deploy (mtime)"
    else:
        return None, "deployed spec content not verifiable"
    data = load_json(spec)
    mp = (data or {}).get("meta", {}).get("max_products") if isinstance(data, dict) else None
    return (mp if isinstance(mp, int) else None), how


def load_cases(file: str | None) -> dict[str, dict]:
    path = PUBLIC_CASES if not file else (ROOT / file if "/" in file else CASES_DIR / file)
    data = load_json(path)
    if isinstance(data, dict):
        data = data.get("cases", [])
    return {c["id"]: c for c in data or [] if isinstance(c, dict) and "id" in c}


def call_index() -> dict[str, Path]:
    """call_id -> saved call dump (freya.get_call output) under runs/; voice calls excluded."""
    index = {}
    for path in RUNS.rglob("*.json"):
        if "voice" in path.parts or path.stat().st_size < 200:
            continue
        data = load_json(path)
        if isinstance(data, dict) and "messages" in data and isinstance(data.get("id"), str):
            index[data["id"]] = path
    return index


# ------------------------------------------------ failure categories (keyword heuristic, labelled)

CATEGORIES = [
    # judge wording alone never makes a platform error (see classify); these are tags for a human to check
    (
        "Possible platform issue (judge wording)",
        r"technical (issue|error|difficult)|system error|service_error|"
        r"failed to reach|platform error|internal error|\b(http|status)\s*50[34]\b",
    ),
    ("Sandbox output (builder-side)", r"sandbox|parseable"),
    ("Simulator errors", r"simulat(or|ed customer) error|persona error"),
    (
        "Multi-product attempt logic",
        r"attempts? (on|for) the|second attempt|persuasion attempts?|"
        r"two attempts|per product|each product",
    ),
    (
        "Identity verification",
        r"not_verified|verif|security question|date of birth|identity|"
        r"wrong answer",
    ),
    (
        "Date calculations",
        r"\bdate\b|weekday|business day|deadline|monday|tuesday|wednesday|thursday|"
        r"friday|week after|next week|holiday",
    ),
    ("Payment amounts", r"amount|minimum payment|floor|past.due"),
    ("Tool arguments", r"\bnotes?\b|queue|reason|callback|transfer"),
    (
        "Conversation loops",
        r"loop|repeat|please go on|cut off|turn limit|max_turns|multiple times|"
        r"twice|again",
    ),
    (
        "Premature termination",
        r"hung up|ended abruptly|terminated|not closed|without close_call|"
        r"close_call",
    ),
    ("Hallucination", r"invent|fabricat|made.up|hallucinat|incorrectly (stated|claimed)|not true"),
    ("Policy interpretation", r"conversation:"),
]
LEDGER = re.compile(
    r"^(outcome|promises|notes|callbacks|transfers|close_call|tools?)\b(.*?), expected (.*)$"
)


def _ledger_category(failed: list[str]) -> str | None:
    """Structured first: what the bank ledger diff says, before any keyword guess."""
    for s in failed:  # an identity outcome explains every later ledger difference
        m = LEDGER.match(str(s))
        if (
            m
            and m.group(1) == "outcome"
            and ("not_verified" in m.group(2)) != ("not_verified" in m.group(3))
        ):
            return "Identity verification"
    for s in failed:
        m = LEDGER.match(str(s))
        if not m:
            continue
        field, actual, expected = m.group(1), m.group(2), m.group(3)
        if field == "promises" and actual.strip(" []"):
            try:
                got, want = ast.literal_eval(actual.strip()), ast.literal_eval(expected.strip())
            except (ValueError, SyntaxError):
                return "Payment amounts"
            if not (isinstance(got, list) and isinstance(want, list)):
                return "Payment amounts"
            if len(got) != len(want):
                return "Promises missing or extra"
            got, want = sorted(got), sorted(want)
            same_amounts = [tuple(x[:2]) for x in got] == [tuple(x[:2]) for x in want]
            return "Date calculations" if same_amounts else "Payment amounts"
        if field in ("notes", "callbacks", "transfers"):
            return "Tool arguments"
    return None


SLOW_TURN_S = 30  # the kit simulator's customer hangs up on long silences


def classify(row: dict) -> tuple[str, list[str]]:
    """Primary category: structural platform evidence, then the ledger diff, then keywords.

    "Platform errors" needs structural evidence (no tool call and 0 s turns). Judge text that mentions
    technical issues only adds a tag; sandbox output failures are builder-side, not platform.
    """
    failed = row.get("failed") or []
    text = " ".join(failed).lower()
    tags = [name for name, pat in CATEGORIES if re.search(pat, text)]
    structured = _ledger_category(failed)
    if structured:
        tags.insert(0, structured)
    if not row.get("tools") and (row.get("slowest_turn_s") or 0) == 0:
        tags.insert(0, "Platform errors")
    elif (
        row.get("ended") == "customer-ended-call"
        and (row.get("slowest_turn_s") or 0) >= SLOW_TURN_S
    ):
        tags.insert(0, "Slow agent turn, customer hung up (latency)")
    if re.search(r"analysis never arrived|no verdict", text):
        if any(not str(s).startswith("conversation:") for s in failed):
            tags.append("No judge verdict (the bank records failed too)")
        else:
            tags.insert(
                0, "Platform errors"
            )  # the judge verdict never arrived, nothing else failed
    tags = list(dict.fromkeys(tags))
    primary = next((t for t in tags if not t.startswith("Possible platform")), None)
    return (primary or (tags[0] if tags else "Unknown")), tags


def failure_detail(row: dict) -> dict:
    ledger, judge, other = [], [], []
    for s in row.get("failed") or []:
        s = redact(str(s))
        m = LEDGER.match(s)
        if m:
            ledger.append(
                {"field": m.group(1), "actual": m.group(2).strip(), "expected": m.group(3).strip()}
            )
        elif s.startswith("conversation:"):
            judge.append(s.removeprefix("conversation:").strip())
        else:
            other.append(s)
    primary, tags = classify(row)
    return {"ledger": ledger, "judge": judge, "other": other, "category": primary, "tags": tags}


# ---------------------------------------------------------------- run records


def build_runs(traces: list[dict], commits: list[dict]) -> tuple[list[dict], list[dict]]:
    slots = load_json(SLOTS_FILE) or {}
    slot_by_agent = {v.get("agent_id"): k for k, v in slots.items() if isinstance(v, dict)}
    deploys = sorted((t for t in traces if t["created"]), key=lambda t: t["created"]["ts"])
    log = kit_log()
    calls = call_index()
    results, incomplete = [], []
    json_paths = {p.with_suffix("") for p in RUNS.rglob("*.json")}

    for path in sorted(RUNS.rglob("*.json")):
        data = load_json(path)
        if not (isinstance(data, dict) and "all_rows" in data):
            continue
        results.append(_run_record(path, data, deploys, log, calls, slot_by_agent, commits))

    sim_ids = {r["simulation_id"] for r in results if r.get("simulation_id")}
    for path in sorted(RUNS.rglob("*.log")):
        if "exports" in path.parts or path.with_suffix("") in json_paths:
            continue  # workflow export logs; console logs of runs that wrote a result
        if parse_trace(path) is not None:
            continue
        text = path.read_text(errors="replace")
        if any(s in text for s in sim_ids):
            continue  # console log of a run whose result JSON exists under another name
        launch = launch_record(path, path.stat().st_mtime)  # a launcher record makes it a run
        if (
            not launch
            and text
            and not re.search(
                r"passed|Traceback|error|run \d+ of|^(PASS|FAIL) \S+|run discarded|run_cases",
                text,
                re.M,
            )
        ):
            continue  # not a run_cases log
        tail = [ln for ln in text.splitlines() if ln.strip()][-1:] or ["(empty file)"]
        exit_code = (launch or {}).get("exit")
        incomplete.append(
            {
                "file": rel(path),
                "status": "incomplete: no result JSON"
                + (f" (launcher exit {exit_code})" if exit_code not in (None, "") else ""),
                "reason": redact(tail[0])[:240] if text else "empty log: killed or never started",
                "time": iso(path.stat().st_mtime),
                "label": (re.search(r"-([0-9a-f]{7})\.log$", path.name) or [None, None])[1],
                "launch": {
                    k: launch.get(k)
                    for k in (
                        "source",
                        "slot",
                        "agent_id",
                        "cases",
                        "cases_sha256",
                        "reps",
                        "build",
                    )
                }
                if launch
                else None,
            }
        )
    results.sort(key=lambda r: r["end_ts"])
    return results, incomplete


def _run_record(path, data, deploys, log, calls, slot_by_agent, commits) -> dict:
    flags: list[str] = []
    agent = data.get("agent_id")
    reps = int(data.get("runs") or 0)
    name = path.stem

    # end time: the kit's own log line for this run, else the file's mtime (flagged)
    match = [
        r
        for r in log
        if r.get("agent_id") == agent
        and r.get("runs") == reps
        and r.get("passed") == data.get("passed")
        and r.get("total") == data.get("total")
        and r.get("seconds") == data.get("seconds")
    ]
    mtime = path.stat().st_mtime
    if match:
        entry = min(match, key=lambda r: abs(r["end_ts"] - mtime))
        end_ts, end_src, brief = entry["end_ts"], "kit/results/log.jsonl", entry.get("brief")
    else:
        end_ts, end_src, brief = mtime, "file mtime (no kit log line)", None
        flags.append("End time from file mtime: no matching kit/results/log.jsonl line")
    start_ts = end_ts - (data.get("seconds") or 0)

    # deployment that served this run: the last CREATED for this agent before the run started.
    # start_ts = end - seconds is a little LATE (run_cases times only the simulation), so no extra slack.
    mine = [d for d in deploys if d["created"]["agent_id"] == agent]
    before = [d for d in mine if d["created"]["ts"] <= start_ts]
    deploy = before[-1] if before else None
    during = [d for d in mine if start_ts < d["created"]["ts"] < end_ts]
    if during:
        flags.append(
            "Agent was redeployed DURING this run: " + ", ".join(d["file"] for d in during)
        )
    if not deploy:
        flags.append(
            "Deployment metadata missing: no build trace published this agent before the run"
        )

    label = (re.search(r"-([0-9a-f]{7})(?:-|$)", name) or [None, None])[1]
    human = score_log_ref(path.name)
    commit, commit_src = None, "unknown"
    if deploy and deploy["git"]:
        commit, commit_src = deploy["git"], "build trace START git= (authoritative)"
        if deploy.get("dirty"):
            flags.append("Build trace says the code was dirty (uncommitted changes) at deploy")
    elif deploy and deploy["label"]:
        commit, commit_src = (
            deploy["label"],
            "deploy-log file name (chosen by the chain script; not verified as HEAD; dirty state not recorded)",
        )
    elif human:
        commit, commit_src = human, "Score log 'Git ref' (human-recorded, not machine-verified)"
        flags.append("Tested commit from the human Score log only: no build trace records it")
    elif label:
        commit, commit_src = label, "result file name only (NOT verified)"
        flags.append(
            "Tested commit taken from the result file name: not verified by a deploy trace"
        )
    else:
        flags.append("Tested commit unknown: no build trace, Score log row or file-name label")
    invalid = [ln for ln in score_log_rows(path.name) if re.search(r"\binvalid\b", ln, re.I)]
    if invalid:
        flags.append(
            "The Score log marks this run invalid (human note; the raw result is still shown): "
            + invalid[0][:200]
        )
    human_all = score_log_refs(path.name)
    if (
        human_all
        and commit
        and not any(h.startswith(commit) or commit.startswith(h) for h in human_all)
    ):
        flags.append(
            f"Score log records {' + '.join(human_all)}; the deploy evidence says {commit}"
        )
    if label and commit and not commit.startswith(label) and not label.startswith(commit):
        flags.append(f"File name says {label} but the deployed code was {commit}")
    cinfo = resolve(commits, commit)
    if cinfo and cinfo["ts"] > start_ts:
        flags.append(
            f"Commit {commit} was made after this run started: it cannot be the tested code"
        )
    if cinfo and deploy and cinfo["ts"] > deploy["start_ts"] and not deploy["git"]:
        flags.append(
            f"The matched deploy trace ({deploy['file']}) started before commit {commit} existed: "
            "deploy metadata for this run is missing"
        )
    if deploy and deploy["created"]["version"] is None and deploy.get("published_version"):
        flags.append(
            f"Agent version {deploy['published_version']} taken from the trace's 'published version' line (CREATED has none)"
        )
    elif deploy and deploy["created"]["version"] is None:
        flags.append(
            "Agent version not recorded by the build trace (first create?): version cross-check not possible"
        )
    if deploy and deploy["spec"]:
        spec = ROOT / deploy["spec"]
        if spec.exists() and spec.stat().st_mtime > deploy["created"]["ts"]:
            flags.append(
                f"Saved spec {deploy['spec']} was rewritten after this deploy: the deployed spec is not on disk"
            )

    # case file, style, case set: the launch record first, the file-name convention only without one
    ids = sorted({r["id"] for rep in data["all_rows"] for r in rep})
    launch = launch_record(path)
    if launch:
        case_file = case_ref(launch["cases"])
        file_src = f"launch record {launch['source']}"
        styled = any(c.get("style") for c in load_cases(case_ref(launch["cases"])).values())
        style = (
            "styled case file (one style per case)"
            if styled
            else "not recorded (the launch record keeps --cases, not --style)"
        )
        style_source = f"case file 'style' field (case file from the {file_src})"
        recorded = launch.get("cases_sha256")
        now_sha = sha256_file(ROOT / relpath(launch["cases"]))
        if recorded and now_sha != recorded:
            flags.append(
                "Case file changed since the launch (launch sha256 differs from the current file): "
                "expected outcomes shown are the current version"
            )
    else:
        case_file, style = case_file_for(name)
        file_src = (
            "file-name convention"
            if case_file
            else "default (no launch record; run_cases records no --cases)"
        )
        style_source = (
            "case file 'style' field" if case_file and case_file.startswith("styled") else "none"
        )
        token = next(
            (v for k, v in STYLE_TOKENS.items() if re.search(rf"(^|[-_]){k}([-_]|$)", name)), None
        )
        if not (case_file and case_file.startswith("styled")) and token:
            style, style_source = token, "file name (run_cases does not record --style)"
    case_set, cs_src = case_set_for(case_file, ids)
    if brief is None and case_set != "extra-B":
        brief = case_set
    expected_total = EXPECTED_TOTAL[case_set]
    subset = len(ids) < expected_total
    cases_def = load_cases(
        case_file if case_file else ("extra-b.json" if case_set == "extra-B" else None)
    )

    # agent kind: the deployed spec's max_products when its content is verified, else name heuristics
    slot = (deploy or {}).get("slot") or (launch or {}).get("slot") or slot_by_agent.get(agent)
    spec_rel = (launch or {}).get("spec") or (deploy or {}).get("spec")
    products, kind_src = (
        spec_products(
            ROOT / relpath(spec_rel),
            (launch or {}).get("spec_sha256"),
            (deploy or {}).get("created", {}).get("ts") if deploy else None,
        )
        if spec_rel
        else (None, "no spec recorded")
    )
    if products is not None:
        kind = "multi-product" if products > 1 else "A-only"
        kind_src = f"spec meta.max_products={products} ({kind_src})"
    elif deploy:
        kind = "multi-product" if deploy["multi_product_build"] else "A-only"
        kind_src = f"brief file names in the build trace (heuristic; {kind_src})"
    elif slot:
        kind = "multi-product" if ("ab" in slot.split("-") or "brief-b" in slot) else "A-only"
        kind_src = f"slot name (heuristic; {kind_src})"
    else:
        kind, kind_src = "unknown", kind_src
    panel = next((p for p, k, cs in PANELS if k == kind and cs == case_set), "Other")
    if deploy and deploy.get("variants"):
        flags.append(
            "In-memory experiment variant applied at build time (in the trace, not in git): "
            + "; ".join(deploy["variants"])
        )
    if launch:
        build_label = str(launch.get("build") or "")
        named = re.findall(r"\b[0-9a-f]{7}\b", build_label)
        if build_label and commit and named and not any(c.startswith(commit[:7]) for c in named):
            flags.append(
                f"Launch record says build '{build_label[:120]}'; the build trace says git={commit}"
                + (" (dirty)" if (deploy or {}).get("dirty") else "")
            )
        if launch.get("agent_id") and launch["agent_id"] != agent:
            flags.append(
                f"Launch record agent {launch['agent_id']} differs from the result's agent"
            )
        lv, dv = (
            str(launch.get("workflow_version") or ""),
            (deploy or {}).get("created", {}).get("version")
            or (deploy or {}).get("published_version"),
        )
        if lv.isdigit() and dv is not None and int(lv) != dv:
            flags.append(f"Launch record version {lv} differs from the deploy trace's version {dv}")
        if str(launch.get("exit", "0")) not in ("0", ""):
            flags.append(f"Launcher recorded exit {launch.get('exit')} for this run")

    # repetition-level strict scoring from all_rows
    per_case: dict[str, dict] = {}
    for i, rep in enumerate(data["all_rows"]):
        for r in rep:
            c = per_case.setdefault(
                r["id"],
                {
                    "id": r["id"],
                    "family": r.get("family"),
                    "reps": [None] * reps,
                    "rows": [None] * reps,
                },
            )
            if i < reps:
                c["reps"][i] = bool(r.get("pass"))
                c["rows"][i] = r
    complete = len(data["all_rows"]) == reps and all(
        None not in c["reps"] for c in per_case.values()
    )
    if not complete:
        flags.append(f"Incomplete: all_rows has {len(data['all_rows'])} of {reps} reps")
    cases = []
    version_seen, version_bad = 0, 0
    for cid in sorted(per_case):
        c = per_case[cid]
        strict = complete and all(c["reps"])
        failures = []
        for i, r in enumerate(c["rows"]):
            if r is None or r.get("pass"):
                continue
            failures.append({"rep": i + 1, "call_id": r.get("call_id"), **failure_detail(r)})
        for r in c["rows"]:
            dump = calls.get((r or {}).get("call_id"))
            deployed_v = (
                (deploy["created"]["version"] or deploy.get("published_version"))
                if deploy
                else None
            )
            if dump and deployed_v is not None:
                v = (load_json(dump) or {}).get("entityVersionNumber")
                version_seen += 1
                version_bad += v != deployed_v
        cdef = cases_def.get(cid, {})
        cases.append(
            {
                "id": cid,
                "family": c["family"],
                "style": cdef.get("style") or style,
                "reps": c["reps"],
                "strict": strict,
                "category": failures[0]["category"] if failures else None,
                "failures": failures,
            }
        )
    strict_passed = sum(c["strict"] for c in cases)
    if complete and strict_passed != data.get("passed"):
        flags.append(
            f"Recomputed strict {strict_passed} differs from the file's passed={data.get('passed')}"
        )
    if version_bad:
        flags.append(
            f"Saved calls show a different agent version in {version_bad} of {version_seen} calls"
        )
    if reps < 3:
        flags.append(f"{reps}-rep run: not an official-style 3/3 measurement")
    if subset:
        flags.append(f"Subset run: {len(ids)} of {expected_total} cases")

    return {
        "id": rel(path),
        "name": name,
        "agent_id": agent,
        "slot": slot,
        "workflow_id": (deploy or {}).get("created", {}).get("workflow_id") if deploy else None,
        "version": (deploy["created"]["version"] or deploy.get("published_version"))
        if deploy
        else None,
        "deploy_log": deploy["file"] if deploy else None,
        "deploy_time": deploy["created"]["time"] if deploy else None,
        "build_mode": deploy["mode"] if deploy else "unknown (no deploy trace)",
        "spec": deploy["spec"] if deploy else None,
        "commit": commit,
        "commit_source": commit_src,
        "commit_subject": cinfo["subject"] if cinfo else None,
        "commit_order": cinfo["order"] if cinfo else None,
        "label": label,
        "end_ts": end_ts,
        "end": iso(end_ts),
        "end_source": end_src,
        "start": iso(start_ts),
        "seconds": data.get("seconds"),
        "simulation_id": data.get("simulation_id"),
        "brief": brief,
        "case_set": case_set,
        "case_set_source": cs_src,
        "case_file": case_file
        or ("kit/public-test-set.json" if case_set != "extra-B" else "extra-b.json"),
        "case_file_source": file_src,
        "launch_record": (launch or {}).get("source"),
        "launch_build": (launch or {}).get("build"),
        "launch_cases_sha256": (launch or {}).get("cases_sha256"),
        "agent_kind_source": kind_src,
        "style": style,
        "style_source": style_source,
        "agent_kind": kind,
        "panel": panel,
        "reps": reps,
        "complete": complete,
        "subset": subset,
        "official_style": complete and reps >= 3 and not subset,
        "strict_passed": strict_passed,
        "total": len(cases),
        "file_passed": data.get("passed"),
        "per_rep_passed": [sum(1 for r in rep if r.get("pass")) for rep in data["all_rows"]],
        "version_check": {"calls_checked": version_seen, "mismatches": version_bad},
        "flags": flags,
        "cases": cases,
    }


# ---------------------------------------------------------------- case detail


def case_detail(runs: list[dict], run_id: str, case_id: str) -> dict | None:
    run = next((r for r in runs if r["id"] == run_id), None)
    if not run:
        return None
    case = next((c for c in run["cases"] if c["id"] == case_id), None)
    if not case:
        return None
    data = load_json(ROOT / run_id) or {}
    calls = call_index()
    reps = []
    for i, rep in enumerate(data.get("all_rows", [])):
        row = next((r for r in rep if r["id"] == case_id), None)
        if not row:
            reps.append({"rep": i + 1, "status": "Not available"})
            continue
        dump = calls.get(row.get("call_id"))
        transcript = None
        if dump:
            call = load_json(dump) or {}
            transcript = redact("\n".join(format_messages(call.get("messages") or [])))
        reps.append(
            {
                "rep": i + 1,
                "pass": row.get("pass"),
                "call_id": row.get("call_id"),
                "tools": row.get("tools"),
                "ended": row.get("ended"),
                "slowest_turn_s": row.get("slowest_turn_s"),
                "detail": failure_detail(row) if not row.get("pass") else None,
                "transcript": transcript,
                "transcript_source": rel(dump) if dump else None,
            }
        )
    cdef = load_cases(None if run["case_file"].startswith("kit/") else run["case_file"]).get(
        case_id, {}
    )
    history = [
        {
            "run": r["id"],
            "end": r["end"],
            "commit": r["commit"],
            "reps": c["reps"],
            "strict": c["strict"],
            "official_style": r["official_style"],
            "panel": r["panel"],
        }
        for r in runs
        for c in r["cases"]
        if c["id"] == case_id and r["case_set"] == run["case_set"]
    ]
    fails = [h for h in history if not h["strict"]]
    return {
        "run": {
            k: run[k]
            for k in (
                "id",
                "commit",
                "commit_source",
                "version",
                "slot",
                "panel",
                "style",
                "case_file",
            )
        },
        "case": {k: case[k] for k in ("id", "family", "style", "reps", "strict", "category")},
        "expected": cdef.get("expected"),
        "expected_source": f"{run['case_file']} (current version of the case file; chosen by "
        f"{run.get('case_file_source', 'file-name convention')})",
        "script_and_checks_source": "current version of the case file; the Config Comparison tab uses "
        "the version committed when the run started",
        "script": cdef.get("script"),
        "checks": cdef.get("checks"),
        "reps": reps,
        "recurring": {
            "failed_runs": len(fails),
            "runs_with_case": len(history),
            "history": history,
        },
        "human_notes": score_log_rows(run["id"]),
        "artifacts": [run["id"], run["id"].removesuffix(".json") + ".log", run.get("deploy_log")],
    }


# ---------------------------------------------------------------- docs (human interpretation)


def score_log_refs(result_name: str) -> list[str]:
    """Every commit hash in the 'Git ref' cell of the Score log rows that cite this result file."""
    refs: list[str] = []
    for line in score_log_rows(result_name):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) > 1:
            refs += re.findall(r"\b[0-9a-f]{7}\b", cells[1])
    return list(dict.fromkeys(refs))


def score_log_ref(result_name: str) -> str | None:
    refs = score_log_refs(result_name)
    return refs[0] if refs else None


def score_log_rows(run_file: str) -> list[str]:
    try:
        text = NOTES.read_text(errors="replace")
    except OSError:
        return []
    base = Path(run_file).name
    return [redact(ln) for ln in text.splitlines() if ln.startswith("|") and base in ln]


def working_state() -> dict:
    try:
        text = WORKING_STATE.read_text(errors="replace")
    except OSError:
        return {"available": False}
    snap = re.search(r"\*\*Snapshot:\*\*\s*(.*?)(?:\.|$)", text, re.M)

    def section(title: str) -> str:
        m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        return m.group(1).strip() if m else ""

    running = section("Running right now")
    open_problems = re.search(
        r"\*\*Open problems, in order:\*\*\n(.*?)(?=\n\n## |\n## |\Z)", running, re.S
    )
    user = section("USER (read this first)")
    return {
        "available": True,
        "file": rel(WORKING_STATE),
        "snapshot": snap.group(1).strip() if snap else None,
        "mtime": iso(WORKING_STATE.stat().st_mtime),
        "running_section": redact(running.split("**Results so far")[0].strip())[:1500],
        "open_problems": redact(open_problems.group(1).strip()) if open_problems else "",
        "user_actions": [
            redact(b.strip("- ").strip())
            for b in user.split("\n- ")
            if "should" in b or "decide" in b.lower()
        ],
    }


# ---------------------------------------------------------------- processes


SIM_OUT = re.compile(r"--out\s+(\S*runs/\S+\.json)")  # any script writing a result under runs/
EXECUTES = re.compile(
    r"(?i)python[0-9.]*(\s+-\S+)*\s+\S*(run_cases\w*\.py|builder/build\.py|smoke\w*\.py)\b"
    r"|(?i:python)[0-9.]*(\s+-\S+)*\s+\S+\.py\b.*\s--out\s+\S*runs/\S+\.json"
    r"|(^|/)(ba|z)?sh\s+\S*(chain\d*|qrun\w*|scratchpad/\S+)\.sh\b"
)


def running_tests() -> list[dict]:
    """Verified only by a live process: run_cases.py, builder/build.py or a chain script."""
    try:
        out = subprocess.run(
            ["ps", "-Ao", "pid,etime,command"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    found = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid, etime, cmd = parts
        if re.match(r"\S*(ba|z)?sh\s+-l?c\b", cmd) or not EXECUTES.search(cmd):
            continue  # wrapper shells, editors, viewers and linters that merely name the file
        if "run_cases" in cmd or re.search(r"smoke\w*\.py", cmd) or SIM_OUT.search(cmd):
            out_file = re.search(r"--out\s+(\S+)", cmd)
            agent = re.search(r"\s([0-9a-f]{8})[0-9a-f-]*(\s|$)", cmd)
            script = re.search(r"(\w+)\.py\b", cmd)
            kind = f"simulation ({script.group(1) if script else 'script'}.py)"
            what = f"agent {agent.group(1) if agent else '?'} -> {Path(out_file.group(1)).name if out_file else 'no --out'}"
            if out_file:
                what += " · " + _progress(ROOT / relpath(out_file.group(1)))
        elif "build.py" in cmd:
            slot = re.search(r"--slot\s+(\S+)", cmd)
            kind, what = "build", f"slot {slot.group(1) if slot else '(default)'}"
        else:
            script = re.search(r"(\S+\.sh)\b", cmd)
            kind, what = "chain/queue script", Path(script.group(1)).name if script else "script"
        if any(f["kind"] == kind and f["what"] == redact(what) for f in found):
            continue  # a launcher wrapper (uv run, caffeinate) and its python child
        found.append({"pid": pid, "elapsed": etime, "kind": kind, "what": redact(what)})
    return found


def _progress(out: Path) -> str:
    """Reps finished so far, from the run's console log next to its --out file (read-only)."""
    try:
        text = out.with_suffix(".log").read_text(errors="replace")
    except OSError:
        return "no console log yet"
    done = re.findall(r"^-- run (\d+) of (\d+):", text, re.M)
    return f"rep {done[-1][0]} of {done[-1][1]} finished" if done else "no rep finished yet"
