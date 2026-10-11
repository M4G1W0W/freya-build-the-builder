"""Final case & documents: the case folder as it arrives, final builds and tests, submission readiness.

Read-only over the case folder: files are opened for reading only, never written or moved. The only
file this module writes is its own version ledger, reports/final_case_ledger.json (gitignored), so a
document's first-seen time and its versions survive dashboard restarts. Nothing from the case is in
this code: file names, purposes and versions are read at run time. Purposes come from the pack's own
README when it names the file, else the file's title, else a guess from the file name against the
document kinds the official page lists. Nothing is fetched and nothing is executed except read-only git.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import data as D

DEFAULT_DIRS = [Path.home() / "Desktop" / "Freya Final case"]
LEDGER = D.ROOT / "reports" / "final_case_ledger.json"
REVIEW_FILE = D.ROOT / "reports" / "final_case_review.json"  # optional, team-written
CONVERSATIONS = D.ROOT / "reports" / "conversations_index.md"
OPENS_UTC = "2026-10-11T17:00:00Z"  # official page: the final case opens Sun 17:00 UTC
DEADLINE_UTC = "2026-10-11T20:00:00Z"  # official page: send submission.json before 20:00 UTC
TARGET_UTC = "2026-10-11T19:00:00Z"  # RUNBOOK step 8: aim for 19:00
NEW_WINDOW_S = 20 * 60
SUBMIT_WORKFLOW = "submission/final.workflow.json"
SUBMIT_TRACE = "traces/final.log"
SKIP = re.compile(r"^(\.|~\$|__MACOSX$|Thumbs\.db$|desktop\.ini$)", re.I)

# document kinds the official page lists for the zip (Submit tab), with generic name hints
EXPECTED = [
    ("brief", "BRIEF.md: read first (named on the page)", ("brief",)),
    ("readme", "README.md: says what each document is (named on the page)", ("readme",)),
    ("analysis", "analysis", ("analysis", "analiz")),
    ("flow drawing", "flow drawing", ("flow", "akis", "akış", "diagram", "diyagram", "flowchart")),
    ("announcements", "announcements", ("announcement", "duyuru", "memo", "notice", "genelge")),
    ("service contract", "service contract", ("contract", "sozlesme", "sözleşme", "openapi")),
    ("test customers", "test customers", ("customer", "musteri", "müşteri")),
    ("questions and answers", "questions and answers", ("faq", "qa", "sss", "question", "soru")),
    (
        "example conversations",
        "6 example conversations",
        ("conversation", "gorusme", "görüşme", "konusma", "konuşma", "dialog"),
    ),
]
EXPECTED_CONVERSATIONS = 6
NAME_VERSION = re.compile(
    r"(?i)(?:^|[\s_\-.(])(v|ver|version|rev|revision|sürüm|surum|versiyon)[\s_\-.]?(\d+(?:\.\d+)*)"
)
TEXT_VERSION = re.compile(
    r"(?i)\b(version|versiyon|sürüm|surum|revizyon|revision|rev)\b\s*[:.]?\s*v?(\d+(?:\.\d+)*)"
)
DOC_NAME = re.compile(
    r"[\w\-.()]+\.(?:md|docx?|pdf|xlsx?|csv|json|ya?ml|txt|pptx?|png|jpe?g|svg)\b", re.I
)
ROLES = [  # areas each engineer owns; the evidence line is looked up in the handoffs at run time
    (
        "Simulation Developer",
        "final builds, mock deploys, tests on our mock, submission files",
        r"Simulation Developer\)? owns|\(simulation chat\)",
    ),
    (
        "Methodology Developer",
        "builder fixes (generic only after 17:00 UTC)",
        r"Methodology (Developer )?(tagged|fixes|prepared)|Methodology Developer \(engine",
    ),
    ("Dashboard Creator", "this dashboard (read-only)", r"Dashboard Creator"),
    ("Submission readiness reviewer", "submission readiness review", r"Submission readiness"),
    ("Service Check", "platform health checks (read-only)", r"Service Check"),
    (
        "the user",
        "decisions, Cloudflare and GitHub accounts, organiser invite, the submission e-mail",
        r"\bUser D\d+|\buser go\b",
    ),
]

_hash_cache: dict[str, tuple[tuple, str]] = {}
_text_cache: dict[str, tuple[float, str]] = {}


# ---------------------------------------------------------------- folder and ledger


def _rel(path: Path) -> str:
    return D.rel(path) if path.is_relative_to(D.ROOT) else str(path)


def case_dirs() -> list[Path]:
    env = os.environ.get("FREYA_FINAL_CASE_DIR")
    return [Path(p).expanduser() for p in env.split(os.pathsep) if p] if env else DEFAULT_DIRS


def scan(folder: Path) -> list[dict]:
    """Every file under the folder (recursive; hidden, lock and OS files skipped), read-only."""
    out = []
    if not folder.is_dir():
        return out
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if not p.is_file() or any(SKIP.match(part) for part in rel.parts):
            continue
        st = p.stat()
        key = str(p)
        cached = _hash_cache.get(key)
        stamp = (st.st_size, st.st_mtime_ns, st.st_ino, st.st_ctime_ns)
        if cached and cached[0] == stamp:
            digest = cached[1]
        else:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            _hash_cache[key] = (stamp, digest)
        out.append(
            {
                "rel": str(rel),
                "path": p,
                "sha256": digest,
                "size": st.st_size,
                "mtime": st.st_mtime,
                "created": getattr(st, "st_birthtime", None),
                "landed": st.st_ctime,  # inode change: when the file was placed in this folder
            }
        )
    return out


def load_ledger(path: Path | None = None) -> dict:
    """A private copy of the ledger (never data.load_json's shared cache object)."""
    try:
        data = json.loads((path or LEDGER).read_text())
    except (OSError, ValueError):
        data = None
    return data if isinstance(data, dict) and "folders" in data else {"folders": {}}


def update_ledger(ledger: dict, folder: Path, files: list[dict], now: float) -> bool:
    """Record new files, new content versions and removals. Returns True when the ledger changed."""
    f = ledger["folders"].setdefault(str(folder), {"first_watched": now, "files": {}})
    changed = False
    present = set()
    for x in files:
        present.add(x["rel"])
        e = f["files"].get(x["rel"])
        if e is None:
            f["files"][x["rel"]] = {
                "first_seen": now,
                "seen_at_ledger_start": now - f["first_watched"] < 30,
                "versions": [{"sha256": x["sha256"], "size": x["size"], "first_seen": now}],
            }
            changed = True
        elif e["versions"][-1]["sha256"] != x["sha256"]:
            e["versions"].append({"sha256": x["sha256"], "size": x["size"], "first_seen": now})
            e.pop("removed_at", None)
            changed = True
        elif e.get("removed_at"):
            e.pop("removed_at")
            changed = True
    for rel, e in f["files"].items():
        if rel not in present and not e.get("removed_at"):
            e["removed_at"] = now
            changed = True
    return changed


def save_ledger(ledger: dict, path: Path | None = None) -> None:
    path = path or LEDGER
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=1))
    tmp.replace(path)


