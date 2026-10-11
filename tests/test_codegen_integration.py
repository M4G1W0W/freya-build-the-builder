"""Integration fixes found by the reviewers: sticky promise flag; weekend attempt-1 date."""

import copy
import json
from pathlib import Path

from freya_builder import codegen, hooks

ROOT = Path(__file__).resolve().parents[1]
SPEC_A = json.loads((ROOT / "tests" / "fixtures" / "spec_a.json").read_text())


def test_promise_post_sets_sticky_flag_and_finalize_honours_it():
    src = hooks.promise_post(SPEC_A, 1)
    vs = {}
    env = {"vars": vs, "result": {"status": "success", "status_code": 200, "data": {"ok": True}}}
    exec(src, env)
    assert vs.get("p1_recorded") == "yes"
    # later duplicate fails and overwrites the flattened response
    fin = {
        "end_event": "promise",
        "p1_id": "p1",
        "p1_recorded": "yes",
        "create_promise_p1_response.data.ok": "false",
        "create_promise_p1_response.status": "success",
        "create_promise_p1_response.status_code": "200",
    }
    exec(codegen.finalize_source(SPEC_A), {"vars": fin})
    assert fin["close_outcome"] == "promise"


def test_post_hook_without_vars_does_not_crash():
    src = hooks.promise_post(SPEC_A, 1)
    result = {"status": "success", "status_code": 200, "data": {"ok": True}}
    exec(src, {"result": result})
    assert "Recorded" in result["data"]["what_to_do_next"]


def test_attempt1_on_weekend_is_not_in_the_past():
    spec = copy.deepcopy(SPEC_A)
    vs = {
        "now": "2026-10-17T11:00",
        "load_account_response.data.ok": "true",
        "load_account_response.data.products.0.product_id": "p1",
        "load_account_response.data.products.0.type": "personal_loan",
        "load_account_response.data.products.0.past_due": "540",
        "load_account_response.data.products.0.days_late": "5",
        "load_account_response.data.products.0.instalment_amount": "180",
    }
    exec(codegen.account_source(spec), {"vars": vs})
    facts = vs["account_facts"]
    assert "2026-10-23" in facts  # Friday of the following week
    assert "already past" not in facts


def _account(spec, now, product):
    vs = {"now": now, "load_account_response.data.ok": "true"}
    for key, value in product.items():
        vs[f"load_account_response.data.products.0.{key}"] = value
    exec(codegen.account_source(spec), {"vars": vs})
    return vs["account_facts"]


LOAN_5 = {
    "product_id": "p1",
    "type": "personal_loan",
    "past_due": "540",
    "days_late": "5",
    "instalment_amount": "180",
}


def test_named_date_lines_apply_holiday_and_deadline_rules():
    facts = _account(SPEC_A, "2026-10-14T11:00", LOAN_5)
    assert "IF THE CUSTOMER NAMES A DATE" in facts
    assert (
        "2026-10-26 (Monday 26 October 2026): not a business day (holiday); offer 2026-10-27"
        in facts
    )
    assert (
        "2026-10-17 (Saturday 17 October 2026): not a business day (weekend); offer 2026-10-19"
        in facts
    )
    assert (
        "a date after 2026-11-02 (Monday 2 November 2026): say the latest date you can record is 2026-11-02"
        in facts
    )


def test_named_date_lines_previous_business_day_mode():
    spec = copy.deepcopy(SPEC_A)
    spec["promise_window"]["non_business_day"] = "previous_business_day"
    facts = _account(spec, "2026-10-14T11:00", LOAN_5)
    assert (
        "2026-10-26 (Monday 26 October 2026): not a business day (holiday); offer 2026-10-23"
        in facts
    )


def test_opening_line_never_says_recorded():
    from freya_builder.render import opening_line

    spec = copy.deepcopy(SPEC_A)
    spec["opening"]["line"] = (
        "Hi, this call is recorded. Am I speaking with {{title}} {{last_name}}?"
    )
    assert (
        opening_line(spec)
        == "Hi, we are recording this call. Am I speaking with {{title}} {{last_name}}?"
    )


