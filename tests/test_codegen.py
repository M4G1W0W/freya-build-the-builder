"""Code-node sources (codegen.py + sandbox/facts.py + sandbox/policy_helpers.py).

Every scenario runs the EXACT generated source with exec, as the engine does. How the engine execs
a snippet is not documented, so the sources are also run with separate globals and locals, and
wrapped in a function. Brief A values (spec_a.json, public practice cases at
now = 2026-10-14T11:00) are TEST DATA ONLY. The mutated spec checks generality against an
independent reference calendar written here.
"""

import copy
import datetime as dt
import json
import re
import textwrap
from pathlib import Path

import pytest

from freya_builder import codegen
from freya_builder.expr import FUNCS
from freya_builder.sandbox import CLOSE, OPEN, assemble
from freya_builder.sandbox import policy_helpers as ph

FIXTURE = Path(__file__).parent / "fixtures" / "spec_a.json"
NOW = "2026-10-14T11:00"


def spec_a() -> dict:
    return json.loads(FIXTURE.read_text())


def spec_multi() -> dict:
    """Spec A with up to three products and notes (Brief B shape)."""
    spec = spec_a()
    spec["meta"]["max_products"] = 3
    spec["notes"]["used"] = True
    return spec


MODES = ["one_dict", "separate_locals", "function"]


def run(source: str, vs: dict, mode: str = "one_dict") -> dict:
    """exec one code-node source on the variable table `vs`, the way `mode` says."""
    if mode == "function":
        wrapped = "def _node(vars):\n" + textwrap.indent(source, "    ") + "\n_node(VS)\n"
        exec(compile(wrapped, "code_node", "exec"), {"VS": vs})
    elif mode == "separate_locals":
        exec(compile(source, "code_node", "exec"), {"vars": vs}, {})
    else:
        exec(compile(source, "code_node", "exec"), {"vars": vs})
    return vs


def flat_account(products: list[dict], node: str = "load_account") -> dict:
    """get_account result as the platform flattens it: every value a string."""
    vs = {
        f"{node}_response.status": "success",
        f"{node}_response.status_code": "200",
        f"{node}_response.data.ok": "true",
    }
    for i, product in enumerate(products):
        for key, value in product.items():
            if isinstance(value, float) and value == int(value):
                value = int(value)
            vs[f"{node}_response.data.products.{i}.{key}"] = str(value)
    return vs


def call(spec: dict, products: list[dict], now: str = NOW, mode: str = "one_dict") -> dict:
    """setup -> load_account result -> account_facts, on one variable table."""
    vs = {"customer_id": "c_test", "now": now}
    run(codegen.setup_source(spec), vs, mode)
    vs.update(flat_account(products))
    return run(codegen.account_source(spec), vs, mode)


def block(facts: str, slot: str) -> str:
    return next(b for b in facts.split("\n\n") if b.startswith(slot + " = "))


def table_line(table: str, iso: str) -> str:
    """The compact calendar's entry for a date: its non-business-day entry, or 'business day'.
    Fails if the date is outside the covered range."""
    end = re.search(r"from today to (\d{4}-\d{2}-\d{2})", table).group(1)
    today = re.search(r"today is \w{3} (\d{4}-\d{2}-\d{2})", table).group(1)
    assert today <= iso <= end, (iso, today, end)
    for entry in table.splitlines()[2].split("; "):
        if entry[4:14] == iso:
            return entry
    return iso + ": business day"


def relative(table: str, name: str) -> str:
    """'next Friday' / 'this Friday' / 'tomorrow' / 'end of this month' -> ISO date."""
    lines = table.splitlines()
    if name in ("tomorrow", "end of this month"):
        line = next(x for x in lines if x.startswith(name + " = "))
        return line.split(" = ", 1)[1][4:14]
    which, day = name.split(" ", 1)
    line = next(x for x in lines if x.startswith(which + " <weekday>"))
    return next(e for e in line.split(": ", 1)[1].split(", ") if e.startswith(day[:3]))[4:14]


CARD = {
    "product_id": "p1",
    "type": "credit_card",
    "card_last4": "4821",
    "past_due": 420.0,
    "days_late": 6,
    "minimum_payment": 126.0,
}
CAR = {
    "product_id": "p1",
    "type": "car_loan",
    "past_due": 1250.0,
    "days_late": 14,
    "instalment_amount": 400.0,
}

# ---------------------------------------------------------------- helper vocabulary


@pytest.fixture
def brief_a_calendar():
    ph.set_calendar([0, 1, 2, 3, 4], spec_a()["calendar"]["holidays"])
    yield
    ph.set_calendar([], [])


def test_vocabulary_covers_expr_whitelist():
    for name in FUNCS - {"min", "max"}:
        assert callable(getattr(ph, name)), name


