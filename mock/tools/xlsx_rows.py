"""Print every sheet of an .xlsx as JSON rows keyed by the header row (stdlib only).

    python3 mock/tools/xlsx_rows.py <file.xlsx> [--raw]

For turning the final zip's test-customer workbook into mock/data/customers.json by hand. Not builder
code. Dates stored as Excel serial numbers are shown as YYYY-MM-DD when the cell's number format is a
date format; --raw prints cell values exactly as stored.
"""

import datetime as dt
import json
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DATE_FMT_IDS = set(range(14, 23)) | {45, 46, 47}


def col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return [
        "".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root.findall("m:si", NS)
    ]


def date_styles(z: zipfile.ZipFile) -> set[int]:
    if "xl/styles.xml" not in z.namelist():
        return set()
    root = ET.fromstring(z.read("xl/styles.xml"))
    custom = {
        int(f.get("numFmtId")): f.get("formatCode", "")
        for f in root.findall("m:numFmts/m:numFmt", NS)
    }
    out = set()
    for i, xf in enumerate(root.findall("m:cellXfs/m:xf", NS)):
        fid = int(xf.get("numFmtId", "0"))
        code = custom.get(fid, "").lower()
        if fid in DATE_FMT_IDS or (
            code and re.search(r"(^|[^a-z])(d|m|y){1,4}", code) and "0" not in code
        ):
            out.add(i)
    return out


def sheets(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for s in wb.findall("m:sheets/m:sheet", NS):
        t = target[s.get(REL)].lstrip("/")
        out.append((s.get("name"), t if t.startswith("xl/") else "xl/" + t))
    return out


def cell_value(c: ET.Element, strings: list[str], dates: set[int], raw: bool):
    t = c.get("t")
    v = c.find("m:v", NS)
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
    if v is None or v.text is None:
        return None
    if t == "s":
        return strings[int(v.text)]
    if t == "b":
        return v.text == "1"
    if t in ("str", "e"):
        return v.text
    num = float(v.text)
    if not raw and int(c.get("s", "0")) in dates:
        return (dt.date(1899, 12, 30) + dt.timedelta(days=num)).isoformat()
    return int(num) if num.is_integer() else num


def read(path: str, raw: bool = False) -> dict[str, list[dict]]:
    with zipfile.ZipFile(path) as z:
        strings, dates = shared_strings(z), date_styles(z)
        out = {}
        for name, part in sheets(z):
            rows = []
            for r in ET.fromstring(z.read(part)).iter(f"{{{NS['m']}}}row"):
                row = {}
                for c in r.findall("m:c", NS):
                    row[col_index(c.get("r"))] = cell_value(c, strings, dates, raw)
                rows.append(row)
            rows = [r for r in rows if any(v not in (None, "") for v in r.values())]
            if not rows:
                out[name] = []
                continue
            header = rows[0]
            keys = {
                i: str(header.get(i) if header.get(i) not in (None, "") else f"col{i}")
                for i in range(max(max(r) for r in rows) + 1)
            }
            out[name] = [{keys[i]: r.get(i) for i in keys} for r in rows[1:]]
        return out


if __name__ == "__main__":
    print(json.dumps(read(sys.argv[1], "--raw" in sys.argv), indent=1, ensure_ascii=False))