def test_facts_state_when_offers_must_stop():
    facts = _account(SPEC_A, "2026-10-14T11:00", LOAN_5)
    assert (
        "after attempt 1 is refused: NO further offer for this product (not even the floor)"
        in facts
    )


def test_attempt_1_line_names_the_floor_and_its_date_with_a_too_much_line():
    # 676e9df styled PUB-06: the floor was offered "today", then again on attempt 1's date. The
    # attempt-1 line says the floor and the date, and the negotiate ATTEMPTS line says a floor offer
    # after "too much" is attempt 1 on attempt 1's date. G1 (cand-g1) restores a separate "IF THE
    # CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH" line that names the floor and attempt 1's date
    # (F1 removed the older version of it; without it F1-F3 offered the floor "today" on PUB-06).
    card = {
        "product_id": "p1",
        "type": "credit_card",
        "card_last4": "1903",
        "past_due": "2125.1",
        "days_late": "12",
        "minimum_payment": "637.5",
    }
    facts = _account(SPEC_A, "2026-10-14T11:00", card)
    line = next(x for x in facts.splitlines() if x.startswith("- attempt 1, on "))
    assert "2026-10-16 (Friday 16 October 2026)" in line and "the floor 637.50" in line
    too = next(x for x in facts.splitlines() if "SAYS THE FULL AMOUNT IS TOO MUCH" in x)
    assert "exactly the floor 637.50 on 2026-10-16" in too and "this IS attempt 1" in too
    # F1 styled PUB-06 r2, r3 (15bcbad): without that line the floor was offered "today" again.
    # The rule now sits in the two lines that already carry attempt 1's date.
    assert "either amount only on this date (not today, unless today is this date)" in line
    plan = next(x for x in facts.splitlines() if x.startswith("OFFER PLAN"))
    assert '1) 2125.10 (or floor 637.50 after "too much") on 2026-10-16' in plan


def test_full_or_floor_without_a_floor_offers_the_full_amount_only():
    spec = copy.deepcopy(SPEC_A)
    for t in spec["products"]["types"]:
        t["floor_field"], t["floor_percent"] = "", 0
    facts = _account(spec, "2026-10-14T11:00", LOAN_5)
    assert "the floor not available" not in facts and "floor not available after" not in facts
    line = next(x for x in facts.splitlines() if x.startswith("- attempt 1, on "))
    assert line.endswith(": the full past-due amount 540.00")


def test_finalize_counts_the_notes_added_in_code():
    # P2 was noted 'paid' by the model; the refused ending then noted P1 in code. Counting only the
    # model's note, every note would be 'paid' and the call would close as paid.
    spec = copy.deepcopy(SPEC_A)
    spec["notes"]["used"] = True
    vs = {
        "end_event": "no_promise_refused",
        "autonote_reason": "refused",
        "p1_id": "p1",
        "p2_id": "p2",
        "p3_id": "none",
        "an_1_response.data.ok": "true",
        "add_note_p2_response.data.ok": "true",
        "add_note_p2_args.arg_reason": "paid",
    }
    exec(codegen.finalize_source(spec), {"vars": vs})
    assert (vs["close_outcome"], vs.get("close_reason")) == ("no_promise", "refused")


CARD_12 = {
    "product_id": "p1",
    "type": "credit_card",
    "card_last4": "1903",
    "past_due": "2125.1",
    "days_late": "12",
    "minimum_payment": "637.5",
}


def _too_much(offer, date_expr):
    spec = copy.deepcopy(SPEC_A)
    spec["too_much"] = {"offer": offer, "date_expr": date_expr}
    return spec


def _too_much_line(facts):
    return next(x for x in facts.splitlines() if "SAYS THE FULL AMOUNT IS TOO MUCH" in x)