def test_helpers(brief_a_calendar):
    wed = dt.date(2026, 10, 14)
    assert ph.add_business_days(wed, 12) == dt.date(2026, 11, 2)
    assert ph.add_business_days(wed, 7) == dt.date(2026, 10, 23)
    assert ph.add_business_days(wed, 0) == wed
    assert ph.add_business_days(dt.date(2026, 10, 27), -1) == dt.date(2026, 10, 23)
    assert ph.next_business_day(dt.date(2026, 10, 23)) == dt.date(2026, 10, 27)
    assert ph.business_day_on_or_after(dt.date(2026, 10, 26)) == dt.date(2026, 10, 27)
    assert ph.business_day_on_or_before(dt.date(2026, 10, 26)) == dt.date(2026, 10, 23)
    assert ph.business_day_on_or_after(wed) == wed
    assert ph.last_business_day_of_week(wed) == dt.date(2026, 10, 16)
    assert ph.last_business_day_of_week(dt.date(2026, 12, 23)) == dt.date(2026, 12, 24)
    assert ph.end_of_month(dt.date(2026, 12, 5)) == dt.date(2026, 12, 31)
    assert ph.end_of_month(dt.date(2026, 2, 5)) == dt.date(2026, 2, 28)
    assert ph.last_business_day_of_month(wed) == dt.date(2026, 10, 30)
    assert ph.weekday_in_week(wed, 4, 1) == dt.date(2026, 10, 23)
    assert ph.is_business_day(dt.date(2026, 10, 26)) is False
    assert ph.date(2026, 10, 14) == wed
    assert ph.add_days(dt.datetime(2026, 10, 14, 11, 0), 2) == dt.date(2026, 10, 16)
    assert ph.add_business_days("2026-10-14", 7) == dt.date(2026, 10, 23)  # ISO text is a date


def test_helpers_give_up_without_workdays():
    ph.set_calendar([], [])
    assert ph.add_business_days(dt.date(2026, 10, 14), 3) is None
    assert ph.last_business_day_of_week(dt.date(2026, 10, 14)) is None


def test_calendar_core_still_works_after_shadowing():
    main = (
        "try:\n"
        "    day = datetime.date(2026, 10, 14)\n"
        "    vars['a'] = nth_business_day_after(day, 7, set([0, 1, 2, 3, 4]), set()).isoformat()\n"
        "    vars['b'] = next_business_day_on_or_after(datetime.date(2026, 10, 17), set([0, 1, 2, 3, 4]), set()).isoformat()\n"
        "except Exception as e:\n"
        "    vars['a'] = str(e)\n"
    )
    vs = run(assemble(codegen.MODULES, main, {}), {})
    assert vs["a"] == "2026-10-23" and vs["b"] == "2026-10-19"


# ---------------------------------------------------------------- source hygiene


def all_sources(spec: dict) -> list[str]:
    events = [r["id"] for r in spec["rows"]] + ["done", "cap_negotiate"]
    return [
        codegen.setup_source(spec),
        codegen.account_source(spec),
        codegen.finalize_source(spec),
    ] + [codegen.exit_source(e) for e in events]


@pytest.mark.parametrize("make", [spec_a, spec_multi])
def test_sources_compile_without_braces_and_stay_small(make):
    for source in all_sources(make()):
        assert OPEN not in source and CLOSE not in source
        compile(source, "code_node", "exec")
        assert len(source.encode()) < 40_000
        assert "eval(" not in source


def test_bad_expression_fails_the_build():
    spec = spec_a()
    spec["bands"][0]["deadline_expr"] = "__import__('os').system('x')"
    with pytest.raises(ValueError, match="band early deadline"):
        codegen.setup_source(spec)


@pytest.mark.parametrize("mode", MODES)
def test_nodes_never_raise_on_empty_vars(mode):
    spec = spec_multi()
    for make, config in [
        (codegen.setup_source, codegen.setup_config(spec)),
        (codegen.account_source, codegen.account_config(spec)),
        (codegen.finalize_source, codegen.finalize_config(spec)),
    ]:
        vs = run(make(spec), {}, mode)
        assert set(config["defaults"]) <= set(vs)
        if make is not codegen.finalize_source:
            assert "close_reason" not in vs
    # finalize with no event and no account falls back to the opening default row.
    assert (vs["close_outcome"], vs["close_reason"]) == ("not_reached", "unclear")


# ---------------------------------------------------------------- setup


@pytest.mark.parametrize("mode", MODES)
def test_setup_on_brief_a(mode):
    vs = run(codegen.setup_source(spec_a()), {"now": NOW}, mode)
    assert vs["today_iso"] == "2026-10-14"
    assert vs["today_facts"].startswith("Today is Wednesday 14 October 2026 (2026-10-14), 11:00.")
    assert vs["end_event"] == "none" and vs["xfer_queue"] == "none"
    assert vs["close_outcome"] == "not_reached"  # outcome of default_rows.opening
    assert vs["account_facts"] == "(not loaded)" and vs["disclosure_text"] == ""
    assert vs["product_count"] == "0" and vs["p1_id"] == "none"
    assert vs["finalize_debug"] == "" and vs["setup_debug"] == ""
    assert "close_reason" not in vs

    table = vs["date_table"]
    assert table.startswith("CALENDAR: today is Wed 2026-10-14.")
    assert table_line(table, "2026-10-14").endswith("business day")
    assert "-> 2026-10-27" in table_line(table, "2026-10-26")
    assert "holiday" in table_line(table, "2026-10-26")
    assert table_line(table, "2026-11-02").endswith("business day")
    table_line(table, "2026-11-16")  # max deadline (2 Nov) + 14 days is covered
    assert relative(table, "next Friday") == "2026-10-23"  # following_week
    assert relative(table, "this Friday") == "2026-10-16"
    assert relative(table, "tomorrow") == "2026-10-15"
    assert relative(table, "end of this month") == "2026-10-31"

    slots = vs["callback_slots"].splitlines()
    assert (
        slots[1] == "- 2026-10-14 (Wednesday 14 October 2026): later than 11:00 (now), until 19:00"
    )
    assert slots[2] == "- 2026-10-15 (Thursday 15 October 2026): from 10:00 to 19:00"
    assert len(slots) == 3