def snapshot_at(folder_entry: dict, ts: float) -> dict:
    """Which document versions the ledger shows in the folder at time ts."""
    files, approx = [], ts < folder_entry["first_watched"]
    for rel, e in sorted(folder_entry["files"].items()):
        vs = [v for v in e["versions"] if v["first_seen"] <= ts] or (
            e["versions"][:1] if approx and e.get("seen_at_ledger_start") else []
        )
        if not vs or (e.get("removed_at") and e["removed_at"] <= ts):
            continue
        files.append({"rel": rel, "version": len(vs), "sha256": vs[-1]["sha256"][:12]})
    sig = hashlib.sha256("\n".join(f"{x['rel']}:{x['sha256']}" for x in files).encode())
    return {
        "id": sig.hexdigest()[:10] if files else None,
        "files": files,
        "basis": "approximate: this run predates the ledger; earliest known folder state"
        if approx
        else "reconstructed from the dashboard's document ledger at that time",
    }


# ---------------------------------------------------------------- per-file metadata


def _xml(z: zipfile.ZipFile, name: str) -> ElementTree.Element | None:
    try:
        return ElementTree.fromstring(z.read(name))
    except (KeyError, ElementTree.ParseError):
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def office_meta(path: Path) -> dict:
    out: dict = {}
    try:
        with zipfile.ZipFile(path) as z:
            core = _xml(z, "docProps/core.xml")
            for el in core.iter() if core is not None else []:
                if _local(el.tag) in ("title", "revision", "modified", "created") and el.text:
                    out[_local(el.tag)] = el.text.strip()[:120]
            book = _xml(z, "xl/workbook.xml")
            if book is not None:
                out["sheets"] = [
                    s.get("name") for s in book.iter() if _local(s.tag) == "sheet" and s.get("name")
                ][:20]
    except (zipfile.BadZipFile, OSError) as exc:
        out["error"] = f"{type(exc).__name__}"
    return out


def _pdf_value(raw: bytes, key: bytes) -> str | None:
    m = re.search(rb"/" + key + rb"\s*\((.{0,200}?)(?<!\\)\)", raw, re.S)
    if not m:
        return None
    v = m.group(1)
    if v.startswith(b"\xfe\xff"):
        return v[2:].decode("utf-16-be", "replace")[:120]
    return v.decode("latin-1", "replace")[:120]


def pdf_meta(path: Path) -> dict:
    raw = path.read_bytes()
    head = re.match(rb"%PDF-(\d\.\d)", raw[:16])
    out = {
        "pdf_version": head.group(1).decode() if head else None,
        "pages": len(re.findall(rb"/Type\s*/Page\b", raw)) or None,
    }
    for key, name in ((b"Title", "title"), (b"ModDate", "modified"), (b"CreationDate", "created")):
        v = _pdf_value(raw, key)
        if v:
            out[name] = v
    return out