def test_too_much_separate_offer_has_its_own_date_and_is_not_an_attempt():
    # Engine-fixes item 2 (rehearsal P2): "too much -> the floor on the next business day; this
    # offer is not a persuasion attempt". It got attempt 1's date and used up attempt 1.
    facts = _account(_too_much("separate", "next_business_day(today)"), "2026-10-14T11:00", CARD_12)
    too = _too_much_line(facts)
    assert too.startswith(
        "- IF THE CUSTOMER SAYS THE FULL AMOUNT IS TOO MUCH before your first offer: offer exactly "
        "the floor 637.50 on 2026-10-15 (Thursday 15 October 2026), once; this offer is NOT a "
        "persuasion attempt"
    )
    assert "IS attempt 1" not in facts
    attempt_1 = next(x for x in facts.splitlines() if x.startswith("- attempt 1, on "))
    assert "2026-10-16 (Friday 16 October 2026)" in attempt_1
    plan = next(x for x in facts.splitlines() if x.startswith("OFFER PLAN"))
    assert plan.endswith(
        '(after "too much": first the floor 637.50 on 2026-10-15, not one of these offers).'
    )


def test_too_much_separate_without_a_date_uses_attempt_1_date():
    too = _too_much_line(_account(_too_much("separate", ""), "2026-10-14T11:00", CARD_12))
    assert "exactly the floor 637.50 on 2026-10-16 (Friday 16 October 2026), once" in too
    assert "NOT a persuasion attempt" in too


def test_too_much_attempt_1_and_a_spec_without_the_field_render_as_before():
    old = copy.deepcopy(SPEC_A)
    del old["too_much"]
    same = _too_much("attempt_1", "next_business_day(today)")
    for spec in (old, same):
        assert codegen.account_source(spec) == codegen.account_source(SPEC_A)
        assert codegen.setup_source(spec) == codegen.setup_source(SPEC_A)
    assert "this IS attempt 1" in _too_much_line(_account(old, "2026-10-14T11:00", CARD_12))


def test_too_much_separate_review_fixes():
    # Review of cand-eng.3 (items 2/4): on Thu 15 Oct the next business day is attempt 1's date,
    # a past date gets the same mark as an attempt, and a transfer band gets no offer line.
    spec = _too_much("separate", "next_business_day(today)")
    too = _too_much_line(_account(spec, "2026-10-15T11:00", CARD_12))
    assert "on 2026-10-16 (Friday 16 October 2026), once" in too
    assert too.endswith(
        "; attempt 1 below offers the same floor on the same date: if the customer refused this "
        "offer, follow the brief's rules on refused offers for attempt 1"
    )
    assert "attempt 1 below" not in _too_much_line(_account(spec, "2026-10-14T11:00", CARD_12))
    past = _too_much("separate", "add_days(today, -1)")
    assert "(already past: not a valid promise date), once" in _too_much_line(
        _account(past, "2026-10-14T11:00", CARD_12)
    )
    xfer = copy.deepcopy(spec)
    xfer["bands"][1]["transfer_row"] = xfer["default_rows"]["negotiate"]
    facts = _account(xfer, "2026-10-14T11:00", CARD_12)
    assert "SAYS THE FULL AMOUNT IS TOO MUCH" not in facts and "first the floor" not in facts


def test_too_much_separate_date_is_checked_like_an_attempt_date():
    from freya_builder.datecheck import check_dates
    from freya_builder.spec import check_spec
    from freya_builder.toolapi import load_tool_api

    tools = load_tool_api(ROOT / "kit" / "tools" / "openapi.json")
    assert check_dates(_too_much("separate", "next_business_day(today)")) == []
    past = check_dates(_too_much("separate", "add_days(today, -1)"))
    assert past and all("the too-much offer of band" in x for x in past)
    assert any(
        x.startswith("too_much.offer is 'separate' but date_expr is empty")
        for x in check_spec(_too_much("separate", ""), tools)
    )