def test_callback_before_the_window_opens_and_after_it_closes():
    early = run(codegen.setup_source(spec_a()), {"now": "2026-10-14T08:30"})["callback_slots"]
    assert "2026-10-14 (Wednesday 14 October 2026): from 10:00 to 19:00" in early
    late = run(codegen.setup_source(spec_a()), {"now": "2026-10-14T19:00"})["callback_slots"]
    assert "2026-10-14 (Wednesday 14 October 2026): no time left today" in late


@pytest.mark.parametrize(
    "now, business",
    [
        ("2026-10-17T11:00", False),  # Saturday
        ("2026-10-26T09:15", False),  # holiday
        ("2026-10-30T18:30", True),  # month end (Friday)
        ("2026-12-31T10:00", True),  # year end
        ("garbage", None),  # unreadable: the server clock is used, nothing raises
    ],
)
def test_setup_on_awkward_days(now, business):
    vs = run(codegen.setup_source(spec_a()), {"now": now})
    assert vs["date_table"].startswith("CALENDAR")
    assert vs["callback_slots"].startswith("CALLBACK SLOTS")
    if business is None:
        assert vs["setup_debug"] == "now unreadable; server clock used"
    else:
        assert vs["today_iso"] == now[:10]
        assert ("not a business day" in vs["today_facts"]) is (not business)


# ---------------------------------------------------------------- account_facts


@pytest.mark.parametrize("mode", MODES)
def test_account_early_band_single_product(mode):
    vs = call(spec_a(), [CARD], mode=mode)
    assert vs["account_status"] == "ok" and vs["product_count"] == "1" and vs["p1_id"] == "p1"
    p1 = block(vs["account_facts"], "P1")
    assert p1.startswith("P1 = credit card ending 4821 (product_id p1)")
    assert "past due: 420.00; days late: 6; band: early" in p1
    assert "- deadline: 2026-11-02 (Monday 2 November 2026)" in p1
    assert "- floor (minimum_payment): 126.00" in p1
    assert re.search(
        r"attempt 1, on 2026-10-16 \(Friday.*full past-due amount 420\.00.*floor 126\.00", p1
    )
    assert "attempt 2" not in p1
    assert "to 2026-11-02 (Monday 2 November 2026), both included" in p1
    assert "create_promise_p1" in p1 and "add_note_p1" not in p1
    assert vs["disclosure_text"] == (
        "I am calling from the collections team about a late payment. Your credit card ending "
        "4821 is 420 past due, 6 days late. Can you make this payment today?"
    )


def test_account_late_band_second_attempt_on_deadline():
    # PUB-04: car loan 1250, 14 days late, instalment 400.
    p1 = block(call(spec_a(), [CAR])["account_facts"], "P1")
    assert "band: late" in p1
    assert "- deadline: 2026-10-23 (Friday 23 October 2026)" in p1
    assert re.search(r"attempt 1, on 2026-10-16 .*1250\.00", p1)
    assert re.search(
        r"attempt 2, on 2026-10-23 \(Friday 23 October 2026\): the floor 400\.00$", p1, re.M
    )


def test_grid_invariants_over_eight_weeks():
    """T5-style grid: every day x 3 times x 1-3 products; deadlines are business days >= today."""
    spec = spec_multi()
    ref = RefCalendar([0, 1, 2, 3, 4], spec["calendar"]["holidays"])
    loan = {"product_id": "p2", "type": "personal_loan", "past_due": 310.5, "days_late": 45}
    products = [CARD, dict(loan, instalment_amount=103.5), dict(CAR, product_id="p3", days_late=8)]
    start = dt.date(2026, 10, 12)
    for offset in range(56):
        day = start + dt.timedelta(days=offset)
        for time in ("09:00", "11:00", "18:30"):
            count = 1 + offset % 3
            vs = call(spec, products[:count], now=f"{day.isoformat()}T{time}")
            assert vs["account_status"] == "ok" and vs["product_count"] == str(count)
            assert vs["setup_debug"] == "" and vs["account_debug"] == ""
            deadlines = re.findall(r"^- deadline: (\S+)", vs["account_facts"], re.M)
            assert len(deadlines) == count
            for iso in deadlines:
                deadline = dt.date.fromisoformat(iso)
                assert deadline >= day and ref.ok(deadline)
                table_line(vs["date_table"], iso)
            for iso, rest in re.findall(r"^- attempt \d, on (\S+)(.*)$", vs["account_facts"], re.M):
                assert ref.ok(dt.date.fromisoformat(iso))
                # A past date from a spec expression is never shown as a valid offer.
                assert iso >= day.isoformat() or "(already past: not a valid promise date)" in rest


def test_past_attempt_date_is_flagged():
    # A spec expression that yields a past date is labelled, never offered silently.
    spec = spec_a()
    spec["attempts"][0]["date_expr"] = "add_days(today, -1)"
    p1 = block(call(spec, [CAR], now="2026-10-14T11:00")["account_facts"], "P1")
    assert "attempt 1, on 2026-10-13 (Tuesday 13 October 2026) (already past" in p1


def test_attempt1_on_saturday_is_next_weeks_friday():
    p1 = block(call(spec_a(), [CAR], now="2026-10-17T11:00")["account_facts"], "P1")
    assert "attempt 1, on 2026-10-23" in p1 and "already past" not in p1


