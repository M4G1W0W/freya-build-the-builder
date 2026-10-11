#!/usr/bin/env python3
"""Review flags for Freya call records: what the judge does not score (dev tool, not the builder).

The platform judge scores only each case's listed checks, so a passing call can still break a
brief rule. This reads saved call records (the JSON of freya.get_call) and prints REVIEW FLAGS
with evidence. A flag is a pointer for a human, never a verdict: a brief may word a read-back
differently, a security refusal may close a call without any identity check, and a tool result
can ask the agent to repeat a question. Flags the record itself seems to justify are marked
level "info" with the reason; the rest are "review". The exit code is always 0.

Checks (2026-10-11 audit of E4-A-styledA and M3-G1-styledA):
  READBACK      the confirmation the customer said yes to before create_promise misses the
                product, the amount or the date of what was recorded (or there was none)
  WEEKDAY       a spoken "<weekday> <day> <month> [year]" whose weekday is wrong
  NO_GOODBYE    the agent's last message before the closing transition, transfer or close_call
                has no thanks or no goodbye
  SAID_TWICE    a sentence (or a near copy) the agent said in two messages; "info" when a tool
                result in between asked for it again
  UNVERIFIED    a close whose values mention verification with no verify_identity call run;
                "info" when the customer refused or questioned the security questions
  TOOL_REFUSED  the platform refused a tool the step does not have ("not currently available")

  python3 scripts/transcript_check.py runs/dev/r4/E4-A-styledA.calls [more files or dirs]
      [--rows runs/dev/r4/E4-A-styledA.attempts.jsonl] [--json out.json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from itertools import pairwise
from pathlib import Path

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]  # fmt: skip
STOP = set(
    "a an the any some of to for on in at and or but i you your we our it is am are be was this "
    "that with can could would will do does please tell me my what".split()
)
REFUSAL = re.compile(
    r"\b(don'?t want|do not want|won'?t|will not|not going to|refuse|rather not|no thanks|"
    r"not comfortable|why do you need|not answering|not telling)\b",
    re.I,
)
_WD = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_MO = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
DAY_FIRST = re.compile(rf"\b{_WD},?\s+(?:the\s+)?{_DAY}\s+(?:of\s+)?{_MO}(?:,?\s+(\d{{4}}))?", re.I)
MONTH_FIRST = re.compile(rf"\b{_WD},?\s+{_MO}\s+{_DAY}(?:,?\s+(\d{{4}}))?", re.I)


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _content(text: str) -> set[str]:
    return {w.rstrip("s") for w in _words(text).split() if w not in STOP and len(w) > 1}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s.strip()]


def parse(call: dict) -> tuple[list[dict], list[dict]]:
    """(turns, tools): spoken turns and tool events, each with t (seconds from start)."""
    turns, tools = [], []
    for m in call.get("messages") or []:
        t = float(m.get("secondsFromStart") or 0)
        text = m.get("message") or ""
        if m.get("role") in ("assistant", "user"):
            turns.append({"role": m["role"], "t": t, "text": text})
            continue
        try:
            e = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(e, dict):
            continue
        ev = e.get("event")
        if ev in ("function_call_start", "function_call_complete", "function_call_error"):
            args = e.get("args") if isinstance(e.get("args"), dict) else {}
            url = str(args.get("url") or "")
            name = url.rstrip("/").rsplit("/", 1)[-1] if url else str(e.get("function") or "")
            if name == "api_call":
                name = ""
            tools.append(
                {
                    "t": t,
                    "kind": ev.removeprefix("function_call_"),
                    "name": re.sub(r"_p\d+$", "", name),
                    "body": args.get("body") if isinstance(args.get("body"), dict) else {},
                    "raw": e,
                }
            )
        elif ev == "tool_call_routing":
            tools.append(
                {"t": t, "kind": "routing", "name": str(e.get("tool_name") or ""), "raw": e}
            )
        elif ev == "route_evaluated" and "not currently available" in text:
            tools.append({"t": t, "kind": "refused", "name": "", "raw": e})
    _name_completions(tools)
    return turns, tools


def _name_completions(tools: list[dict]) -> None:
    # A completion of an api_call has no url: it belongs to the latest unnamed start before it.
    last = ""
    for x in tools:
        if x["kind"] == "start":
            last = x["name"]
        elif x["kind"] in ("complete", "error") and not x["name"]:
            x["name"] = last


def _flag(code: str, level: str, t: float, evidence: str, note: str) -> dict:
    return {"code": code, "level": level, "t": round(t, 1), "evidence": evidence, "note": note}


def _products(tools: list[dict]) -> list[dict]:
    for x in tools:
        data = (x["raw"].get("result") or {}).get("data") if x["kind"] == "complete" else None
        if isinstance(data, dict) and isinstance(data.get("products"), list):
            return [p for p in data["products"] if isinstance(p, dict)]
    return []


def _product_names(p: dict) -> list[str]:
    names = []
    for k, v in p.items():
        if k in ("type", "name", "product_name", "label") and isinstance(v, str):
            names.append(v.replace("_", " "))
        elif "last4" in k and v:
            names.append(str(v))
    return names


def _numbers(text: str) -> set[float]:
    out = set()
    for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            out.add(round(float(n.replace(",", "")), 2))
        except ValueError:
            pass
    return out


def _says_date(text: str, iso: str) -> bool:
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return True  # nothing to compare against
    low = text.lower()
    month = MONTHS[d.month - 1]
    return iso[:10] in text or bool(
        re.search(rf"\b{d.day}(?:st|nd|rd|th)?\s+(?:of\s+)?{month}\b", low)
        or re.search(rf"\b{month}\s+{d.day}(?:st|nd|rd|th)?\b", low)
    )


def check_readback(turns: list[dict], tools: list[dict]) -> list[dict]:
    flags, seen = [], set()
    products = {str(p.get("product_id")): p for p in _products(tools)}
    starts = [x for x in tools if x["kind"] == "start" and x["name"] == "create_promise"]
    groups: dict[int, list[dict]] = {}
    for s in starts:
        users = [i for i, u in enumerate(turns) if u["role"] == "user" and u["t"] <= s["t"]]
        if not users:
            continue
        ask = next(
            (
                i
                for i in range(users[-1] - 1, -1, -1)
                if turns[i]["role"] == "assistant"
                and re.search(r"\bconfirm\b", turns[i]["text"], re.I)
                and "?" in turns[i]["text"]
            ),
            -1,
        )
        groups.setdefault(ask, []).append(s)
    for ask, calls in groups.items():
        if ask < 0:
            flags.append(
                _flag("READBACK", "review", calls[0]["t"], "no confirmation question before it",
                      "create_promise ran without a read-back the customer said yes to")
            )  # fmt: skip
            continue
        text = turns[ask]["text"]
        missing = []
        for c in calls:
            key = json.dumps(c["body"], sort_keys=True)
            if key in seen:
                continue  # a retry of the same promise
            seen.add(key)
            amount, date = c["body"].get("amount"), c["body"].get("date")
            prod = products.get(str(c["body"].get("product_id")))
            if prod is None and len(products) == 1:
                prod = next(iter(products.values()))
            names = _product_names(prod) if prod else []
            if names and not any(n.lower() in text.lower() for n in names):
                missing.append(f"product ({' / '.join(names)})")
            try:
                if amount is not None and round(float(amount), 2) not in _numbers(text):
                    missing.append(f"amount ({amount})")
            except (TypeError, ValueError):
                pass
            if date and not _says_date(text, str(date)):
                missing.append(f"date ({date})")
        if missing:
            flags.append(
                _flag("READBACK", "review", turns[ask]["t"], text,
                      "the confirmation before create_promise does not name: " + ", ".join(missing))
            )  # fmt: skip
    return flags


def _year(month: int, now: dt.date | None) -> int:
    if not now:
        return dt.date.today().year
    return now.year + 1 if month < now.month - 6 else now.year


def check_weekdays(turns: list[dict], now: dt.date | None) -> list[dict]:
    flags = []
    for u in turns:
        if u["role"] != "assistant":
            continue
        for rx, order in ((DAY_FIRST, "dm"), (MONTH_FIRST, "md")):
            for m in rx.finditer(u["text"]):
                wd = m.group(1).lower()
                day, mon = (m.group(2), m.group(3)) if order == "dm" else (m.group(3), m.group(2))
                month = MONTHS.index(mon.lower()) + 1
                year = int(m.group(4)) if m.group(4) else _year(month, now)
                try:
                    d = dt.date(year, month, int(day))
                except ValueError:
                    continue
                if WEEKDAYS[d.weekday()] != wd:
                    flags.append(
                        _flag("WEEKDAY", "review", u["t"], m.group(0),
                              f"{d.isoformat()} is a {WEEKDAYS[d.weekday()].title()}")
                    )  # fmt: skip
    return flags


def check_goodbye(turns: list[dict], tools: list[dict]) -> list[dict]:
    ends = [
        x["t"]
        for x in tools
        if (x["kind"] == "routing" and x["name"].startswith("transition_to_ev_"))
        or (x["kind"] == "start" and x["name"] in ("close_call", "transfer_to_agent"))
    ]
    if not any(x["kind"] == "start" and x["name"] == "close_call" for x in tools) or not ends:
        return []
    end = min(ends)
    said = [u for u in turns if u["role"] == "assistant" and u["t"] <= end + 2.0]
    if not said:
        return [_flag("NO_GOODBYE", "review", end, "", "the agent said nothing before closing")]
    last = said[-1]
    lacks = [w for w, rx in (("thanks", r"\bthank"), ("goodbye", r"good ?bye|\bbye\b"))
             if not re.search(rx, last["text"], re.I)]  # fmt: skip
    if not lacks:
        return []
    note = "no " + " and no ".join(lacks) + " before the call was closed"
    if any(u["role"] == "user" and last["t"] < u["t"] <= end for u in turns):
        note += "; the agent said nothing after the customer's last message"
    return [_flag("NO_GOODBYE", "review", last["t"], last["text"], note)]


ASK_AGAIN = re.compile(r"\b(ask|say|repeat)\b[^.]{0,40}\b(again|same)\b", re.I)


def _tool_between(tools: list[dict], t0: float, t1: float, sentence: str) -> str:
    """A tool result between t0 and t1 that asks to repeat, or carries half the sentence's words."""
    want = _content(sentence)
    for x in tools:
        if x["kind"] not in ("complete", "error") or not t0 <= x["t"] <= t1:
            continue
        raw = json.dumps(x["raw"].get("result") or x["raw"].get("error") or "")
        if ASK_AGAIN.search(raw) or (want and len(want & _content(raw)) * 2 >= len(want)):
            return f"{x['name'] or 'tool'} result at {x['t']:.1f}s"
    return ""


