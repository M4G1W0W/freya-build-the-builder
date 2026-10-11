"""Per case-and-rep evidence for independent review (read-only, local artefacts only).

Sources, in order of strength:
- the run_cases result row (all_rows): pass/fail, ledger differences, the judge text (cut at 400 chars by the
  kit, written only when the judge did NOT pass), call_id, the ledger's tool-call list, slowest turn, end reason;
- a raw call dump saved under runs/ (freya.get_call output): full transcript, tool arguments, bank responses and
  tool errors, the judge's full reason with the messages it cites, call timestamps, the agent version that
  answered, and the workflow snapshot's runtime variables (today_facts, date_table, account_facts, ...);
- a formatted transcript (.txt written by scripts/show_call.py) when only that was saved: messages, tool lines
  (cut at 300 chars) and the judge line, but no runtime variables;
- the deploy trace that published the agent (commit, input hashes, build mode), the case file (expected ledger)
  and the Score log row that cites the run (human interpretation, labelled as such).

Nothing is fetched from Freya. Anything not present locally is reported as "Not available" with the reason;
nothing is reconstructed or inferred. Judge message numbers count customer/agent messages from 0, as the judge does.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import data as D

NA = "Not available"
FACT_VARS = (
    "today_facts",
    "today_iso",
    "date_table",
    "account_facts",
    "callback_slots",
    "disclosure_text",
    "product_count",
    "account_status",
    "close_outcome",
    "end_event",
    "xfer_queue",
)
BANK_WRITES = ("create_promise", "add_note", "schedule_callback", "transfer_to_agent", "close_call")
PRE_NEGOTIATION = ("setup", "opening", "identity", "third_party", "load_account", "account_facts")
DATE_WORDS = re.compile(
    r"\b(today|tomorrow|tonight|next week|week after next|this week|end of (the )?month|monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|"
    r"october|november|december|\d{1,2}(st|nd|rd|th)\b|\d{4}-\d\d-\d\d)",
    re.I,
)
YES = re.compile(
    r"\b(yes|yeah|yep|correct|confirm(ed)?|that'?s right|ok(ay)?|sure|agreed|fine)\b", re.I
)
NO_VERDICT = re.compile(r"analysis never arrived|no verdict", re.I)
STRIP_KEYS = ("headers", "header", "url", "method")


# ---------------------------------------------------------------- local artefacts


def txt_index() -> dict[str, Path]:
    """call_id -> formatted transcript (.txt) whose first line is 'call <id> | ...' (rebuilt per request)."""
    index: dict[str, Path] = {}
    for p in D.RUNS.rglob("*.txt"):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:  # read-only
                m = re.match(r"call ([0-9a-f-]{36})\b", f.readline())
        except OSError:
            continue
        if m:
            index[m.group(1)] = p
    return index


def sha256_12(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def _strip(x: object) -> object:
    """Request/response payload without transport details (headers, url, method), at any depth."""
    if isinstance(x, dict):
        if "body" in x and set(x) <= {"body", *STRIP_KEYS}:
            return _strip(x["body"])
        if "data" in x and set(x) <= {"data", "status", "message", "status_code", *STRIP_KEYS}:
            return _strip(x["data"])
        return {k: _strip(v) for k, v in x.items() if k not in STRIP_KEYS}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _tool_name(fn: str, args: object) -> str:
    """api_call entries are named by their bank endpoint (…/v1/close_call -> api_call:close_call)."""
    if fn == "api_call" and isinstance(args, dict) and isinstance(args.get("url"), str):
        return "api_call:" + args["url"].rstrip("/").rsplit("/", 1)[-1]
    return fn


def _event(m: dict) -> dict | None:
    try:
        e = json.loads(m.get("message") or "")
    except ValueError:
        return None
    return e if isinstance(e, dict) else None


def parse_call(call: dict) -> dict:
    """Structured transcript from a raw call dump: messages (judge numbering), tool calls, routes, errors."""
    timeline, tools, conv = [], [], []
    for m in call.get("messages") or []:
        t = m.get("secondsFromStart")
        role = m.get("role")
        if role in ("user", "assistant"):
            item = {
                "n": len(conv),
                "t": t,
                "who": "customer" if role == "user" else "agent",
                "node": m.get("nodeId"),
                "text": D.redact(m.get("message") or ""),
            }
            conv.append(item)
            timeline.append({"kind": "message", **item})
            continue
        e = _event(m) if role == "system" else None
        if not e:
            continue
        ev = e.get("event")
        if ev == "function_call_start":
            raw_fn = str(e.get("function"))
            name = _tool_name(raw_fn, e.get("args"))
            entry = {
                "t": t,
                "function": name,
                "_raw": raw_fn,
                "node": m.get("nodeId"),
                "args": "(generated code; not shown)"
                if raw_fn == "code_exec"
                else _strip(e.get("args")),
                "result": None,
                "status": None,
                "error": None,
                "after_message": len(conv) - 1,
            }
            tools.append(entry)
            timeline.append({"kind": "tool_call", "t": t, "function": name, "i": len(tools) - 1})
        elif ev in (
            "function_call_complete",
            "function_call_complete_deferred",
            "function_call_error",
        ):
            raw_fn = str(e.get("function"))
            entry = next(
                (
                    x
                    for x in reversed(tools)
                    if x["_raw"] == raw_fn and x["result"] is None and x["error"] is None
                ),
                None,
            )
            if ev == "function_call_error":
                err = D.redact(
                    str(e.get("error") or e.get("message") or e.get("details") or "error")
                )[:300]
                if entry:
                    entry["error"], entry["status"] = err, "error"
                timeline.append(
                    {
                        "kind": "tool_error",
                        "t": t,
                        "function": entry["function"] if entry else raw_fn,
                        "error": err,
                    }
                )
            elif entry:
                res = e.get("result")
                entry["result"] = _strip(res)
                entry["status"] = res.get("status") if isinstance(res, dict) else None
        elif ev == "node_enter":
            timeline.append(
                {"kind": "node", "t": t, "node": e.get("node"), "from": e.get("from_node")}
            )
        elif ev == "route_evaluated" and e.get("matched"):
            timeline.append(
                {
                    "kind": "route",
                    "t": t,
                    "from": e.get("from_node"),
                    "to": e.get("target"),
                    "reason": D.redact(str(e.get("reason") or ""))[:200],
                }
            )
        elif ev in ("error", "max_turns_exceeded", "tool_call_routing", "call_ended"):
            detail = {k: v for k, v in e.items() if k != "event"}
            timeline.append(
                {"kind": ev, "t": t, "detail": D.redact(json.dumps(_strip(detail)))[:300]}
            )
    for x in tools:
        x.pop("_raw", None)
    snaps = [
        m.get("workflowSnapshot")
        for m in call.get("messages") or []
        if isinstance(m.get("workflowSnapshot"), dict)
    ]
    variables = {}
    if snaps:
        table = snaps[-1].get("variableTable") or {}
        for k in FACT_VARS:
            if isinstance(table.get(k), dict):
                variables[k] = D.redact(str(table[k].get("value")))
        for k, v in table.items():  # loaded products, as the bank returned them
            if k.startswith("load_account_response.data.products.") and isinstance(v, dict):
                variables[k.removeprefix("load_account_response.data.")] = v.get("value")
    return {
        "source": "raw",
        "messages": conv,
        "timeline": timeline,
        "tool_calls": tools,
        "runtime_variables": variables,
    }


TXT_LINE = re.compile(r"^\[\s*(-|[\d.]+)s?\]\s(.*)$")


def parse_txt(path: Path) -> dict:
    """Structured view of a formatted transcript (.txt); tool args/results are the cut text, not JSON."""
    lines = path.read_text(errors="replace").splitlines()
    judge = next(
        (ln.removeprefix("judge:").strip() for ln in lines[:3] if ln.startswith("judge:")), None
    )
    conv, tools, timeline, node = [], [], [], None
    for ln in lines:
        m = TXT_LINE.match(ln)
        if not m:
            if conv and timeline and timeline[-1]["kind"] == "message" and ln.strip():
                conv[-1]["text"] += "\n" + D.redact(ln)  # continuation of a multi-line message
            continue
        t = None if m.group(1) == "-" else float(m.group(1))
        body = m.group(2)
        if body.startswith(("AGENT: ", "CUST : ")):
            item = {
                "n": len(conv),
                "t": t,
                "who": "agent" if body.startswith("AGENT") else "customer",
                "node": node,
                "text": D.redact(body[7:]),
            }
            conv.append(item)
            timeline.append({"kind": "message", **item})
        elif (s := body.strip()).startswith("== enter "):
            node = s.removeprefix("== enter ").split(" ")[0]
            timeline.append({"kind": "node", "t": t, "node": node})
        elif s.startswith("-> "):
            fn, _, rest = s[3:].partition(" ")
            tools.append(
                {
                    "t": t,
                    "function": fn,
                    "node": node,
                    "args": D.redact(rest) if fn != "code_exec" else "(generated code; not shown)",
                    "result": None,
                    "status": None,
                    "error": None,
                    "after_message": len(conv) - 1,
                    "note": "text cut at 300 chars",
                }
            )
            timeline.append({"kind": "tool_call", "t": t, "function": fn, "i": len(tools) - 1})
        elif s.startswith("<- "):
            fn, _, rest = s[3:].partition(" ")
            entry = next(
                (x for x in reversed(tools) if x["function"] == fn and x["result"] is None), None
            )
            if entry:
                entry["result"] = D.redact(rest)
        elif s.startswith("~~ route "):
            timeline.append({"kind": "route", "t": t, "detail": D.redact(s[9:])[:300]})
        elif s.startswith("!! "):
            timeline.append({"kind": "error", "t": t, "detail": D.redact(s[3:])[:300]})
    return {
        "source": "txt",
        "messages": conv,
        "timeline": timeline,
        "tool_calls": tools,
        "runtime_variables": {},
        "judge_line": D.redact(judge) if judge else None,
    }


# ---------------------------------------------------------------- derived sections


def _classification_evidence(failed: list[str], row: dict) -> list[dict]:
    out = []
    if any(NO_VERDICT.search(s) for s in failed):
        bank_failed = any(not s.startswith("conversation:") for s in failed)
        out.append(
            {
                "category": "No judge verdict (bank records failed: not a platform error)"
                if bank_failed
                else "Platform errors",
                "matched": "no judge verdict",
                "context": next(s for s in failed if NO_VERDICT.search(s)),
                "source": "structural: the judge verdict never arrived",
            }
        )
    if (
        row.get("ended") == "customer-ended-call"
        and (row.get("slowest_turn_s") or 0) >= D.SLOW_TURN_S
    ):
        out.append(
            {
                "category": "Slow agent turn, customer hung up (latency)",
                "matched": f"customer-ended-call after a {row.get('slowest_turn_s')} s agent turn",
                "context": f"ended={row.get('ended')} slowest_turn_s={row.get('slowest_turn_s')}",
                "source": "structural",
            }
        )
    if not row.get("tools") and (row.get("slowest_turn_s") or 0) == 0:
        out.append(
            {
                "category": "Platform errors",
                "matched": "no tool call and 0 s turns",
                "context": f"tools={row.get('tools')} slowest_turn_s={row.get('slowest_turn_s')}",
                "source": "structural",
            }
        )
    structured = D._ledger_category(failed)
    if structured:
        out.append(
            {
                "category": structured,
                "matched": "ledger difference",
                "context": next((s for s in failed if D.LEDGER.match(s)), ""),
                "source": "ledger diff (structured)",
            }
        )
    for name, pat in D.CATEGORIES:
        for s in failed:
            m = re.search(pat, s, re.I)
            if m:
                a, b = max(0, m.start() - 60), min(len(s), m.end() + 60)
                out.append(
                    {
                        "category": name,
                        "matched": m.group(0),
                        "context": D.redact(s[a:b]),
                        "source": "keyword in result row (low confidence)",
                    }
                )
                break
    return out


def _scope(parsed: dict) -> tuple[list[dict], str]:
    negotiation = [m for m in parsed["messages"] if m.get("node") == "negotiate"]
    if negotiation:
        return negotiation, "messages recorded in the 'negotiate' node"
    rest = [m for m in parsed["messages"] if m.get("node") not in PRE_NEGOTIATION]
    return rest, "messages outside the opening/identity/setup nodes (no 'negotiate' node recorded)"


def _date_chain(
    parsed: dict | None, ledger: list[dict], expected: dict | None, why_missing: str
) -> dict:
    chain: dict = {
        "note": "customer wording -> runtime date facts -> proposed date -> confirmation -> recorded promise"
    }
    exp = (expected or {}).get("promises")
    diff = next((x for x in ledger if x["field"] == "promises"), None)
    from_diff = (
        diff["actual"] if diff else "score_ledger reported no promise difference for this rep"
    )
    if not parsed:
        for k in ("customer_wording", "runtime_date_facts", "proposed_dates", "confirmation"):
            chain[k] = f"{NA}: {why_missing}"
        chain["recorded_promise"] = {"from_ledger_diff": from_diff, "expected": exp}
        return chain
    msgs, scope = _scope(parsed)
    chain["scope"] = scope
    chain["source"] = (
        "raw call dump" if parsed["source"] == "raw" else "formatted transcript (.txt)"
    )
    chain["customer_wording"] = [
        m for m in msgs if m["who"] == "customer" and DATE_WORDS.search(m["text"])
    ]
    v = parsed["runtime_variables"]
    facts = {k: v[k] for k in ("today_facts", "date_table", "account_facts") if k in v}
    chain["runtime_date_facts"] = facts or (
        f"{NA}: a .txt transcript holds no runtime variables"
        if parsed["source"] == "txt"
        else f"{NA} in the snapshot"
    )
    proposals = [m for m in msgs if m["who"] == "agent" and DATE_WORDS.search(m["text"])]
    chain["proposed_dates"] = proposals
    pairs = []
    for c in msgs:  # every customer yes, attached to the agent date message just before it
        if c["who"] != "customer" or not YES.search(c["text"]):
            continue
        before = [p for p in proposals if p["n"] < c["n"]]
        if before:
            pairs.append({"after_agent_message": before[-1]["n"], "customer": c})
    chain["confirmation"] = (
        pairs or f"{NA}: no customer yes/confirm follows an agent date message in scope"
    )
    calls = [t for t in parsed["tool_calls"] if str(t["function"]).startswith("create_promise")]
    chain["recorded_promise"] = {
        "tool_calls": calls or "no create_promise call in the transcript",
        "from_ledger_diff": from_diff,
        "expected": exp,
    }
    chain["selection_rule"] = (
        "messages listed when they contain a weekday, month, ordinal day, ISO date or relative day word (keyword match, not interpretation)"
    )
    return chain


def _products(
    parsed: dict | None, ledger: list[dict], expected: dict | None, why_missing: str
) -> dict:
    out: dict = {
        "note": "per product: what the bank loaded, agent messages that name it, notes and promises recorded"
    }
    exp = expected or {}
    out["from_ledger_diff"] = [
        x for x in ledger if x["field"] in ("promises", "notes", "outcome")
    ] or "no ledger difference reported"
    out["expected"] = {k: exp.get(k) for k in ("promises", "notes", "outcome", "reason")}
    if not parsed or parsed["source"] != "raw":
        out["products"] = (
            f"{NA}: {why_missing if not parsed else 'a .txt transcript holds no loaded-product variables'}"
        )
        return out
    v = parsed["runtime_variables"]
    products = {}
    for i in range(10):
        pid = v.get(f"products.{i}.product_id")
        if pid is None:
            continue
        ptype = str(v.get(f"products.{i}.type") or "")
        words = tuple(w for w in {ptype.replace("_", " ").lower()} if w)
        suffix = f"_p{i + 1}"
        products[str(pid)] = {
            "loaded": {k.split(".", 2)[2]: v[k] for k in v if k.startswith(f"products.{i}.")},
            "agent_messages_naming_it": [
                m
                for m in parsed["messages"]
                if m["who"] == "agent" and any(w in m["text"].lower() for w in words)
            ],
            "naming_rule": f"agent messages containing '{', '.join(words)}' (the bank's product type with spaces)",
            "notes_recorded": [
                t
                for t in parsed["tool_calls"]
                if str(t["function"]).startswith("add_note") and str(t["function"]).endswith(suffix)
            ],
            "promises_recorded": [
                t
                for t in parsed["tool_calls"]
                if str(t["function"]).startswith("create_promise")
                and str(t["function"]).endswith(suffix)
            ],
            "expected_promises": [
                p for p in exp.get("promises") or [] if p.get("product_id") == pid
            ],
            "expected_notes": [
                n
                for n in exp.get("notes") or []
                if isinstance(n, dict) and n.get("product_id") == pid
            ],
        }
    out["products"] = products or f"{NA}: the snapshot holds no loaded products"
    out["attempts"] = (
        "Not recorded as such: the agent messages naming each product are listed; counting them as offers or attempts is left to the reviewer"
    )
    return out


# ---------------------------------------------------------------- evidence for one case and rep


class EvidenceError(ValueError):
    """A request the endpoint answers with 4xx (unknown run/case, rep out of range)."""


def detail(runs: list[dict], run_id: str, case_id: str, rep: int | None) -> dict:
    run = next((r for r in runs if r["id"] == run_id), None)
    if not run:
        raise EvidenceError("unknown run")
    data = (
        D.load_json(D.ROOT / run_id) or {}
    )  # run_id is one of the known result files, never a free path
    reps = data.get("all_rows") or []
    case = next((c for c in run["cases"] if c["id"] == case_id), None)
    if not case:
        raise EvidenceError("unknown case for this run")
    requested = rep
    rep = rep or next((f["rep"] for f in case["failures"]), 1)
    if not 1 <= rep <= len(reps):
        raise EvidenceError(f"rep {rep} not in this run ({len(reps)} reps recorded)")
    row = next((r for r in reps[rep - 1] if r.get("id") == case_id), None)
    if row is None:
        raise EvidenceError(f"{case_id} has no row in rep {rep}")
    failed = [str(s) for s in row.get("failed") or []]
    fd = D.failure_detail(row) if failed else None
    ledger = fd["ledger"] if fd else []
    cdef = D.load_cases(None if run["case_file"].startswith("kit/") else run["case_file"]).get(
        case_id, {}
    )

    call_id = row.get("call_id")
    dump_path = D.call_index().get(call_id) if call_id else None
    call = D.load_json(dump_path) if dump_path else None
    call = call if isinstance(call, dict) else None
    txt_path = None if call else (txt_index().get(call_id) if call_id else None)
    parsed = parse_call(call) if call else (parse_txt(txt_path) if txt_path else None)
    why_missing = "this call was not saved locally (it exists only on Freya)"
    judge_full = call.get("successCriteriaResult") if call else None
    judge_rows = [
        s.removeprefix("conversation:").strip() for s in failed if s.startswith("conversation:")
    ]
    no_verdict = any(NO_VERDICT.search(s) for s in judge_rows)

    deploy = next((t for t in D.all_traces() if t["file"] == run.get("deploy_log")), None)
    untrusted = any("started before commit" in f for f in run["flags"])
    if untrusted:
        deploy = None
    spec_path = D.ROOT / deploy["spec"] if deploy and deploy.get("spec") else None
    start_line = (
        (Path(D.ROOT / deploy["file"]).read_text(errors="replace").splitlines() or [""])[0]
        if deploy
        else ""
    )
    sha = re.search(r"sha256=(\S+)", start_line)
    family = case.get("family") or ""
    primary = fd["category"] if fd else None
    scorer_lines = [s for s in failed if not s.startswith("conversation:")]
    tags = list(fd["tags"] if fd else [])
    if no_verdict and not any("No judge verdict" in t for t in tags):
        tags.append("No judge verdict")
    if no_verdict and not scorer_lines:  # a missing verdict never hides a bank-record failure
        primary = "Platform errors"
    date_related = (
        primary == "Date calculations"
        or family == "Dates"
        or any(x["field"] == "promises" for x in ledger)
    )
    multi = family == "Multi-product" or bool(
        parsed and parsed["runtime_variables"].get("products.1.product_id")
    )
    last_rep = rep == len(reps)
    status = (
        "completed, official-style (3+ reps, full case set)"
        if run["official_style"]
        else (
            "completed, NOT official-style ("
            + ("subset" if run["subset"] else f"{run['reps']} rep(s)")
            + ")"
        )
        if run["complete"]
        else "incomplete"
    )
    if judge_full:
        full = {
            "source": "raw call dump",
            "success": judge_full.get("success"),
            "reason": D.redact(str(judge_full.get("reason"))),
            "cited_messages": judge_full.get("relevantMessages"),
        }
    elif parsed and parsed.get("judge_line"):
        full = {
            "source": f"formatted transcript header ({D.rel(txt_path)})",
            "reason": parsed["judge_line"],
        }
    else:
        full = f"{NA}: {why_missing}"
    return {
        "case": {
            "run": run_id,
            "case": case_id,
            "rep": rep,
            "requested_rep": requested,
            "rep_note": None
            if requested
            else "no rep requested: the first failed rep is shown (rep 1 if none failed)",
            "reps_recorded": len(reps),
            "family": family,
            "title": cdef.get("title"),
            "run_status": status,
        },
        "result": {
            "raw_rep_pass": bool(row.get("pass")),
            "all_reps": case["reps"],
            "strict_case_pass_in_this_run": case["strict"],
            "official": run["official_style"],
            "call_id": call_id or NA,
            "ended": row.get("ended"),
            "ledger_calls_in_order": row.get("tools"),
            "ledger_calls_note": "run_cases stores the bank ledger's list of tool calls (led['calls']) here",
            "slowest_turn_s": row.get("slowest_turn_s"),
        },
        "classification": {
            "primary": primary,
            "tags": tags,
            "evidence": _classification_evidence(failed, row) if failed else [],
            "method": "auto: structural checks, then the ledger diff, then keywords (low confidence); the human classification is in the Score log rows below",
        },
        "platform_adjusted_interpretation": {
            "ignored_in_platform_adjusted_view": primary == "Platform errors",
            "rule": "a rep is ignored only with structural platform evidence (no tool call and 0 s turns, or no judge verdict while the bank records passed); this is an INTERPRETATION, never the official score",
        },
        "judge": {
            "from_result_row": ("no verdict: " + "; ".join(judge_rows))
            if no_verdict
            else judge_rows
            or (
                "judge passed (run_cases writes a judge line only when the judge did not pass); the failure is in the ledger"
                if failed
                else "rep passed"
            ),
            "result_row_note": "cut at 400 characters by kit/tools/run_cases.py",
            "full": full,
        },
        "bank_records": {
            "ledger_differences": ledger
            or (
                "none reported"
                if not failed
                else "none reported (the failure is conversation-only)"
                if not scorer_lines
                else "no field differences; see scorer_checks"
            ),
            "scorer_checks": [D.redact(x) for x in (fd["other"] if fd else [])]
            or "none failed besides the field differences",
            "expected_ledger": cdef.get("expected") or NA,
            "expected_source": f"{run['case_file']} (current version of the case file; chosen by: {run.get('case_file_source', 'file-name convention')})",
            "final_ledger": f"{NA}: run_cases saves the differences above and the ledger's call list (result.ledger_calls_in_order), not the record values",
            "bank_writes_in_call": [
                t
                for t in parsed["tool_calls"]
                if str(t["function"]).removeprefix("api_call:").startswith(BANK_WRITES)
            ]
            if parsed
            else f"{NA}: {why_missing}",
        },
        "transcript": {
            "source": D.rel(dump_path) if dump_path else (D.rel(txt_path) if txt_path else None),
            "kind": "raw call dump (structured)"
            if call
            else (
                "formatted transcript (.txt): tool text cut at 300 chars, no runtime variables"
                if txt_path
                else f"{NA}: {why_missing}"
            ),
            "message_numbering": "n counts customer/agent messages from 0, as the judge's 'Message N' does",
            "messages": parsed["messages"] if parsed else None,
            "timeline": parsed["timeline"] if parsed else None,
            "tool_calls": parsed["tool_calls"] if parsed else None,
        },
        "runtime_variables": parsed["runtime_variables"]
        if parsed and parsed["source"] == "raw"
        else f"{NA}: needs a raw call dump",
        "date_chain": _date_chain(parsed, ledger, cdef.get("expected"), why_missing)
        if date_related
        else "not a date-related failure (no promise difference, not a Dates case, primary category is not Date calculations)",
        "multi_product": _products(parsed, ledger, cdef.get("expected"), why_missing)
        if multi
        else "not a multi-product case",
        "provenance": {
            "commit": run["commit"],
            "commit_source": run["commit_source"],
            "agent_id": run["agent_id"],
            "slot": run["slot"],
            "agent_version_deployed": f"{NA}: the matched deploy trace predates the tested commit"
            if untrusted
            else run["version"]
            if run["version"] is not None
            else f"{NA}: not in the deploy trace",
            "agent_version_in_call": call.get("entityVersionNumber", NA)
            if call
            else f"{NA}: needs a raw call dump",
            "workflow_id_deployed": (run["workflow_id"] or NA)
            if not untrusted
            else f"{NA}: the matched deploy trace predates the tested commit",
            "workflow_id_in_call": call.get("assistantWorkflowId", NA)
            if call
            else f"{NA}: needs a raw call dump",
            "deploy_trace": (run["deploy_log"] or NA)
            if not untrusted
            else f"{NA}: the matched deploy trace predates the tested commit",
            "build": f"{NA}: deploy metadata missing"
            if untrusted
            else (
                "fresh extraction (full builder: brief -> LLM -> spec)"
                if run["build_mode"] == "full-builder"
                else f"saved spec ({run['spec']}) rendered with --spec: no LLM extraction"
                if run["build_mode"] == "saved-spec"
                else run["build_mode"]
            ),
            "input_sha256_in_trace": sha.group(1)
            if sha
            else f"{NA}: no trace, or the trace predates input hashing",
            "spec_sha256_now": (sha256_12(spec_path) or NA)
            if spec_path
            else "not a saved-spec build (or deploy unknown)",
            "spec_note": (
                "the spec file was rewritten after this deploy; the hash above is the CURRENT file, not the deployed one"
                if spec_path.stat().st_mtime > deploy["created"]["ts"]
                else "the trace does not hash the spec; the file is unchanged since the deploy"
            )
            if spec_path and spec_path.exists()
            else None,
            "speech_style": case["style"],
            "speech_style_source": run["style_source"],
            "speech_style_in_call": f"{NA}: the call record does not carry the persona or its style",
            "flags": run["flags"],
        },
        "timestamps": {
            "last_simulation_id_of_run": run.get("simulation_id") or NA,
            "simulation_id_of_this_rep": run.get("simulation_id")
            if last_rep
            else f"{NA}: run_cases records only the last rep's simulation id",
            "run_start_estimate": run["start"],
            "run_start_note": "a LATE bound for the whole run (end minus run_cases' measured simulation seconds; setup, ledger reads and gaps between reps are excluded)",
            "run_end": run["end"],
            "run_end_source": run["end_source"]
            + " (written after run_cases collected all verdicts and ledgers)",
            "call_created": call.get("createdAt", NA) if call else f"{NA}: needs a raw call dump",
            "call_started": call.get("startedAt", NA) if call else f"{NA}: needs a raw call dump",
            "call_ended": call.get("endedAt", NA) if call else f"{NA}: needs a raw call dump",
            "call_record_updated": call.get("updatedAt", NA)
            if call
            else f"{NA}: needs a raw call dump",
            "verdict_arrival": f"{NA}: not recorded; Freya does not label when the judge verdict was written (call_record_updated is only the last update of the call record)",
        },
        "human_notes": D.score_log_rows(run_id) or f"{NA}: no Score log row cites this run file",
        "artifacts": [
            x
            for x in (
                run_id,
                run_id.removesuffix(".json") + ".log"
                if (D.ROOT / (run_id.removesuffix(".json") + ".log")).exists()
                else None,
                run.get("deploy_log"),
                D.rel(dump_path) if dump_path else None,
                D.rel(txt_path) if txt_path else None,
            )
            if x
        ],
    }


# ---------------------------------------------------------------- index of failed reps


def index(runs: list[dict], incomplete: list[dict]) -> dict:
    calls, txts = D.call_index(), txt_index()
    groups = {"completed_official": [], "completed_not_official": []}
    for r in runs:
        group = "completed_official" if r["official_style"] else "completed_not_official"
        for c in r["cases"]:
            for f in c["failures"]:
                groups[group].append(
                    {
                        "run": r["id"],
                        "end": r["end"],
                        "panel": r["panel"],
                        "case": c["id"],
                        "family": c["family"],
                        "rep": f["rep"],
                        "style": c["style"],
                        "style_source": r["style_source"],
                        "category": f["category"],
                        "commit": r["commit"],
                        "version": r["version"],
                        "build_mode": r["build_mode"],
                        "call_id": f["call_id"],
                        "raw_call": f["call_id"] in calls,
                        "formatted_transcript": f["call_id"] in txts,
                    }
                )
    for g in groups.values():
        g.sort(key=lambda x: x["end"] or "", reverse=True)
    return {
        "endpoint": "GET /api/failure-detail?run=<run id>&case=<case id>&rep=<n>",
        "completed_official": groups["completed_official"],
        "completed_not_official": groups["completed_not_official"],
        "incomplete_runs": incomplete,
        "note": "Incomplete runs have no result JSON and are listed separately (their console log may hold partial per-rep lines); "
        "official-style = complete, full case set, 3+ reps.",
        "coverage": {
            "failed_reps": sum(len(g) for g in groups.values()),
            "with_raw_call_dump": sum(x["raw_call"] for g in groups.values() for x in g),
            "with_formatted_transcript_only": sum(
                (not x["raw_call"]) and x["formatted_transcript"]
                for g in groups.values()
                for x in g
            ),
        },
    }