def test_account_keeps_leading_zeros_and_decimal_amounts():
    card = dict(CARD, card_last4="0377", past_due=2125.1, minimum_payment=637.5)
    vs = call(spec_a(), [card])
    assert "credit card ending 0377" in vs["account_facts"]
    assert "past due: 2125.10" in vs["account_facts"] and "637.50" in vs["account_facts"]
    assert "ending 0377 is 2125.10 past due" in vs["disclosure_text"]


def test_account_on_the_last_business_day_of_the_week():
    # Attempt 1 rule: if today is that day, the last business day of next week.
    p1 = block(call(spec_a(), [CAR], now="2026-10-16T11:00")["account_facts"], "P1")
    assert "attempt 1, on 2026-10-23" in p1


def test_account_multi_product_deadlines_per_product():
    # PUB-13 shape: credit card 300, 4 days late; personal loan 900, 20 days late.
    products = [
        dict(CARD, card_last4="6604", past_due=300.0, days_late=4, minimum_payment=90.0),
        {
            "product_id": "p2",
            "type": "personal_loan",
            "past_due": 900.0,
            "days_late": 20,
            "instalment_amount": 300.0,
        },
    ]
    vs = call(spec_multi(), products)
    assert (vs["p1_id"], vs["p2_id"], vs["p3_id"], vs["product_count"]) == ("p1", "p2", "none", "2")
    facts = vs["account_facts"]
    assert "- deadline: 2026-11-02" in block(facts, "P1")
    assert "- deadline: 2026-10-23" in block(facts, "P2")
    assert "attempt 2" not in block(facts, "P1") and "attempt 2" in block(facts, "P2")
    assert "add_note_p2" in block(facts, "P2")
    assert "Deadline per product: P1 2026-11-02" in facts and "P2 2026-10-23" in facts
    assert "P3: not in use (never call create_promise_p3 or add_note_p3)" in facts
    assert vs["disclosure_text"].endswith(
        "Your credit card ending 6604 is 300 past due, 4 days late. Your personal loan is 900 past "
        "due, 20 days late. Can you pay all of them today?"
    )


def test_account_more_products_than_slots():
    products = [dict(CARD, product_id=f"p{i}") for i in range(1, 5)]
    vs = call(spec_multi(), products)
    assert (vs["p3_id"], vs["product_count"]) == ("p3", "3")
    assert "The bank returned 4 products" in vs["account_facts"]


@pytest.mark.parametrize(
    "result",
    [
        {},  # the call failed: no data at all
        {"load_account_response.data.ok": "false", "load_account_failure_count": "2"},
        {"load_account_response.data.ok": "true"},  # ok but no products
    ],
)
def test_account_unavailable(result):
    vs = {"now": NOW}
    run(codegen.setup_source(spec_a()), vs)
    vs.update(result)
    run(codegen.account_source(spec_a()), vs)
    assert vs["account_status"] == "unavailable" and vs["product_count"] == "0"
    assert vs["account_facts"].startswith("ACCOUNT NOT AVAILABLE")
    assert "transition_to_ev_no_promise_refused" in vs["account_facts"]
    assert vs["p1_id"] == "none"


# ---------------------------------------------------------------- finalize


def finalize(spec: dict, extra: dict, product_count: int = 1) -> dict:
    vs = {"now": NOW}
    run(codegen.setup_source(spec), vs)
    for k in range(1, product_count + 1):
        vs[f"p{k}_id"] = f"p{k}"
    vs["account_status"] = "ok" if product_count else "not_loaded"
    vs.update(extra)
    return run(codegen.finalize_source(spec), vs)


def promise_ok(k: int, flag: object = "true") -> dict:
    return {
        f"create_promise_p{k}_response.status": "success",
        f"create_promise_p{k}_response.status_code": "200",
        f"create_promise_p{k}_response.data.ok": flag,
    }


def note(k: int, reason: str) -> dict:
    # The key the platform writes (seen in route_evaluated variable tables, 10 Oct 14:18 UTC):
    # <tool>_args.<ARG_PREFIX><field>. The earlier assumed key "<tool>_args.reason" never exists.
    return {
        f"add_note_p{k}_args.arg_reason": reason,
        f"add_note_p{k}_response.status": "success",
        f"add_note_p{k}_response.data.ok": "true",
    }


@pytest.mark.parametrize("flag", ["true", "True"])
def test_finalize_promise(flag):
    vs = finalize(spec_a(), {"end_event": "done", **promise_ok(1, flag)})
    assert (vs["close_outcome"], vs["xfer_queue"], vs["close_key"]) == (
        "promise",
        "none",
        "promise",
    )
    assert "close_reason" not in vs


def test_finalize_failed_promise_is_not_a_promise():
    failed = promise_ok(1, "false")
    vs = finalize(spec_a(), {"end_event": "no_promise_service_error", **failed})
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "service_error")
    # A 500 envelope without data is not a promise either.
    error = {
        "create_promise_p1_response.status": "error",
        "create_promise_p1_response.status_code": "500",
    }
    vs = finalize(spec_a(), {"end_event": "done", **error})
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "refused")


def test_finalize_event_paid():
    vs = finalize(spec_a(), {"end_event": "paid"})
    assert vs["close_outcome"] == "paid" and "close_reason" not in vs