def read_text(path: Path, limit: int = 200_000) -> str:
    data = path.read_bytes()[:limit]
    for enc in ("utf-8-sig", "cp1254"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def file_meta(path: Path) -> dict:
    suffix = path.suffix.lower()
    try:
        if suffix in (".docx", ".xlsx", ".pptx"):
            return office_meta(path)
        if suffix == ".pdf":
            return pdf_meta(path)
        if suffix in (".md", ".txt", ".csv", ".json", ".yaml", ".yml"):
            text = read_text(path)
            head = re.search(r"^\s*#{1,3}\s+(.+)$", text, re.M) if suffix == ".md" else None
            ver = TEXT_VERSION.search(text[:3000])
            return {
                "title": head.group(1).strip()[:120] if head else None,
                "text_version": f"{ver.group(1)} {ver.group(2)}" if ver else None,
                "lines": text.count("\n") + 1,
            }
    except OSError as exc:
        return {"error": type(exc).__name__}
    return {}


def name_version(rel: str) -> str | None:
    m = NAME_VERSION.search(Path(rel).stem)
    return f"{m.group(1)} {m.group(2)}" if m else None


DATE_IN_NAME = re.compile(r"(?:19|20)\d\d[-_.]?\d\d[-_.]?\d\d")


def stem_key(rel: str) -> str:
    """A file's name without versions, dates or copy numbers: two files with one key are versions."""
    s = DATE_IN_NAME.sub("", NAME_VERSION.sub("", Path(rel).stem))
    return re.sub(r"[\W_]+", " ", re.sub(r"\(\d+\)$", "", s)).strip().lower()


PHRASES = [  # the official page's category names, matched in the pack README's line for a file
    ("test customers", ("test customer",)),
    ("service contract", ("service contract",)),
    ("example conversations", ("example conversation",)),
    ("flow drawing", ("flow drawing",)),
    ("questions and answers", ("questions and answers",)),
    ("announcements", ("announcement",)),
    ("analysis", ("analysis",)),
]


def guess_kind(rel: str, title: str | None, readme: list[str] | None = None) -> str | None:
    said = " ".join(h for h in readme or [] if not h.startswith("(folder ")).lower()
    for kind, phrases in PHRASES:
        if any(ph in said for ph in phrases):
            return kind
    tokens = [t for t in re.split(r"[\W_]+", f"{Path(rel).stem} {title or ''}".lower()) if t]
    for kind, _, hints in EXPECTED:
        if any(t == h or (len(h) >= 4 and t.startswith(h)) for t in tokens for h in hints):
            return kind
    return None


def readme_purposes(files: list[dict]) -> tuple[str | None, dict[str, list[str]], list[str]]:
    """The pack's README: lines that name each file, and document names it lists that are absent."""
    readme = next((x for x in files if re.match(r"(?i)readme(\.\w+)?$", Path(x["rel"]).name)), None)
    if not readme:
        return None, {}, []
    text = D.redact(read_text(readme["path"]))
    lines = text.splitlines()
    out: dict[str, list[str]] = {}
    for x in files:
        name, stem = Path(x["rel"]).name, Path(x["rel"]).stem
        hits = [
            ln.strip()[:240]
            for ln in lines
            if name.lower() in ln.lower() or (len(stem) >= 5 and stem.lower() in ln.lower())
        ]
        if not hits:  # the README may describe the file's folder instead
            for parent in Path(x["rel"]).parents:
                d = str(parent)
                if d == ".":
                    break
                hits = [ln.strip()[:240] for ln in lines if f"{d.lower()}/" in ln.lower()]
                if hits:
                    hits = [f"(folder {d}/) {h}" for h in hits]
                    break
        if hits and x is not readme:
            out[x["rel"]] = hits[:3]
    names = {Path(x["rel"]).name.lower() for x in files}
    listed = sorted({m.group(0) for m in DOC_NAME.finditer(text)})
    absent = [n for n in listed if n.lower() not in names]
    return readme["rel"], out, absent


# ---------------------------------------------------------------- handoff evidence


def _cached_text(path: Path) -> str:
    try:
        mt = path.stat().st_mtime
    except OSError:
        return ""
    c = _text_cache.get(str(path))
    if c and c[0] == mt:
        return c[1]
    text = path.read_text(errors="replace")
    _text_cache[str(path)] = (mt, text)
    return text


def chats() -> list[dict]:
    """The monitored Claude chats (title, state, last write, conversation file) from the index."""
    rows = []
    for ln in _cached_text(CONVERSATIONS).splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[-1].startswith("reports/"):
            rows.append(
                {
                    "title": cells[0],
                    "role": cells[1],
                    "last_write": cells[5],
                    "state": cells[6],
                    "file": cells[7],
                }
            )
    return rows


def handoff_sources() -> list[tuple[str, Path]]:
    """Review evidence: the monitored chats' exports under reports/ (gitignored)."""
    return [(f"chat '{c['title']}'", D.ROOT / c["file"]) for c in chats()]


def committed_case_mentions(names: list[str]) -> dict[str, list[str]]:
    """Tracked files (outside traces/ and submission/) that name a case file: case content in the
    repo. Read-only git grep over the working tree of tracked files."""
    names = [n for n in names if n]
    if not names:
        return {}
    args = ["grep", "-n", "-I", "-F", "-i"]
    for n in names:
        args += ["-e", n]
    out = D.git(*args, "--", ".", ":!traces", ":!submission")
    hits: dict[str, list[str]] = {}
    for ln in out.splitlines():
        path, _, rest = ln.partition(":")
        line_no = rest.partition(":")[0]
        for n in names:
            if n.lower() in ln.lower():
                hits.setdefault(n, []).append(f"{path}:{line_no}")
    return hits


STAMP = re.compile(r"^### (YOU|CLAUDE) · (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)")
_blame_cache: dict[str, tuple[tuple, list[float | None]]] = {}


def line_times(path: Path) -> list[float | None]:
    """When each line of a repo doc was written: its commit time (read-only git blame); lines not
    committed yet get the file's modification time. Files outside git: the modification time."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    key = (mtime, D.git("rev-parse", "HEAD").strip())
    c = _blame_cache.get(str(path))
    if c and c[0] == key:
        return c[1]
    out: list[float | None] = []
    porcelain = (
        D.git("blame", "--line-porcelain", "--", D.rel(path)) if path.is_relative_to(D.ROOT) else ""
    )
    author_time, uncommitted = None, False
    for ln in porcelain.splitlines():
        if ln.startswith("author-time "):
            author_time = float(ln.split()[1])
        elif ln.startswith("author "):
            uncommitted = ln == "author Not Committed Yet"
        elif ln.startswith("\t"):
            out.append(mtime if uncommitted else author_time)
    n = path.read_text(errors="replace").count("\n") + 1
    if len(out) < n:
        out += [mtime] * (n - len(out))
    _blame_cache[str(path)] = (key, out)
    return out


def _name_pattern(names: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True) if n)
    return re.compile(rf"(?<![\w.\-/])(?:{alts})(?![\w\-])", re.I)


def mentions(needles: list[str], since: float) -> list[dict]:
    """Chat lines that name a document (whole name or relative path), written after `since`."""
    found = []
    pat = _name_pattern(needles)
    for label, path in handoff_sources():
        text = _cached_text(path)
        if not pat.search(text):
            continue
        stamp, who = None, None
        for i, ln in enumerate(text.splitlines(), 1):
            m = STAMP.match(ln)
            if m:
                who, stamp = m.group(1), D.parse_utc(m.group(2) + "Z")
                continue
            if stamp is None or stamp < since or not pat.search(ln):
                continue
            found.append(
                {
                    "source": label,
                    "line": i,
                    "speaker": who,
                    "time": D.iso(stamp),
                    "time_basis": "message time",
                    "text": D.redact(ln.strip())[:220],
                }
            )
    found.sort(key=lambda x: x["time"] or "")
    return found[-12:]


def review_records() -> dict:
    """The optional team review file, normalised: one bad entry never breaks the view."""
    data = D.load_json(REVIEW_FILE)
    out = {}
    for k, r in data.items() if isinstance(data, dict) else []:
        if not isinstance(r, dict):
            r = {"status": str(r)} if isinstance(r, str) else {}
        c = r.get("contradictions")
        out[str(k)] = {
            "status": str(r["status"]) if r.get("status") else None,
            "by": str(r.get("by") or "") or None,
            "at": str(r.get("at") or "") or None,
            "notes": str(r.get("notes") or ""),
            "sha256": str(r.get("sha256") or ""),
            "kind": str(r.get("kind") or "") or None,
            "purpose": str(r.get("purpose") or "") or None,
            "contradictions": [str(x) for x in c] if isinstance(c, list) else [],
        }
    return out


def documents(now: float, ledger: dict, write: bool = True) -> dict:
    folders = []
    changed = False
    reviews = review_records()
    page = _cached_text(D.ROOT / "docs/reference/hackathon_page_live_2026-10-11.md")
    for folder in case_dirs():
        files = scan(folder)
        changed |= update_ledger(ledger, folder, files, now)
        entry = ledger["folders"][str(folder)]
        readme, purposes, absent = readme_purposes(files)
        own = {Path(t).name for t in D.git("ls-files").splitlines()}  # names the repo itself uses
        public = {n for n in {Path(x["rel"]).name for x in files} if n in page or n in own}
        leaks = committed_case_mentions(
            [Path(x["rel"]).name for x in files if Path(x["rel"]).name not in public]
        )
        by_hash: dict[str, list[str]] = {}
        for x in files:
            by_hash.setdefault(x["sha256"], []).append(x["rel"])
        stems: dict[str, list[str]] = {}
        for x in files:
            key = (str(Path(x["rel"]).parent), stem_key(x["rel"]))
            stems.setdefault(key, []).append(x["rel"])
        docs = []
        for x in files:
            e = entry["files"][x["rel"]]
            meta = file_meta(x["path"])
            kind = guess_kind(x["rel"], meta.get("title"), purposes.get(x["rel"]))
            versions = e["versions"]
            first = e["first_seen"]
            # observed arrival; files already present when the ledger started: the case opening
            # (file dates can be the sender's, and change times move on metadata edits)
            opens = D.parse_utc(OPENS_UTC)
            since = opens if e["seen_at_ledger_start"] else max(opens, first - 15)
            rec = reviews.get(x["rel"]) or reviews.get(Path(x["rel"]).name) or {}
            kind = rec.get("kind") or kind
            ment = mentions([x["rel"], Path(x["rel"]).name], since)
            leaked = leaks.get(Path(x["rel"]).name, [])
            flags = []
            if now - versions[-1]["first_seen"] < NEW_WINDOW_S and not e["seen_at_ledger_start"]:
                flags.append(("new", "NEW: first seen " + D.iso(versions[-1]["first_seen"])))
            if len(versions) > 1:
                flags.append(
                    (
                        "amended",
                        f"AMENDED: content changed {len(versions) - 1} time(s), latest "
                        f"{D.iso(versions[-1]['first_seen'])}",
                    )
                )
            key = (str(Path(x["rel"]).parent), stem_key(x["rel"]))
            sib = [r for r in stems.get(key, []) if r != x["rel"]]
            same_kind = [r for r in sib if Path(r).suffix.lower() == Path(x["rel"]).suffix.lower()]
            other_fmt = [r for r in sib if r not in same_kind]
            if same_kind:
                flags.append(
                    (
                        "contradiction",
                        f"other version(s) present: {', '.join(same_kind)}: which is current?",
                    )
                )
            if other_fmt:
                flags.append(
                    (
                        "contradiction",
                        f"same document in another format: {', '.join(other_fmt)}: confirm they agree",
                    )
                )
            dup = [r for r in by_hash[x["sha256"]] if r != x["rel"]]
            if dup:
                flags.append(("contradiction", f"identical content to {', '.join(dup)}"))
            if kind == "announcements":
                flags.append(("amended", "announcements may change rules in other documents"))
            for c in rec.get("contradictions") or []:
                flags.append(("contradiction", f"team note: {c}"))
            if leaked:
                flags.append(("leak", f"named in tracked repo files: {', '.join(leaked[:4])}"))
            rec_sha = rec.get("sha256") or ""
            if rec.get("status") and rec_sha and x["sha256"].startswith(rec_sha):
                status, basis = f"reviewed: {rec['status']}", f"team record ({_rel(REVIEW_FILE)})"
            elif rec.get("status") and rec_sha:
                status = "not reviewed (STALE: the file changed after the team's review)"
                basis = f"team record ({_rel(REVIEW_FILE)}) for an older version"
                flags.append(("contradiction", "reviewed version differs from the current file"))
            elif rec.get("status"):
                status = f"not reviewed (team record '{rec['status']}' has no sha256)"
                basis = f"team record ({_rel(REVIEW_FILE)}) without the file's sha256"
            else:
                status = "not reviewed" + (
                    f" (mentioned in {len(ment)} chat line(s))" if ment else ""
                )
                basis = "only a team record with the file's sha256 counts as a review"
            docs.append(
                {
                    "rel": x["rel"],
                    "kind_ext": Path(x["rel"]).suffix.lower().lstrip(".") or "?",
                    "size": x["size"],
                    "sha256": x["sha256"][:12],
                    "first_seen": D.iso(first),
                    "first_seen_note": "already in the folder when the ledger started"
                    if e["seen_at_ledger_start"]
                    else "arrival observed by the dashboard (within one 12 s refresh)",
                    "landed": D.iso(x["landed"]),
                    "landed_note": "filesystem change time: when it was placed here, or a later metadata edit",
                    "file_created": D.iso(x["created"]),
                    "file_modified": D.iso(x["mtime"]),
                    "version": {
                        "ledger": len(versions),
                        "ledger_note": "content versions seen by the dashboard",
                        "name": name_version(x["rel"]),
                        "embedded": {
                            k: meta.get(k)
                            for k in ("revision", "text_version", "pdf_version", "modified")
                            if meta.get(k)
                        },
                    },
                    "purpose": {
                        "readme": purposes.get(x["rel"], []),
                        "team": rec.get("purpose"),
                        "title": meta.get("title"),
                        "sheets": meta.get("sheets"),
                        "pages": meta.get("pages"),
                        "kind_guess": kind,
                        "basis": "team record"
                        if rec.get("purpose")
                        else "README"
                        if purposes.get(x["rel"])
                        else (
                            "title"
                            if meta.get("title")
                            else ("guess from the file name" if kind else "unknown")
                        ),
                    },
                    "review": {
                        "status": status,
                        "basis": basis,
                        "by": rec.get("by"),
                        "at": rec.get("at"),
                        "notes": D.redact(str(rec.get("notes") or ""))[:400],
                        "mentions": ment,
                    },
                    "flags": [{"kind": k, "text": t} for k, t in flags],
                }
            )
        removed = [
            {"rel": r, "removed_at": D.iso(e["removed_at"]), "first_seen": D.iso(e["first_seen"])}
            for r, e in entry["files"].items()
            if e.get("removed_at")
        ]
        kinds = {d["purpose"]["kind_guess"] for d in docs}
        convs = sum(d["purpose"]["kind_guess"] == "example conversations" for d in docs)
        expected = [
            {
                "kind": k,
                "label": label,
                "seen": [d["rel"] for d in docs if d["purpose"]["kind_guess"] == k],
            }
            for k, label, _ in EXPECTED
        ]
        contradictions = [
            {"rel": d["rel"], "text": f["text"]}
            for d in docs
            for f in d["flags"]
            if f["kind"] == "contradiction"
        ]
        contradictions += [
            {"rel": readme, "text": f"README lists {n}, not in the folder (yet)"} for n in absent
        ]
        last = max((v["first_seen"] for e in entry["files"].values() for v in e["versions"]),
                   default=None)  # fmt: skip
        folders.append(
            {
                "folder": str(folder),
                "exists": folder.is_dir(),
                "watched_since": D.iso(entry["first_watched"]),
                "documents": docs,
                "removed": removed,
                "readme": readme,
                "readme_absent": absent,
                "expected": expected,
                "expected_missing": [x["label"] for x in expected if not x["seen"]],
                "conversations_seen": convs,
                "contradictions": contradictions,
                "leaks": {k: v[:8] for k, v in leaks.items()},
                "last_change": D.iso(last),
                "seconds_since_last_change": int(now - last) if last else None,
                "counts": {
                    "files": len(docs),
                    "new": sum(any(f["kind"] == "new" for f in d["flags"]) for d in docs),
                    "amended": sum(any(f["kind"] == "amended" for f in d["flags"]) for d in docs),
                    "contradictions": len(contradictions),
                    "not_reviewed": sum(
                        d["review"]["status"].startswith("not reviewed") for d in docs
                    ),
                    "leaks": sum(any(f["kind"] == "leak" for f in d["flags"]) for d in docs),
                    "kinds_matched": len(kinds - {None}),
                },
                "completeness": "NOT confirmed complete: more documents may still arrive; the "
                "kinds are matched by name guesses, not confirmed",
            }
        )
    if changed and write:
        save_ledger(ledger)
    return {"folders": folders, "ledger": _rel(LEDGER), "review_file": _rel(REVIEW_FILE)}


# ---------------------------------------------------------------- final builds and tests


def _final_trace_paths() -> list[Path]:
    paths = sorted((D.ROOT / "traces").glob("*.log")) + sorted(D.RUNS.rglob("*.log"))
    return [p for p in paths if p.is_file()]


def _commit(ref: str | None) -> str | None:
    """The full commit a ref names, or None when git does not know it (never fail-open)."""
    if not ref:
        return None
    return D.git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip() or None


def builder_version(commit: str | None, freeze: str | None) -> dict:
    full = _commit(commit)
    tags = D.git("tag", "--points-at", full).split() if full else []

    def same(ref: str | None) -> bool | None:
        other = _commit(ref)
        if not (full and other):
            return None
        return not D.git("diff", "--name-only", full, other, "--", *D.CODE_PATHS).strip()

    return {
        "commit": commit,
        "known_to_git": bool(full),
        "tags": tags,
        "freeze_tag": freeze,
        "same_code_as_freeze": same(freeze),
        "same_code_as_head": same("HEAD"),
    }


def latest_freeze_tag() -> str | None:
    tags = D.git("tag", "--list", "freeze-final*", "--sort=-creatordate").split()
    return tags[0] if tags else None


def _folder_key(folder: str) -> str:
    p = Path(folder).expanduser()
    return str(p if p.is_absolute() else (D.ROOT / p).resolve())


def final_builds(ledger: dict, freeze: str | None) -> list[dict]:
    """Builder runs in the final form (START tool_api is a URL: our mock)."""
    out = []
    watched = {_folder_key(str(d)) for d in case_dirs()}
    for p in _final_trace_paths():
        t = D.parse_trace(p)
        if not t:
            continue
        lines = p.read_text(errors="replace").splitlines()
        start_line = next((ln for ln in lines if " START " in ln), "")
        api = re.search(r"\btool_api=(\S+)", start_line)
        if not api or not re.match(r"https?://", api.group(1)):
            continue
        read = next(
            (re.search(r"read (\d+) document", ln) for ln in lines if "document(s)" in ln), None
        )
        folder = t["briefs"][0] if t["briefs"] else None
        key = _folder_key(folder) if folder else None
        entry = ledger["folders"].get(key) if key in watched else None
        notes = []
        if entry:
            snap = snapshot_at(entry, t["start_ts"])
        else:
            snap = {"id": None, "files": [], "basis": "folder not watched by the dashboard"}
            notes.append(
                f"case folder {folder} is not a watched folder: documents unchecked "
                "(set FREYA_FINAL_CASE_DIR to include it)"
            )
        docs_read = int(read.group(1)) if read else None
        if docs_read is not None and snap["id"] and docs_read != len(snap["files"]):
            notes.append(
                f"the builder read {docs_read} document(s); the ledger shows "
                f"{len(snap['files'])} in the folder at that time"
            )
        newer = []
        if entry:
            early = t["start_ts"] < entry["first_watched"]
            for rel, e in entry["files"].items():
                vs = e["versions"][1:] if early and e.get("seen_at_ledger_start") else e["versions"]
                if any(v["first_seen"] > t["start_ts"] for v in vs):
                    newer.append(rel)
        if newer:
            notes.append(f"documents new or changed since this build: {', '.join(sorted(newer))}")
        if t["dirty"]:
            notes.append("dirty=True: the builder code had uncommitted changes")
        created = t["created"] or {}
        platform_test = any(x["name"].startswith("platform dry-run") for x in t["tests"])
        kind = (
            "real"
            if created
            else "real, no agent created"
            if platform_test or (t["end"] and not t["end"]["ok"])
            else "dry"
            if t["end"]
            else "running or killed"
        )
        bv = builder_version(t["git"], freeze)
        if not bv["known_to_git"]:
            notes.append(f"builder commit {t['git']} is unknown to this repo: version unverified")
        out.append(
            {
                "file": t["file"],
                "official": t["file"] == SUBMIT_TRACE,
                "start": t["start"],
                "start_ts": t["start_ts"],
                "end": t["end"],
                "kind": kind,
                "dry": kind == "dry",
                "mock_url": api.group(1),
                "case_folder": folder,
                "folder_watched": bool(entry),
                "dirty": t["dirty"],
                "builder": bv,
                "models": len(t["models"]),
                "tests": t["tests"],
                "created": created or None,
                "documents_read": docs_read,
                "snapshot": snap,
                "docs_changed_since": sorted(newer),
                "notes": notes,
            }
        )
    out.sort(key=lambda b: b["start_ts"])
    return out


PRACTICE_ID = re.compile(r"^PUB-\d+$")


def scenario_results() -> list[dict]:
    """Result files of scripts/sim_scenarios.py ({agent_id, simulation_id, started, rows}), which
    test on our mock without the kit's ledger shape (no all_rows)."""
    out = []
    for p in sorted(D.RUNS.rglob("*.json")):
        data = D.load_json(p)
        if not (isinstance(data, dict) and "rows" in data and "simulation_id" in data):
            continue
        if "all_rows" in data or not isinstance(data.get("rows"), list):
            continue
        rows = [r for r in data["rows"] if isinstance(r, dict)]
        out.append(
            {
                "id": D.rel(p),
                "agent_id": data.get("agent_id"),
                "start": data.get("started"),
                "end": D.iso(p.stat().st_mtime),
                "cases": [{"id": str(r.get("id", ""))} for r in rows],
                "strict_passed": sum(bool(r.get("pass")) for r in rows),
                "total": len(rows),
                "reps": 1,
                "complete": bool(rows),
                "source": "scripts/sim_scenarios.py result",
            }
        )
    return out


def final_tests(runs: list[dict], builds: list[dict]) -> list[dict]:
    """Result files that test a final agent: built by a final build, a 'final' slot, or non-practice
    case ids run after the final opened. Everything else stays historical practice."""
    opens = D.parse_utc(OPENS_UTC)
    by_id: dict[str, list[dict]] = {}
    for b in builds:
        if b["created"]:
            for k in ("workflow_id", "agent_id"):
                if b["created"].get(k):
                    by_id.setdefault(b["created"][k], []).append(b)
    out = []
    for r in runs:
        ids = [c.get("id", "") for c in r.get("cases", [])]
        try:
            start = D.parse_utc(r["start"]) if r.get("start") else float(r.get("end_ts") or 0)
        except ValueError:
            start = float(r.get("end_ts") or 0)
        linked = by_id.get(r.get("workflow_id") or "") or by_id.get(r.get("agent_id") or "") or []
        slot = str(r.get("slot") or "")
        why = (
            "agent built by a final build"
            if linked
            else "slot named final"
            if slot.startswith("final")
            else "non-practice case ids after the final opened"
            if start >= opens and ids and not any(PRACTICE_ID.match(i) for i in ids)
            else None
        )
        if not why:
            continue
        build = max(
            (b for b in linked if b["created"] and b["created"]["ts"] <= start),
            key=lambda b: b["created"]["ts"],
            default=None,
        )
        out.append(
            {
                "run": r["id"],
                "source": r.get("source", "run_cases result"),
                "why_final": why,
                "start": r.get("start"),
                "start_ts": start,
                "end": r.get("end"),
                "strict": f"{r.get('strict_passed')}/{r.get('total')}",
                "all_passed": bool(r.get("total")) and r.get("strict_passed") == r.get("total"),
                "reps": r.get("reps"),
                "complete": r.get("complete"),
                "cases": ids,
                "slot": slot or None,
                "agent_id": r.get("agent_id"),
                "workflow_id": r.get("workflow_id"),
                "build": build["file"] if build else None,
                "builder_commit": build["builder"]["commit"] if build else r.get("commit"),
                "snapshot": build["snapshot"]["id"] if build else None,
                "link_basis": "agent/workflow id matched to the newest final build created before "
                "the test"
                if build
                else "no final build created before this test matched: builder and documents "
                "unknown",
            }
        )
    return out


# ---------------------------------------------------------------- submission readiness


def _env_value(name: str) -> str | None:
    try:
        for ln in (D.ROOT / ".env").read_text().splitlines():
            m = re.match(rf"\s*(?:export\s+)?{name}\s*=\s*(.*)$", ln)
            if m:
                return m.group(1).strip().strip("'\"") or None
    except OSError:
        return None
    return None


def _git_ok(*args: str) -> str | None:
    out = D.git(*args).strip()
    return None if not out or out.startswith("ERROR") or out.startswith("fatal") else out


def _urls(obj: object) -> list[str]:
    if isinstance(obj, str):
        return [obj] if re.match(r"https?://", obj) else []
    if isinstance(obj, dict):
        return [u for v in obj.values() for u in _urls(v)]
    if isinstance(obj, list):
        return [u for v in obj for u in _urls(v)]
    return []


def _handoff_line(pattern: str) -> dict | None:
    """The most recently written WORKING_STATE line matching a pattern (by line commit time)."""
    times = line_times(D.WORKING_STATE)
    best = None
    for i, ln in enumerate(_cached_text(D.WORKING_STATE).splitlines(), 1):
        if re.search(pattern, ln, re.I):
            t = times[i - 1] if i - 1 < len(times) else None
            if best is None or (t or 0) > (best["ts"] or 0):
                best = {"source": D.rel(D.WORKING_STATE), "line": i, "ts": t, "time": D.iso(t),
                        "text": D.redact(ln.strip())[:240]}  # fmt: skip
    return best


def _item(name, status, owner, detail, evidence=None) -> dict:
    return {"item": name, "status": status, "owner": owner, "detail": detail,
            "evidence": evidence or []}  # fmt: skip


def _committed(path: str) -> bool:
    """Tracked and the working copy equals HEAD."""
    return bool(_git_ok("ls-files", "--", path)) and not D.git("status", "--porcelain", "--", path)


def _pushed(path: str) -> bool:
    """origin/main holds exactly the working copy's content (as of the last fetch or push)."""
    local = _git_ok("hash-object", "--", path)
    remote = _git_ok("rev-parse", f"origin/main:{path}")
    return bool(local and remote and local == remote)


def _env_secret_values() -> list[str]:
    """Values of .env keys that look secret (never shown; only counted)."""
    vals = set(D._SECRETS)
    try:
        for ln in (D.ROOT / ".env").read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)$", ln)
            if m and re.search(r"KEY|TOKEN|SECRET|PASSWORD", m.group(1)):
                v = m.group(2).strip().strip("'\"")
                if len(v) >= 8:
                    vals.add(v)
    except OSError:
        pass
    return [v for v in vals if v]


