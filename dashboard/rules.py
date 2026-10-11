"""Rules & Cases: organizer rules, briefs and cases, internal decisions, open interpretations (read-only).

Original text is read from the source files on every request (cached by file stat and git HEAD).
Summaries come from dashboard/rules_catalog.json, which the team wrote: each summary carries a verbatim
quote that is re-found in its source file here, so a changed source shows up as stale instead of
silently drifting. Labels come from the catalog's source registry: official organizer material (the
page snapshots and the kit) vs internal (team-written) vs locally derived (fixtures). Nothing is
fetched, written or executed except read-only git; Claude session files are never read.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import data as D

CATALOG = Path(__file__).with_name("rules_catalog.json")
ISTANBUL_OFFSET = 3 * 3600  # Turkey keeps UTC+3 all year (no DST since 2016)
OFFICIAL_CASES = "kit/public-test-set.json"
PAGE_CASES = "docs/reference/hackathon_practice_cases.json"
FIXTURE_CASES = "tests/fixtures/cases"
OFFICIAL_BRIEFS = "kit/briefs"
FIXTURE_BRIEFS = "tests/fixtures/briefs"
ORGANIZER = ("organizer_rule", "submission", "deadline", "after_hidden_briefs", "scoring", "limit")
INTERNAL = ("internal_budget", "internal_freeze", "internal_promotion", "internal_other")
CONTEXT_CHARS = 1500

_cache: dict[str, object] = {"key": None, "view": None}


# ---------------------------------------------------------------- sources


def _git_meta(rel: str) -> dict:
    last = D.git("log", "-1", "--format=%h%x09%cI%x09%s", "--", rel).strip().split("\t")
    return {
        "last_commit": last[0] if len(last) == 3 else None,
        "last_commit_date": last[1] if len(last) == 3 else None,
        "last_commit_subject": last[2] if len(last) == 3 else None,
        "tracked": bool(D.git("ls-files", "--", rel).strip()),
        "uncommitted_changes": bool(D.git("status", "--porcelain", "--", rel).strip()),
    }


def source_meta(rel: str, registry: dict[str, dict]) -> dict:
    path = D.ROOT / rel
    reg = registry.get(rel)
    meta = {
        "file": rel,
        "label": reg["label"] if reg else "unregistered",
        "kind": reg.get("kind") if reg else "not in the dashboard's source registry: label unknown",
        "link": reg.get("link") if reg else None,
        "captured": reg.get("captured") if reg else None,
        "exists": path.exists(),
    }
    if not path.exists():
        return meta
    st = path.stat()
    meta.update(
        _git_meta(rel),
        size=st.st_size,
        modified=D.iso(st.st_mtime),
        sha256_current=hashlib.sha256(path.read_bytes()).hexdigest()[:12],
        sha256_note="hash of the file as it is now (not a historical value)",
    )
    return meta


# ---------------------------------------------------------------- quotes


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_quote(text: str, quote: str) -> tuple[int, int, str] | None:
    """(start, end, how) of `quote` in `text`: exact, else with whitespace runs collapsed."""
    i = text.find(quote)
    if i >= 0:
        return i, i + len(quote), "exact"
    chars, index, space = [], [], False
    for k, ch in enumerate(text):
        if ch.isspace():
            if space:
                continue
            chars.append(" ")
            space = True
        else:
            chars.append(ch)
            space = False
        index.append(k)
    flat, q = "".join(chars), _norm(quote)
    j = flat.find(q) if q else -1
    if j < 0:
        return None
    return index[j], index[j + len(q) - 1] + 1, "whitespace-normalised"


def locate(rel: str, quote: str) -> dict:
    """Where the quote is: line, enclosing markdown section, and the surrounding original paragraph."""
    path = D.ROOT / rel
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return {"status": "source missing", "line": None, "section": None, "original": None}
    hit = find_quote(text, quote)
    if not hit:
        return {
            "status": "stale: quote not found in the current source (it changed after the catalog was written)",
            "line": None,
            "section": None,
            "original": None,
        }
    start, end, how = hit
    heads = [m for m in re.finditer(r"^#{1,6} .*$", text[:start], re.M)]
    a = text.rfind("\n\n", 0, start)
    b = text.find("\n\n", end)
    a, b = (a + 2 if a >= 0 else 0), (b if b >= 0 else len(text))
    if b - a > CONTEXT_CHARS:
        a, b = max(a, start - CONTEXT_CHARS // 3), min(b, end + CONTEXT_CHARS // 3)
    return {
        "status": "verified" if how == "exact" else "verified (whitespace differs)",
        "line": text.count("\n", 0, start) + 1,
        "section": heads[-1].group(0).lstrip("#").strip() if heads else None,
        "original": D.redact(text[a:b].strip()),
    }


def _istanbul(utc: str) -> dict:
    try:
        ts = D.parse_utc(utc if utc.endswith("Z") else utc + "Z")
    except ValueError:
        return {"utc": utc, "istanbul": None, "status": "unparseable UTC value in the catalog"}
    now = time.time()
    left = ts - now
    return {
        "utc": D.iso(ts),
        "istanbul": time.strftime("%a %d %b %H:%M", time.gmtime(ts + ISTANBUL_OFFSET)) + " (UTC+3)",
        "status": "passed"
        if left < 0
        else f"in {int(left // 3600)} h {int(left % 3600 // 60)} min",
    }


def _item(it: dict, registry: dict[str, dict]) -> dict:
    out = {**it, **locate(it["source_file"], it["quote"])}
    reg = registry.get(it["source_file"])
    out["source_label"] = reg["label"] if reg else "unregistered"
    flags = []
    if it["category"] in ORGANIZER and out["source_label"] != "official":
        flags.append(
            f"cited source is {out['source_label']}, not official organizer material: "
            "shown as a rule only with this warning"
        )
    if it.get("utc"):
        out["time"] = _istanbul(it["utc"])
    out["flags"] = flags
    return out


# ---------------------------------------------------------------- briefs and cases


def _load_cases(rel: str) -> list[dict]:
    data = D.load_json(D.ROOT / rel)
    if isinstance(data, dict):
        data = data.get("cases", [])
    return [c for c in data or [] if isinstance(c, dict) and "id" in c]


def _case_files() -> list[str]:
    """Official sets, the fixtures, and any other case file a run's launch record names."""
    fixtures = sorted(str(p.relative_to(D.ROOT)) for p in (D.ROOT / FIXTURE_CASES).glob("*.json"))
    referenced = set()
    for meta in D.RUNS.rglob("*.meta.json"):
        data = D.load_json(meta)
        if isinstance(data, dict) and isinstance(data.get("cases"), str):
            referenced.add(D.relpath(data["cases"]))
    for calls in D.RUNS.rglob("calls.tsv"):
        referenced |= {
            D.relpath(r["casefile"])
            for r in D._calls_rows(calls.parent).values()
            if str(r.get("casefile", "")).endswith(".json")
        }
    kit = sorted(  # a new case file the organizers ship in the kit shows up by itself
        str(q.relative_to(D.ROOT))
        for q in (D.ROOT / "kit").rglob("*.json")
        if q.name != Path(OFFICIAL_CASES).name and _looks_like_cases(q)
    )
    known = {OFFICIAL_CASES, PAGE_CASES, *fixtures, *kit}
    extra = sorted(r for r in referenced if r not in known and (D.ROOT / r).exists())
    return [OFFICIAL_CASES, *kit, PAGE_CASES, *fixtures, *extra]