def test_finalize_transfer_wins_over_a_recorded_promise():
    vs = finalize(spec_a(), {"end_event": "transferred_restructuring", **promise_ok(1)})
    assert (vs["close_outcome"], vs["close_reason"], vs["xfer_queue"]) == (
        "transferred",
        "restructuring",
        "restructuring",
    )


def test_finalize_done_with_nothing_recorded():
    vs = finalize(spec_a(), {"end_event": "done"})
    assert (vs["close_outcome"], vs["close_reason"], vs["xfer_queue"]) == (
        "no_promise",
        "refused",
        "none",
    )


@pytest.mark.parametrize(
    "event, outcome, reason",
    [
        ("cap_identity", "not_verified", "declined"),
        ("cap_opening", "not_reached", "unclear"),
        ("not_reached_callback", "not_reached", "callback"),
        ("not_verified_failed", "not_verified", "failed"),
    ],
)
def test_finalize_event_rows(event, outcome, reason):
    vs = finalize(spec_a(), {"end_event": event}, product_count=0)
    assert (vs["close_outcome"], vs["close_reason"], vs["xfer_queue"]) == (outcome, reason, "none")


def test_finalize_notes_all_paid():
    vs = finalize(spec_multi(), {"end_event": "done", **note(1, "paid"), **note(2, "paid")}, 2)
    assert vs["close_outcome"] == "paid" and "close_reason" not in vs


def test_finalize_first_note_not_paid():
    extra = {"end_event": "done", **note(1, "paid"), **note(2, "refused"), **note(3, "dispute")}
    vs = finalize(spec_multi(), extra, 3)
    assert (vs["close_outcome"], vs["close_reason"], vs["close_key"]) == (
        "no_promise",
        "refused",
        "no_promise_refused",
    )


def test_finalize_promise_beats_notes():
    # PUB-12 shape: one promise, two refused notes.
    extra = {"end_event": "done", **promise_ok(1), **note(2, "refused"), **note(3, "refused")}
    vs = finalize(spec_multi(), extra, 3)
    assert vs["close_outcome"] == "promise" and "close_reason" not in vs
    assert "promises=P1; notes=P2:refused,P3:refused" in vs["finalize_debug"]


def test_finalize_ignores_unused_slots():
    vs = finalize(spec_multi(), {"end_event": "done", **promise_ok(2)}, product_count=1)
    assert vs["close_outcome"] == "no_promise"


# ---------------------------------------------------------------- generality


def mutated_spec() -> dict:
    """Other calendar, Mon-Thu business days, next_occurrence, a 3rd band with a transfer."""
    spec = spec_multi()
    spec["calendar"].update(
        business_weekdays=[0, 1, 2, 3],
        holidays=["2026-10-15", "2026-10-20", "2026-11-05"],
        next_weekday="next_occurrence",
    )
    spec["bands"] = [
        {"name": "b1", "min_days": 1, "max_days": 10, "deadline_expr": "add_business_days(today, 10)", "attempts": 1, "transfer_row": ""},
        {"name": "b2", "min_days": 11, "max_days": 60, "deadline_expr": "add_business_days(today, 5)", "attempts": 2, "transfer_row": ""},
        {"name": "b3", "min_days": 61, "max_days": 90, "deadline_expr": "min(add_business_days(today, 3), end_of_month(today))", "attempts": 0, "transfer_row": "transferred_support"},
    ]  # fmt: skip
    spec["attempts"] = [
        {"n": 1, "bands": [], "amount": "full", "date_expr": "next_business_day(today)", "note": ""},
        {"n": 2, "bands": ["b2"], "amount": "floor", "date_expr": "business_day_on_or_before(add_days(deadline, -1))", "note": ""},
    ]  # fmt: skip
    spec["callback"].update(
        day_exprs=[
            "today if is_business_day(today) else next_business_day(today)",
            "add_business_days(today, 2)",
        ],
        start="9:00",
        end="17:30",
    )
    return spec


class RefCalendar:
    """Independent reference for the mutated spec (plain loops, no sandbox code)."""

    def __init__(self, workdays, holidays):
        self.workdays, self.holidays = set(workdays), set(holidays)

    def ok(self, d):
        return d.weekday() in self.workdays and d.isoformat() not in self.holidays

    def nth_after(self, d, n):
        while n:
            d += dt.timedelta(days=1)
            n -= self.ok(d)
        return d

    def on_or_before(self, d):
        while not self.ok(d):
            d -= dt.timedelta(days=1)
        return d

    def on_or_after(self, d):
        while not self.ok(d):
            d += dt.timedelta(days=1)
        return d

    def last_of_week(self, d):
        return self.on_or_before(d + dt.timedelta(days=6 - d.weekday()))