def _deploy_evidence(after_ts: float | None) -> dict | None:
    """The newest WORKING_STATE line reporting a finished mock deploy, if newer than after_ts."""
    times = line_times(D.WORKING_STATE)
    best = None
    neg = re.compile(r"\bnot\b|\bnext\b|pending|\bto deploy\b|todo|\bwill\b|redeploy needed", re.I)
    for i, ln in enumerate(_cached_text(D.WORKING_STATE).splitlines(), 1):
        if re.search(r"\bdeployed\b", ln, re.I) and re.search(r"mock|worker|wrangler", ln, re.I):
            if neg.search(ln):
                continue
            t = times[i - 1] if i - 1 < len(times) else None
            if t and (best is None or t > best["ts"]):
                best = {"source": D.rel(D.WORKING_STATE), "line": i, "ts": t, "time": D.iso(t),
                        "text": D.redact(ln.strip())[:240]}  # fmt: skip
    if best and after_ts and best["ts"] >= after_ts:
        return best
    return None


def readiness(builds: list[dict], tests: list[dict], docs: dict, freeze: str | None) -> list[dict]:
    items = []
    head = _git_ok("rev-parse", "--short", "HEAD")
    sim, user = "Simulation Developer", "the user"

    # documents
    for f in docs["folders"]:
        c = f["counts"]
        status = (
            "blocker"
            if not f["exists"] or not c["files"]
            else (
                "warn"
                if c["not_reviewed"] or c["contradictions"] or f["expected_missing"]
                else "ok"
            )
        )
        items.append(
            _item(
                "Case documents",
                status,
                sim,
                f"{c['files']} file(s) in {f['folder']}; {c['not_reviewed']} without a team review "
                f"record for the current version; {c['new']} new, {c['amended']} amended, "
                f"{c['contradictions']} to check; kinds not seen yet: "
                f"{', '.join(f['expected_missing']) or 'none'}. {f['completeness']}.",
            )
        )
        named = sorted({p.split(":")[0] for v in f.get("leaks", {}).values() for p in v})
        if named:
            items.append(
                _item(
                    "Case content in the repo",
                    "warn",
                    user,
                    f"{len(f['leaks'])} case file name(s) appear in tracked files outside traces/ and "
                    f"submission/: {', '.join(named[:8])}. The hard rule allows nothing from the case "
                    "in the builder; whether docs and mock/ may hold it is the user's call.",
                )
            )

    # builder
    fv = builder_version("HEAD", freeze)
    items.append(
        _item(
            "Builder version",
            "ok" if fv["same_code_as_freeze"] else "warn",
            "Methodology Developer",
            f"HEAD {head}: builder code (src/, builder/) "
            + ("identical to " if fv["same_code_as_freeze"] else "DIFFERS from or unknown vs ")
            + f"{freeze or 'no freeze-final* tag'}",
        )
    )

    # final build: the submission trace first, then the newest real build, then the newest dry run
    official = [b for b in builds if b["official"]]
    real = [b for b in builds if b["kind"].startswith("real")]
    b = (official or real or builds or [None])[-1]
    if not b:
        items.append(
            _item(
                "Final build",
                "blocker",
                sim,
                "no builder run in the final form yet "
                "(trace with tool_api=<mock URL>) under traces/ or runs/",
            )
        )
    else:
        ok = b["kind"] == "real" and b["end"] and b["end"]["ok"]
        clean = ok and not b["docs_changed_since"] and b["folder_watched"] and not b["dirty"]
        items.append(
            _item(
                "Final build",
                "ok" if clean else ("warn" if b["kind"].startswith("real") else "blocker"),
                sim,
                f"{b['file']} ({b['kind']}) started {b['start']}, END ok="
                f"{b['end']['ok'] if b['end'] else '?'}, documents snapshot {b['snapshot']['id']}"
                + ("; " + "; ".join(b["notes"]) if b["notes"] else ""),
            )
        )

    # final testing: a complete, fully passing test of the submitted agent after it was created
    ob = official[-1] if official else None
    good = [t for t in tests if ob and ob["created"] and t["build"] == ob["file"]
            and t["start_ts"] >= ob["created"]["ts"] and t["complete"]]  # fmt: skip
    passed = [t for t in good if t["all_passed"]]
    items.append(
        _item(
            "Final testing on our mock",
            "ok" if passed else "warn",
            sim,
            (
                f"{len(good)} complete test(s) of the submitted build; fully passing: "
                + (", ".join(f"{t['run']} {t['strict']}" for t in passed) or "none")
                + (
                    f"; others: {', '.join(t['run'] + ' ' + t['strict'] for t in good if t not in passed)}"
                    if len(good) > len(passed)
                    else ""
                )
            )
            if ob
            else f"{len(tests)} final test result(s), but no submission trace ({SUBMIT_TRACE}) to test yet",
        )
    )

    # mock
    mock_env = _env_value("MOCK_URL")
    mock_dirty = D.git("status", "--porcelain", "--", "mock").strip()
    adapted = _git_ok("log", "-1", f"--since={OPENS_UTC}", "--format=%h %ct %s", "--", "mock")
    adapted_ts = float(adapted.split()[1]) if adapted else None
    deployed = _deploy_evidence(adapted_ts)
    urls_used = sorted({x["mock_url"] for x in builds})
    items.append(
        _item(
            "Mock (Cloudflare Workers)",
            "ok" if mock_env and adapted and deployed and not mock_dirty else "warn",
            sim,
            f"MOCK_URL in .env: {mock_env or 'not set'}; latest mock/ commit since the case opened: "
            + (f"{adapted.split()[0]} at {D.iso(adapted_ts)}" if adapted else "none")
            + f"; uncommitted mock/ changes: {'yes' if mock_dirty else 'no'}; a finished deploy "
            f"reported in WORKING_STATE after that commit: {'yes' if deployed else 'not evidenced'}; "
            f"mock URLs used by final builds: {', '.join(urls_used) or 'none yet'}. Live status is "
            "not checked (no network calls); the deploy evidence is handoff text.",
            [deployed] if deployed else [],
        )
    )

    # workflow export
    wf_path = D.ROOT / SUBMIT_WORKFLOW
    export = D.load_json(wf_path) if wf_path.exists() else None
    if not isinstance(export, dict):
        items.append(_item("Workflow export", "blocker", sim, f"{SUBMIT_WORKFLOW} not found"))
    else:
        mock = (ob or b or {}).get("mock_url", "").rstrip("/")
        bad_urls = sorted(
            {u for u in _urls(export.get("workflow")) if mock and not u.startswith(mock)}
        )
        problems = []
        if not ob or not ob["created"]:
            problems.append(f"no CREATED line in {SUBMIT_TRACE} to match")
        elif export.get("workflow_id") != ob["created"].get("workflow_id"):
            problems.append("workflow_id differs from the submission trace's CREATED line")
        else:
            try:
                upd = D.parse_utc(
                    str(export.get("updated_at", "")).replace("+00:00", "Z")[:19] + "Z"
                )
            except ValueError:
                upd = None
            if upd is None:
                problems.append("export has no readable updated_at: cannot tie it to this run")
            elif upd < ob["start_ts"]:
                problems.append("export predates the submission trace's run (re-export?)")
        if bad_urls:
            problems.append(f"URLs outside the mock: {', '.join(bad_urls[:4])}")
        if not _committed(SUBMIT_WORKFLOW):
            problems.append("not committed (or modified since the commit)")
        elif not _pushed(SUBMIT_WORKFLOW):
            problems.append("origin/main does not hold this exact file (as of the last push/fetch)")
        hard = (
            bad_urls
            or not ob
            or not ob["created"]
            or (export.get("workflow_id") != ob["created"].get("workflow_id"))
        )
        items.append(
            _item(
                "Workflow export",
                "blocker" if hard else ("warn" if problems else "ok"),
                sim,
                f"workflow_id {export.get('workflow_id')}, agent_id {export.get('agent_id')}"
                + (
                    f"; {'; '.join(problems)}"
                    if problems
                    else "; matches the submission trace's run, committed, pushed"
                ),
            )
        )

    # trace
    if not ob:
        items.append(
            _item(
                "Matching trace",
                "blocker",
                sim,
                f"{SUBMIT_TRACE} not found or not a final-form trace",
            )
        )
    else:
        text = (D.ROOT / SUBMIT_TRACE).read_text(errors="replace")
        leaks = sum(1 for v in _env_secret_values() if v in text)
        problems = []
        if not (ob["end"] and ob["end"]["ok"]):
            problems.append("END ok is not True")
        if ob["dirty"] is not False:
            problems.append("dirty is not False")
        if not ob["builder"]["known_to_git"]:
            problems.append("its builder commit is unknown to this repo")
        elif not ob["builder"]["same_code_as_head"]:
            problems.append("its builder commit's code differs from HEAD")
        if leaks:
            problems.append(f"{leaks} secret value(s) from .env found in the trace")
        if not _committed(SUBMIT_TRACE):
            problems.append("not committed (or modified since the commit)")
        elif not _pushed(SUBMIT_TRACE):
            problems.append("origin/main does not hold this exact file (as of the last push/fetch)")
        items.append(
            _item(
                "Matching trace",
                "blocker"
                if leaks or not ob["end"] or not ob["end"]["ok"]
                else ("warn" if problems else "ok"),
                sim,
                f"git={ob['builder']['commit'] and ob['builder']['commit'][:8]} dirty={ob['dirty']} "
                f"documents snapshot {ob['snapshot']['id']}"
                + (f"; {'; '.join(problems)}" if problems else "; ok, committed, pushed"),
            )
        )

    # repository access
    origin = _git_ok("remote", "get-url", "origin")
    counts = (_git_ok("rev-list", "--left-right", "--count", "origin/main...HEAD") or "").split()
    ahead = int(counts[1]) if len(counts) == 2 and counts[1].isdigit() else None
    invite = _handoff_line(r"invit")
    granted = bool(invite and re.search(
        r"\binvited\b|access granted|collaborator (added|accepted)|invitation accepted",
        invite["text"], re.I) and not re.search(r"\bopen\b|pending|\bto invite\b|todo",
                                                invite["text"], re.I))  # fmt: skip
    problems = []
    if not origin:
        problems.append("no origin remote")
    if ahead is None:
        problems.append("cannot compare HEAD with origin/main")
    elif ahead:
        problems.append(
            f"HEAD has {ahead} commit(s) not in origin/main (as of the last fetch/push)"
        )
    if not granted:
        problems.append(
            "organiser access not evidenced (the newest WORKING_STATE line about the "
            "invite does not report it done)"
        )
    items.append(
        _item(
            "Repository access",
            "ok" if not problems else "warn",
            user,
            f"origin: {origin or 'none'}; "
            + ("; ".join(problems) if problems else "HEAD pushed; organiser access reported"),
            [invite] if invite else [],
        )
    )

    # submission.json
    draft = next((p for p in (D.ROOT / "submission.json", D.ROOT / "submission" / "submission.json",
                              D.RUNS / "submission.json") if p.exists()), None)  # fmt: skip
    if not draft:
        items.append(
            _item(
                "submission.json",
                "warn",
                user,
                "no draft found (repo root, "
                "submission/, runs/); RUNBOOK step 8 has the template; e-mail it "
                "before 20:00 UTC",
            )
        )
    else:
        sj = D.load_json(draft)
        sj = sj if isinstance(sj, dict) else {}
        miss = [k for k in ("team", "members", "repo", "commit", "run_command", "workflow",
                            "trace", "mock_url") if not sj.get(k)]  # fmt: skip
        mism = []
        if (
            ob
            and sj.get("mock_url")
            and str(sj["mock_url"]).rstrip("/") != ob["mock_url"].rstrip("/")
        ):
            mism.append("mock_url differs from the submission trace's")
        commit = str(sj.get("commit") or "")
        if commit and "origin/main" not in D.git("branch", "-r", "--contains", commit):
            mism.append("commit is not in origin/main (the organisers cannot clone it)")
        for k in ("workflow", "trace"):
            if sj.get(k) and not (D.ROOT / str(sj[k])).exists():
                mism.append(f"{k} path {sj[k]} does not exist")
        rc = str(sj.get("run_command") or "")
        if rc and not ("{case_folder}" in rc and "{mock_url}" in rc):
            mism.append("run_command lacks {case_folder} or {mock_url}")
        items.append(
            _item(
                "submission.json",
                "warn" if miss or mism else "ok",
                user,
                f"{_rel(draft)}: missing {', '.join(miss) or 'nothing'}"
                + (f"; {'; '.join(mism)}" if mism else ""),
            )
        )
    return items