def _fragment(text: str) -> bool:
    """A customer message cut off mid-sentence (no closing punctuation)."""
    return bool(text.strip()) and not re.search(r"[.?!][\"')\]]*$", text.strip())


def check_said_twice(turns: list[dict], tools: list[dict]) -> list[dict]:
    msgs = [u for u in turns if u["role"] == "assistant"]
    if not msgs:
        return []
    first_t, last_t = msgs[0]["t"], msgs[-1]["t"]
    before: dict[float, str] = {}  # agent message time -> the customer message it answers
    last_user = ""
    for u in turns:
        if u["role"] == "user":
            last_user = u["text"]
        else:
            before.setdefault(u["t"], last_user)
    # Short lines ("Please go on.", "Correct.", "Thank you. Goodbye.") are stock replies.
    said = [
        (u["t"], s, u["text"])
        for u in msgs
        for s in sentences(u["text"])
        if len(_words(s).split()) >= 4
    ]
    flags = []
    exact: dict[str, list[tuple[float, str]]] = {}
    for t, s, _ in said:
        exact.setdefault(_words(s), []).append((t, s))
    for occ in exact.values():
        times = sorted({t for t, _ in occ})
        if len(times) < 2:
            continue
        s = occ[0][1]
        why = [_tool_between(tools, a, b, s) for a, b in pairwise(times)]
        note = f"said {len(times)} times ({', '.join(f'{t:.1f}s' for t in times)})"
        if times[-1] == last_t:
            note += ", the last time in the agent's final message"
        level = "review"
        if all(why):
            level, note = "info", note + f"; a tool result asked for it again ({why[0]})"
        elif all(_fragment(before.get(t, "")) for t in times):
            level, note = "info", note + "; each time it answered a cut-off customer message"
        flags.append(_flag("SAID_TWICE", level, times[0], s, note))
    seen = set()
    confirm = re.compile(r"\bconfirm\b", re.I)
    for i, (t0, a, ma) in enumerate(said):
        if t0 == first_t:
            continue  # the scripted opening; answering "are you a robot?" restates it
        for t1, b, mb in said[i + 1 :]:
            small, big = sorted((_content(a), _content(b)), key=len)
            if t1 == t0 or _words(a) == _words(b) or (a, b) in seen:
                continue
            if confirm.search(ma) or confirm.search(mb):
                continue  # a read-back restates the offer it confirms
            if len(small) >= 4 and len(small & big) >= 0.8 * len(small):
                seen.add((a, b))
                why = _tool_between(tools, t0, t1, a)
                note = f"said again in other words at {t1:.1f}s"
                if t1 == last_t:
                    note += ", in the agent's final message"
                if why:
                    note += f"; a tool result asked for it again ({why})"
                flags.append(
                    _flag("SAID_TWICE", "info" if why else "review", t0, f"{a} | {b}", note)
                )
    return flags