def test_mutated_spec_dates():
    spec = mutated_spec()
    ref = RefCalendar([0, 1, 2, 3], ["2026-10-15", "2026-10-20", "2026-11-05"])
    today = dt.date(2026, 10, 14)
    products = [
        {"product_id": "x1", "type": "credit_card", "card_last4": "0042", "past_due": 100.0, "days_late": 3, "minimum_payment": 30.0},
        {"product_id": "x2", "type": "personal_loan", "past_due": 600.0, "days_late": 30, "instalment_amount": 200.0},
        {"product_id": "x3", "type": "car_loan", "past_due": 999.99, "days_late": 75, "instalment_amount": 333.33},
    ]  # fmt: skip
    vs = call(spec, products, now="2026-10-14T16:45")
    facts = vs["account_facts"]

    d1, d2 = ref.nth_after(today, 10), ref.nth_after(today, 5)
    d3 = min(ref.nth_after(today, 3), dt.date(2026, 10, 31))
    assert f"- deadline: {d1.isoformat()}" in block(facts, "P1")
    assert f"- deadline: {d2.isoformat()}" in block(facts, "P2")
    assert f"- deadline: {d3.isoformat()}" in block(facts, "P3")
    assert f"attempt 1, on {ref.nth_after(today, 1).isoformat()}" in block(facts, "P1")
    attempt2 = ref.on_or_before(d2 - dt.timedelta(days=1)).isoformat()
    assert re.search(f"attempt 2, on {attempt2} .*: the floor 200\\.00$", block(facts, "P2"), re.M)
    assert "attempt" not in block(facts, "P3").replace("persuasion attempts in this band: 0", "")
    assert "MANDATORY TRANSFER: end with transition_to_ev_transferred_support" in block(facts, "P3")
    assert "credit card ending 0042" in block(facts, "P1")

    table = vs["date_table"]
    assert table.startswith("CALENDAR") and "Business days: Mon, Tue, Wed, Thu," in table
    friday = table_line(table, "2026-10-16")
    # A Friday off is a non-working day, not a weekend (the model repeats these words).
    assert "non-working day" in friday and "weekend" not in friday
    assert "weekend" in table_line(table, "2026-10-17")
    assert f"-> {ref.on_or_after(dt.date(2026, 10, 16)).isoformat()}" in friday
    assert "holiday" in table_line(table, "2026-10-20")
    assert relative(table, "next Thursday") == "2026-10-15"  # next_occurrence, not 2026-10-22
    assert relative(table, "next Wednesday") == "2026-10-21"  # never today
    assert relative(table, "this Thursday") == "2026-10-15"
    table_line(table, (d1 + dt.timedelta(days=14)).isoformat())

    slots = vs["callback_slots"].splitlines()
    assert slots[1].startswith("- 2026-10-14 ") and slots[1].endswith(
        "later than 16:45 (now), until 17:30"
    )
    second = ref.nth_after(today, 2).isoformat()
    assert slots[2].startswith(f"- {second} ") and slots[2].endswith("from 09:00 to 17:30")


def test_mutated_spec_mandatory_transfer_closes_as_its_row():
    spec = mutated_spec()
    vs = finalize(spec, {"end_event": "transferred_support", **promise_ok(1)}, 3)
    assert (vs["close_outcome"], vs["close_reason"], vs["xfer_queue"]) == (
        "transferred",
        "support",
        "support",
    )


def test_spec_without_callback_or_notes():
    spec = copy.deepcopy(mutated_spec())
    spec["callback"]["enabled"] = False
    spec["callback"]["day_exprs"] = []
    vs = run(codegen.setup_source(spec), {"now": NOW})
    assert vs["callback_slots"] == "(no callback window in the brief)"


def test_exit_source_sets_end_event():
    for event in ("done", "cap_identity", "transferred_human"):
        assert run(codegen.exit_source(event), {"end_event": "none"})["end_event"] == event
    with pytest.raises(ValueError):
        codegen.exit_source("")


# ---------------------------------------------------------------- review regressions


@pytest.mark.parametrize("mode", MODES)
def test_calendar_is_seen_in_every_exec_mode(mode):
    # Regression: set_calendar rebound WORKDAYS with `global`. Run inside a function, the helpers
    # kept the empty calendar: every day "not a business day", every deadline "not available".
    vs = call(spec_a(), [CAR], mode=mode)
    assert "- deadline: 2026-10-23 (Friday 23 October 2026)" in block(vs["account_facts"], "P1")
    assert table_line(vs["date_table"], "2026-10-15").endswith(": business day")
    vs.update({"end_event": "done", **promise_ok(1)})
    assert run(codegen.finalize_source(spec_a()), vs, mode)["close_outcome"] == "promise"


def test_brief_a_dates_match_the_reference_calendar_day_by_day():
    """Every day from 1 Oct 2026 to 7 Feb 2027: weekends, holidays, month ends and the year end."""
    spec = spec_a()
    ref = RefCalendar([0, 1, 2, 3, 4], spec["calendar"]["holidays"])
    start = dt.date(2026, 10, 1)
    for offset in range(130):
        day = start + dt.timedelta(days=offset)
        for product, n in ((CARD, 12), (CAR, 7)):
            vs = call(spec, [product], now=f"{day.isoformat()}T11:00")
            p1 = block(vs["account_facts"], "P1")
            deadline = ref.nth_after(day, n)
            assert f"- deadline: {deadline.isoformat()}" in p1, day
            week_end = ref.last_of_week(day)
            first = week_end if week_end > day else ref.last_of_week(day + dt.timedelta(days=7))
            assert f"attempt 1, on {first.isoformat()}" in p1, day
            assert (f"attempt 2, on {deadline.isoformat()}" in p1) is (product is CAR), day
        slots = [line[2:12] for line in vs["callback_slots"].splitlines()[1:]]
        assert slots == sorted({day.isoformat(), ref.nth_after(day, 1).isoformat()}), day
        monday = day - dt.timedelta(days=day.weekday())
        next_friday = (monday + dt.timedelta(days=11)).isoformat()
        assert relative(vs["date_table"], "next Friday") == next_friday, day