def ownership() -> list[dict]:
    rows = {c["title"]: c for c in chats()}
    out = []
    for who, area, pattern in ROLES:
        ev = _handoff_line(pattern)
        c = rows.get(who)
        out.append(
            {
                "engineer": who,
                "area": area,
                "chat_state": c["state"] if c else ("person" if who == "the user" else "no chat"),
                "last_write": c["last_write"] if c else None,
                "evidence": ev,
            }
        )
    return out


def newest_updates(n: int) -> list[tuple[str, str]]:
    """The n newest '## UPDATE HH:MM UTC' blocks of WORKING_STATE (title, body)."""
    text = _cached_text(D.WORKING_STATE)
    found = re.findall(r"^## (UPDATE[^\n]*)\n(.*?)(?=^## |\Z)", text, re.M | re.S)

    def hhmm(block: tuple[str, str]) -> str:
        m = re.search(r"(\d\d:\d\d) UTC", block[0])
        return m.group(1) if m else "00:00"

    return sorted(found, key=hhmm, reverse=True)[:n]


def latest_updates() -> list[dict]:
    out = []
    for title, body in newest_updates(2):
        bullets = [b.strip() for b in re.split(r"\n- ", "\n" + body.strip()) if b.strip()]
        out.append(
            {
                "title": D.redact(title)[:200],
                "bullets": [D.redact(re.sub(r"\s+", " ", b))[:300] for b in bullets[:6]],
                "source": D.rel(D.WORKING_STATE),
            }
        )
    return out