def check_unverified(call: dict, turns: list[dict], tools: list[dict]) -> list[dict]:
    flags = []
    for x in tools:
        if x["kind"] == "refused":
            flags.append(
                _flag("TOOL_REFUSED", "review", x["t"], "not currently available",
                      "the agent called a tool this step does not have")
            )  # fmt: skip
            break
    closes = [x for x in tools if x["kind"] == "start" and x["name"] == "close_call"]
    if not closes or any(x["kind"] == "start" and x["name"] == "verify_identity" for x in tools):
        return flags
    body = closes[0]["body"]
    if not any("verif" in str(v).lower() for v in body.values()):
        return flags
    refusals = [u for u in turns if u["role"] == "user" and REFUSAL.search(u["text"])]
    if refusals:
        note = f"no identity check ran; the customer refused or questioned it at {refusals[0]['t']:.1f}s"
        flags.append(_flag("UNVERIFIED", "info", closes[0]["t"], json.dumps(body), note))
    else:
        flags.append(
            _flag("UNVERIFIED", "review", closes[0]["t"], json.dumps(body),
                  "closed as not verified, but no identity check ran and no refusal was found")
        )  # fmt: skip
    return flags


def call_now(call: dict) -> dt.date | None:
    for m in call.get("messages") or []:
        hit = re.search(r'"now"\s*:\s*"(\d{4}-\d{2}-\d{2})', m.get("message") or "")
        if hit:
            return dt.date.fromisoformat(hit.group(1))
    return None


