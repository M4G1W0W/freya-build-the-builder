"""Read a case folder (the bank's documents: Markdown, Word, PDF, Excel) into one text.

The official run command passes a folder (hackathon page, Submit tab: `build.py {case_folder}
{mock_url}`; FAQ: "a folder of the bank's documents in Markdown, Word, PDF and Excel"). The
standard library reads .docx and .xlsx (zip + XML); .pdf uses `pdftotext` when it is on PATH,
else a best-effort stream scan. A file that cannot be read is reported and skipped, never fatal.
"""

import re
import shutil
import subprocess
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml"}
FIRST = ("brief.md", "readme.md")  # Submit tab: "Read BRIEF.md first; README.md says what each is"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def decode_text(data: bytes) -> str:
    """UTF-8, else cp1252 (pasted e-mails), else UTF-8 with replacement: never crash (audit F79)."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    lines = []
    body = root.find(f"{W}body")
    for block in body if body is not None else []:
        if block.tag == f"{W}p":
            lines.append(_paragraph(block))
        elif block.tag == f"{W}tbl":
            for row in block.iter(f"{W}tr"):
                cells = [" ".join(_paragraph(p) for p in c.iter(f"{W}p")) for c in row]
                lines.append(" | ".join(c.strip() for c in cells))
    return "\n".join(lines).strip()


def _paragraph(p: ElementTree.Element) -> str:
    out = []
    for node in p.iter():
        if node.tag == f"{W}t" and node.text:
            out.append(node.text)
        elif node.tag == f"{W}tab":
            out.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            out.append("\n")
    return "".join(out)


def xlsx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{S}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{S}t")))
        sheets = _sheet_names(z, names)
        out = []
        for title, member in sheets:
            out.append(f"--- sheet: {title} ---")
            for row in ElementTree.fromstring(z.read(member)).iter(f"{S}row"):
                cells = [_cell(c, shared) for c in row.iter(f"{S}c")]
                if any(cells):
                    out.append("\t".join(cells))
    return "\n".join(out).strip()


def _sheet_names(z: zipfile.ZipFile, names: set[str]) -> list[tuple[str, str]]:
    """(sheet title, zip member) in workbook order; falls back to the sheet files' names."""
    try:
        wb = ElementTree.fromstring(z.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target", "") for r in rels}
        out = []
        for sh in wb.iter(f"{S}sheet"):
            t = target.get(sh.get(f"{R}id"), "").lstrip("/")
            member = t if t.startswith("xl/") else "xl/" + t
            if member in names:
                out.append((sh.get("name", member), member))
        if out:
            return out
    except (KeyError, ElementTree.ParseError):
        pass
    found = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    return [(Path(n).stem, n) for n in found]


def _cell(c: ElementTree.Element, shared: list[str]) -> str:
    kind = c.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in c.iter(f"{S}t"))
    v = c.find(f"{S}v")
    if v is None or v.text is None:
        return ""
    if kind == "s":
        i = int(v.text)
        return shared[i] if 0 <= i < len(shared) else ""
    return v.text


def pdf_text(path: Path) -> str:
    if shutil.which("pdftotext"):
        done = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=120
        )
        if done.returncode == 0 and done.stdout.strip():
            return decode_text(done.stdout).strip()
    return _pdf_streams_text(path.read_bytes())


def _pdf_streams_text(data: bytes) -> str:
    """Best effort without dependencies: inflate each stream, keep the strings shown by Tj/TJ."""
    lines = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        for block in re.findall(rb"BT(.*?)ET", raw, re.S):
            parts = re.findall(rb"\((.*?)(?<!\\)\)\s*Tj|\[(.*?)\]\s*TJ", block, re.S)
            text = []
            for tj, arr in parts:
                if tj:
                    text.append(_pdf_string(tj))
                else:
                    text.extend(_pdf_string(s) for s in re.findall(rb"\((.*?)(?<!\\)\)", arr, re.S))
            if text:
                lines.append("".join(text))
    return "\n".join(lines).strip()


def _pdf_string(s: bytes) -> str:
    s = re.sub(rb"\\([nrtbf()\\])", lambda m: {b"n": b"\n"}.get(m.group(1), m.group(1)), s)
    return decode_text(s)


READERS: dict[str, Callable[[Path], str]] = {
    ".docx": docx_text,
    ".xlsx": xlsx_text,
    ".xlsm": xlsx_text,
    ".pdf": pdf_text,
}


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return decode_text(path.read_bytes())
    reader = READERS.get(suffix)
    if reader is None:
        raise ValueError(f"no reader for {suffix or 'files without a suffix'}")
    return reader(path)


MAX_DOC_CHARS = 60_000  # a data dump (thousands of records) would swamp every model call


def capped(name: str, text: str, warn: Callable[[str], None] = lambda _: None) -> str:
    """A document's text for the model calls: an oversized one keeps its first MAX_DOC_CHARS."""
    if len(text) <= MAX_DOC_CHARS:
        return text
    warn(f"{name}: {len(text)} chars; the model reads the first {MAX_DOC_CHARS}")
    cut = len(text) - MAX_DOC_CHARS
    return text[:MAX_DOC_CHARS] + f"\n[... cut by the builder: {cut} more chars]"


def case_files(folder: Path) -> list[Path]:
    """Every file below the folder: BRIEF.md, then README.md, then the rest by path."""
    files = [
        p
        for p in folder.rglob("*")
        if p.is_file()
        and not any(
            part.startswith(".") or part == "__MACOSX" for part in p.relative_to(folder).parts
        )
    ]

    def key(p: Path) -> tuple[int, str]:
        name = p.name.lower()
        rank = FIRST.index(name) if name in FIRST else len(FIRST)
        return rank, str(p.relative_to(folder)).lower()

    return sorted(files, key=key)


def read_folder(folder: Path, warn: Callable[[str], None]) -> list[tuple[str, str]]:
    """(relative path, text) per readable, non-empty file; every other file is reported."""
    out = []
    for p in case_files(folder):
        rel = str(p.relative_to(folder))
        try:
            text = read_file(p)
        except Exception as e:  # one odd file must not stop the build (page: crash fixes allowed)
            warn(f"case folder: skipped {rel}: {type(e).__name__}: {str(e)[:120]}")
            continue
        if not text.strip():
            warn(f"case folder: no text read from {rel}")
            continue
        out.append((rel, text))
    return out