def handoff_open_items(limit: int = 12) -> list[dict]:
    """Open or user-decision lines in the three newest WORKING_STATE updates (by their HH:MM)."""
    blocks = newest_updates(3)
    out = []
    pat = re.compile(r"\bopen\b|user decides|decision|not adopted|blocker|todo|pending", re.I)
    for title, body in blocks:
        for ln in body.splitlines():
            if pat.search(ln):
                out.append({"update": title[:80], "text": D.redact(ln.strip("- ").strip())[:240]})
    return out[:limit]


# ---------------------------------------------------------------- the view


def view(runs: list[dict], now: float | None = None) -> dict:
    now = time.time() if now is None else now
    ledger = load_ledger()
    docs = documents(now, ledger)
    freeze = latest_freeze_tag()
    builds = final_builds(ledger, freeze)
    tests = final_tests(runs + scenario_results(), builds)
    items = readiness(builds, tests, docs, freeze)
    blockers = [i for i in items if i["status"] == "blocker"]
    for f in docs["folders"]:
        unread = [
            d["rel"] for d in f["documents"] if d["review"]["status"].startswith("not reviewed")
        ]
        amended = [d["rel"] for d in f["documents"] if any(x["text"].startswith("AMENDED")
                                                            for x in d["flags"])]  # fmt: skip
        if unread:
            blockers.append(_item(f"{len(unread)} document(s) not reviewed", "warn",
                                  "Simulation Developer", ", ".join(unread)))  # fmt: skip
        if amended:
            blockers.append(_item(f"{len(amended)} document(s) amended after arrival", "warn",
                                  "Simulation Developer",
                                  "re-read: " + ", ".join(amended)))  # fmt: skip
    left = D.parse_utc(DEADLINE_UTC) - now
    return {
        "generated_at": D.iso(now),
        "deadline": {
            "utc": DEADLINE_UTC,
            "istanbul": "Sun 11 Oct 23:00 (UTC+3)",
            "target_utc": TARGET_UTC,
            "seconds_left": int(left),
            "basis": "official page: send submission.json before 20:00 UTC (23:00 Istanbul); "
            "target 19:00 from the RUNBOOK",
        },
        "opens_utc": OPENS_UTC,
        "documents": docs,
        "freeze_tag": freeze,
        "builds": builds,
        "tests": tests,
        "readiness": items,
        "blockers": blockers,
        "ownership": ownership(),
        "handoff_open_items": handoff_open_items(),
        "latest_updates": latest_updates(),
        "handoff_sources": [label for label, _ in handoff_sources()],
    }