def _looks_like_cases(path: Path) -> bool:
    data = D.load_json(path)
    data = data.get("cases") if isinstance(data, dict) else data
    return (
        isinstance(data, list)
        and bool(data)
        and all(
            isinstance(c, dict) and "id" in c and ("expected" in c or "checks" in c) for c in data
        )
    )


def _case_view(c: dict) -> dict:
    keep = ("id", "brief", "family", "level", "title", "style", "script", "expected", "checks")
    out = {k: c.get(k) for k in keep if k in c}
    out["other_fields"] = sorted(k for k in c if k not in keep)
    return out


def case_diff(official: list[dict], page: list[dict]) -> list[dict]:
    """Case-by-case differences between the kit's cases and the cases captured from the page."""
    a, b = {c["id"]: c for c in official}, {c["id"]: c for c in page}
    out = []
    for cid in sorted(set(a) | set(b)):
        if cid not in a or cid not in b:
            out.append({"case": cid, "field": "(whole case)", "kit": cid in a, "page": cid in b})
            continue
        for k in sorted(set(a[cid]) | set(b[cid])):
            if a[cid].get(k) != b[cid].get(k):
                out.append({"case": cid, "field": k, "kit": a[cid].get(k), "page": b[cid].get(k)})
    return out


def _briefs(registry: dict[str, dict]) -> list[dict]:
    out = []
    files = sorted((D.ROOT / OFFICIAL_BRIEFS).glob("*.md")) + sorted(
        (D.ROOT / FIXTURE_BRIEFS).rglob("*.md")
    )
    for p in files:
        rel = str(p.relative_to(D.ROOT))
        meta = source_meta(rel, registry)
        if meta["label"] == "unregistered" and rel.startswith(FIXTURE_BRIEFS):
            meta["label"], meta["kind"] = (
                "locally derived",
                "test fixture brief (no provenance note)",
            )
        text = p.read_text(errors="replace")
        out.append(
            {
                **meta,
                "sections": [m.group(0) for m in re.finditer(r"^#{1,3} .*$", text, re.M)],
                "text": D.redact(text),
            }
        )
    return out


# ---------------------------------------------------------------- the view