@pytest.mark.parametrize(
    "now, order, iso, hm",
    [
        ("2026-10-14T11:00:00.000Z", "dmy", "2026-10-14", "11:00"),
        ("2026-10-14T11:00:00+02:00", "dmy", "2026-10-14", "11:00"),
        ("2026-10-14 9:05", "dmy", "2026-10-14", "09:05"),
        ("2026/10/14 11:00", "dmy", "2026-10-14", "11:00"),
        ("14/10/2026 11:00", "dmy", "2026-10-14", "11:00"),
        ("14.10.2026 18.30", "dmy", "2026-10-14", "18:30"),
        ("10/14/2026 2:30 pm", "mdy", "2026-10-14", "14:30"),
        ("Wednesday 14 October 2026, 11:00", "dmy", "2026-10-14", "11:00"),
        ("Oct 14, 2026 11:00 AM", "mdy", "2026-10-14", "11:00"),
        ("14th of October 2026 at 7pm", "dmy", "2026-10-14", "19:00"),
    ],
)
def test_now_in_other_formats(now, order, iso, hm):
    # Regression: every `now` but ISO with '-' fell back to the server clock: wrong dates.
    spec = spec_a()
    spec["calendar"]["numeric_date_order"] = order
    vs = run(codegen.setup_source(spec), {"now": now})
    assert vs["setup_debug"] == ""
    assert vs["today_iso"] == iso and f"({iso}), {hm}." in vs["today_facts"]


def test_templates_take_double_braces_and_call_variables():
    # Regression: '{{card_last4}}' left braces in the spoken text, and a call variable in the
    # intro (the customer's name) was never filled.
    spec = spec_a()
    spec["products"]["types"][0]["label"] = "credit card ending {{card_last4}}"
    spec["disclosure"]["product_sentence"] = (
        "Your {{ label }} is {past_due} past due, {{days_late}} days late."
    )
    spec["disclosure"]["intro"] = "{{title}} {last_name}, I am calling about a late payment."
    vs = {"now": NOW, "title": "Mr", "last_name": "Reyes"}
    run(codegen.setup_source(spec), vs)
    vs.update(flat_account([CARD]))
    run(codegen.account_source(spec), vs)
    assert vs["disclosure_text"] == (
        "Mr Reyes, I am calling about a late payment. Your credit card ending 4821 is 420 past "
        "due, 6 days late. Can you make this payment today?"
    )
    assert "{" not in vs["account_facts"] + vs["disclosure_text"]
    unavailable = {"now": NOW, "title": "Mr", "last_name": "Reyes"}
    run(codegen.setup_source(spec), unavailable)
    run(codegen.account_source(spec), unavailable)
    assert unavailable["disclosure_text"] == "Mr Reyes, I am calling about a late payment."


@pytest.mark.parametrize(
    "start, end, today_slot",
    [
        ("10am", "7pm", "later than 11:00 (now), until 19:00"),
        ("10.00", "19h30", "later than 11:00 (now), until 19:30"),
        ("9:30 a.m.", "12 pm", "later than 11:00 (now), until 12:00"),
    ],
)
def test_callback_window_in_other_time_formats(start, end, today_slot):
    # Regression: '7pm' was read as 07:00, which left no callback time at all.
    spec = spec_a()
    spec["callback"].update(start=start, end=end)
    slots = run(codegen.setup_source(spec), {"now": NOW})["callback_slots"].splitlines()
    assert slots[1].endswith(today_slot)


def test_valid_dates_are_bounded_by_business_days():
    # Regression: on a Saturday the window began "from 2026-10-17 (Saturday ...)".
    p1 = block(call(spec_a(), [CAR], now="2026-10-17T11:00")["account_facts"], "P1")
    assert "business days from 2026-10-19 (Monday 19 October 2026) to 2026-10-28" in p1
    spec = spec_a()
    spec["promise_window"]["max_expr"] = "add_days(today, 12)"  # 2026-10-26, a holiday
    p1 = block(call(spec, [CAR])["account_facts"], "P1")
    assert "to 2026-10-23 (Friday 23 October 2026), both included" in p1
    spec["promise_window"]["min_expr"] = "add_days(deadline, 1)"
    p1 = block(call(spec, [CAR])["account_facts"], "P1")
    assert "- valid promise dates: none" in p1


def test_expression_may_return_an_iso_date_string():
    spec = spec_a()
    spec["bands"][1]["deadline_expr"] = "'2026-10-22'"
    p1 = block(call(spec, [CAR])["account_facts"], "P1")
    assert "- deadline: 2026-10-22 (Thursday 22 October 2026)" in p1


def test_finalize_promise_exit_needs_a_recorded_promise():
    # Regression: the model's transition_to_ev_promise closed as promise with nothing recorded.
    vs = finalize(spec_a(), {"end_event": "promise", **promise_ok(1, "false")})
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "refused")
    vs = finalize(spec_a(), {"end_event": "promise"})
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "refused")
    vs = finalize(spec_a(), {"end_event": "promise", **promise_ok(1)})
    assert vs["close_outcome"] == "promise" and "close_reason" not in vs


@pytest.mark.parametrize(
    "flag, recorded",
    [
        ("true", True),
        ("True", True),
        (True, True),
        ("1", True),
        ("false", False),
        ("False", False),
        (False, False),
        ("0", False),
        (0, False),
    ],
)
def test_finalize_reads_every_form_of_the_ok_flag(flag, recorded):
    # Regression: '0' fell through to the HTTP envelope and counted as recorded.
    vs = finalize(spec_a(), {"end_event": "done", **promise_ok(1, flag)})
    assert (vs["close_outcome"] == "promise") is recorded