def compact(v: dict) -> dict:
    """The final-case view for the review snapshot: no mention excerpts, nothing from the files."""
    if not v or v.get("error"):
        return {"error": (v or {}).get("error", "not computed")}
    folders = []
    for f in v["documents"]["folders"]:
        folders.append(
            {
                **{
                    k: f[k]
                    for k in (
                        "folder",
                        "completeness",
                        "counts",
                        "expected_missing",
                        "last_change",
                        "readme_absent",
                    )
                },  # fmt: skip
                "documents": [
                    {
                        "rel": d["rel"],
                        "first_seen": d["first_seen"],
                        "version": d["version"]["ledger"],
                        "purpose_basis": d["purpose"]["basis"],
                        "kind_guess": d["purpose"]["kind_guess"],
                        "review": d["review"]["status"],
                        "flags": [x["text"] for x in d["flags"]],
                    }
                    for d in f["documents"]
                ],
            }
        )
    return {
        "deadline": v["deadline"],
        "readiness": v["readiness"],
        "blockers": v["blockers"],
        "documents": {"folders": folders},
        "builds": [
            {k: b[k] for k in ("file", "start", "dry", "mock_url", "builder", "created", "notes")}
            | {"snapshot": b["snapshot"]["id"], "end_ok": (b["end"] or {}).get("ok")}
            for b in v["builds"]
        ],
        "tests": v["tests"],
    }


def summary_markdown(v: dict | None) -> str:
    if not v or v.get("error"):
        return f"\n## Final case readiness\n\nNot available: {(v or {}).get('error', 'not computed')}\n"
    lines = [
        "",
        "## Final case readiness",
        "",
        f"Deadline {v['deadline']['utc']} (23:00 Istanbul); {v['deadline']['seconds_left'] // 60} "
        "min left. Final testing below is separate from the historical practice results.",
        "",
        "| Item | Status | Owner | Detail |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {i['item']} | {i['status']} | {i['owner']} | {i['detail'].replace('|', '/')} |"
        for i in v["readiness"]
    ]
    for f in v["documents"]["folders"]:
        lines += ["", f"Documents in `{f['folder']}` ({f['completeness']}):", ""]
        lines += [
            f"- {d['rel']} (first seen {d['first_seen']}, ledger v{d['version']}, "
            f"purpose basis {d['purpose_basis']}, review: {d['review']}"
            + (f"; flags: {'; '.join(d['flags'])}" if d["flags"] else "")
            + ")"
            for d in f["documents"]
        ]
    lines += ["", f"Final builds: {len(v['builds'])}; final test result files: {len(v['tests'])}."]
    return "\n".join(lines) + "\n"