def check_call(call: dict) -> list[dict]:
    turns, tools = parse(call)
    return (
        check_readback(turns, tools)
        + check_weekdays(turns, call_now(call))
        + check_goodbye(turns, tools)
        + check_said_twice(turns, tools)
        + check_unverified(call, turns, tools)
    )


def case_ids(paths: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("call_id"), str) and (x.get("id") or x.get("case_id")):
                out[x["call_id"]] = str(x.get("id") or x.get("case_id"))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for p in paths:
        text = Path(p).read_text()
        for chunk in text.splitlines() if p.endswith(".jsonl") else [text]:
            if chunk.strip():
                walk(json.loads(chunk))
    return out


def call_files(paths: list[str]) -> list[Path]:
    files = []
    for p in map(Path, paths):
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("paths", nargs="+", help="call record JSON files or folders of them")
    ap.add_argument(
        "--rows", nargs="*", default=[], help="run rows (JSON/JSONL) mapping call ids to cases"
    )
    ap.add_argument("--json", help="also write every flag here")
    a = ap.parse_args(argv)
    cases = case_ids(a.rows)
    report, counts = [], {}
    for f in call_files(a.paths):
        call = json.loads(f.read_text())
        if not isinstance(call, dict) or not isinstance(call.get("messages"), list):
            continue
        cid = str(call.get("id") or f.stem)
        flags = check_call(call)
        report.append({"call_id": cid, "case": cases.get(cid, ""), "file": str(f), "flags": flags})
        for fl in flags:
            key = f"{fl['code']}/{fl['level']}"
            counts[key] = counts.get(key, 0) + 1
            print(f"{cid[:8]} {cases.get(cid, ''):7} {fl['level']:6} {fl['code']:12} {fl['t']:>6}s "
                  f"{fl['note']} :: {fl['evidence'][:160]}")  # fmt: skip
    print(
        f"REVIEW FLAGS (not verdicts): {len(report)} calls; "
        + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    )
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