def test_finalize_envelope_without_an_ok_flag():
    base = {"end_event": "done", "create_promise_p1_response.status": "success"}
    vs = finalize(spec_a(), {**base, "create_promise_p1_response.status_code": "200.0"})
    assert vs["close_outcome"] == "promise"  # regression: '200.0' was not a status code
    error = {
        "create_promise_p1_response.status_code": 200,
        "create_promise_p1_response.data.error": "x",
    }
    assert finalize(spec_a(), {**base, **error})["close_outcome"] == "no_promise"


def test_finalize_note_reason_under_body_args():
    extra = {"end_event": "done", **note(1, "dispute")}
    extra["add_note_p1_args.body.reason"] = extra.pop("add_note_p1_args.arg_reason")
    vs = finalize(spec_multi(), extra, 1)
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "dispute")


def test_non_finite_numbers_do_not_break_a_product():
    card = dict(CARD, past_due="NaN", days_late="inf")
    p1 = block(call(spec_a(), [card])["account_facts"], "P1")
    assert "past due: not available; days late: None; band: none" in p1


def test_offer_plan_sets_the_attempt_counts_side_by_side():
    # PUB-12 at 90b737d and d46b807: correct per-product facts, yet the model copied the late-band
    # product's "full, then floor" onto the early-band car loan. The plan lists every product's
    # offers in one line, and the early band says ONE offer only.
    products = [
        dict(CARD, card_last4="6604", past_due=300.0, days_late=4, minimum_payment=90.0),
        {
            "product_id": "p2",
            "type": "personal_loan",
            "past_due": 900.0,
            "days_late": 20,
            "instalment_amount": 300.0,
        },
    ]
    facts = call(spec_multi(), products)["account_facts"]
    assert "- persuasion attempts in this band: 1 (ONE offer only)" in block(facts, "P1")
    plan = next(line for line in facts.splitlines() if line.startswith("OFFER PLAN"))
    assert "not even the floor" in plan
    assert "P1: 1 offer only: 1) 300.00 on 2026-10-16" in plan
    assert "P2: 2 offers: 1) 900.00 on 2026-10-16, 2) floor 300.00 on 2026-10-23" in plan


def test_finalize_wrap_up_default_ending_takes_the_note_reason():
    # PUB-05 on the A+B agent, 1bc0c1d rep 3: wrap_up ends through the default negotiate row and
    # finalize must take the outcome from the saved note. The reason sat under ..._args.arg_reason,
    # which finalize did not read, so the call closed as no_promise/refused instead of hardship.
    spec = spec_multi()
    extra = {"end_event": spec["default_rows"]["negotiate"], **note(1, "hardship")}
    vs = finalize(spec, extra, 1)
    assert (vs["close_outcome"], vs["close_reason"]) == ("no_promise", "hardship")


def test_account_marks_unused_slots_even_without_setup():
    # The notes-done route reads p<k>_id == 'none' for unused slots. setup writes that default, but
    # setup's sandbox run can fail (seen 10 Oct, 14:3x UTC); account_facts writes it too.
    vs = {"now": "2026-10-14T11:00", "load_account_response.data.ok": "true"}
    for key, value in CARD.items():
        vs[f"load_account_response.data.products.0.{key}"] = value
    exec(codegen.account_source(spec_multi()), {"vars": vs})
    assert vs["p1_id"] == "p1" and vs["p2_id"] == "none" and vs["p3_id"] == "none"


def test_floor_as_a_percentage_of_past_due():
    # audit F15: "the lowest acceptable amount is 30% of the past-due amount" had no representation.
    spec = spec_a()
    for t in spec["products"]["types"]:
        t["floor_field"], t["floor_percent"] = "", 30
    p1 = block(call(spec, [CARD])["account_facts"], "P1")
    assert "- floor (30% of past due): 126.00" in p1  # CARD: 420.00 past due
    assert "floor 126.00" in p1


@pytest.mark.parametrize("mode", MODES)
def test_date_table_stays_small(mode):
    # a8b70ea: the EVERY DAY weeks grew the table to 1920 chars, and a talkative call's
    # verify_identity post-hook then failed 40 times with "Sandbox did not return a parseable
    # result" (every sandbox run returns all variables; 6393c16 saw the same at 4.8 KB). Reverted.
    table = run(codegen.setup_source(spec_a()), {"now": NOW}, mode)["date_table"]
    assert len(table) < 1450 and "EVERY DAY" not in table


@pytest.mark.parametrize("mode", MODES)
def test_period_rows_list_their_days(mode):
    # a8b70ea styled PUB-07: after "the week after next", "Monday" became Monday 2 November (the
    # deadline) in every failed call; the row gave only "Mon 2026-10-26 to Sun 2026-11-01".
    table = run(codegen.setup_source(spec_a()), {"now": NOW}, mode)["date_table"]
    row = next(x for x in table.splitlines() if x.startswith("the week after next"))
    assert row.endswith(
        ": Mon 2026-10-26, Tue 2026-10-27, Wed 2026-10-28, Thu 2026-10-29, Fri 2026-10-30, "
        "Sat 2026-10-31, Sun 2026-11-01"
    )
    assert next(x for x in table.splitlines() if x.startswith("next week")).endswith(
        "Sun 2026-10-25"
    )