def _fingerprint(cat: dict) -> str:
    files = {s["file"] for s in cat["sources"]} | {i["source_file"] for i in cat["items"]}
    files |= {b["source_file"] for d in cat.get("deadlines", []) for b in d["basis"]}
    files |= {str(p.relative_to(D.ROOT)) for d in (FIXTURE_CASES, OFFICIAL_BRIEFS, FIXTURE_BRIEFS)
              for p in (D.ROOT / d).rglob("*") if p.is_file()}  # fmt: skip
    files |= set(_case_files())
    parts = [D.git("rev-parse", "HEAD").strip(), str(CATALOG.stat().st_mtime)]
    for rel in sorted(files):
        try:
            st = (D.ROOT / rel).stat()
            parts.append(f"{rel}:{st.st_mtime}:{st.st_size}")
        except OSError:
            parts.append(f"{rel}:missing")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def view() -> dict:
    cat = json.loads(CATALOG.read_text())
    key = _fingerprint(cat)
    if _cache["key"] == key and _cache["view"] is not None:
        out = dict(_cache["view"])  # type: ignore[arg-type]
    else:
        out = _build(cat)
        _cache.update(key=key, view=out)
    for it in (
        out["deadlines"] + out["reported"] + out["organizer_rules"] + out["internal_decisions"]
    ):
        if it.get("utc"):  # the time left moves on between rebuilds
            it["time"] = _istanbul(it["utc"])
    return {**out, "generated_at": D.iso(time.time())}


def _build(cat: dict) -> dict:
    registry = {s["file"]: s for s in cat["sources"]}
    items = [_item(i, registry) for i in cat["items"]]
    case_files = _case_files()
    sources = {rel: source_meta(rel, registry) for rel in sorted(set(registry) | set(case_files))}
    for rel, meta in sources.items():
        if meta["label"] == "unregistered" and rel.startswith(FIXTURE_CASES):
            meta["label"], meta["kind"] = "locally derived", "test fixture (no provenance note)"
        elif meta["label"] == "unregistered" and rel.startswith("kit/"):
            meta["label"], meta["kind"] = (
                "official",
                "case file in the kit (kit/ is kept unmodified)",
            )
        elif meta["label"] == "unregistered" and rel.startswith("runs/"):
            meta["label"] = "locally derived"
            meta["kind"] = "case file named by a run's launch record (runs/ is gitignored)"
    for it in items:
        if it["category"] in ("source_date", "case_provenance") and it["source_file"] in sources:
            sources[it["source_file"]].setdefault("notes", []).append(
                {k: it.get(k) for k in ("category", "summary", "quote", "status", "line", "notes")}
            )
    official, page = _load_cases(OFFICIAL_CASES), _load_cases(PAGE_CASES)
    conflicts = []
    for c in cat.get("conflicts", []):
        sides = [{**s, **locate(s["source_file"], s["quote"])} for s in c["sides"]]
        conflicts.append({**c, "sides": sides})
    diffs = case_diff(official, page)
    conflicts.append(
        {
            "topic": f"Cases: {OFFICIAL_CASES} (kit) vs {PAGE_CASES} (captured from the page)",
            "kind": "computed",
            "explanation": f"{len(diffs)} field difference(s), computed at read time"
            + (f" (fields: {', '.join(sorted({d['field'] for d in diffs}))})" if diffs else "")
            + ". Which source prevails is not stated in the captured organizer text; 'the kit "
            "overrides the page' is a team assumption (CLAUDE.md).",
            "differences": diffs,
        }
    )
    by = lambda cats: [i for i in items if i["category"] in cats]  # noqa: E731
    deadlines = [
        {
            **d,
            "label": "official (date reconstructed)",
            "basis": [{**b, **locate(b["source_file"], b["quote"])} for b in d["basis"]],
            "time": _istanbul(d["utc"]),
        }
        for d in cat.get("deadlines", [])
    ]
    return {
        "endpoint": "GET /api/rules-and-cases",
        "about": cat.get("about"),
        "labels": cat.get("labels"),
        "deadlines": deadlines,
        "reported": [{**r, "time": _istanbul(r["utc"])} for r in cat.get("reported", [])],
        "internal_timing": [
            i for i in items if i["category"] == "internal_freeze" and i.get("utc")
        ],
        "organizer_rules": by(ORGANIZER),
        "internal_decisions": by(INTERNAL),
        "interpretations": by(("interpretation",)),
        "clarifications": by(("clarification",)),
        "conflicts_and_stale": conflicts,
        "missing": cat.get("missing", []),
        "sources": list(sources.values()),
        "briefs": _briefs(registry),
        "case_sets": [
            {
                **sources[rel],
                "cases": [_case_view(c) for c in _load_cases(rel)],
            }
            for rel in case_files
        ],
        "counts": {
            "items": len(items),
            "verified": sum(i["status"].startswith("verified") for i in items),
            "stale": sum(i["status"].startswith("stale") for i in items),
        },
    }
