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


def test_facts_say_exactly_when_and_what_the_floor_offer_is():
    # 676e9df styled PUB-06 (2 of 3 reps): after "the full amount is too much" the floor was
    # offered "today", then again on attempt 1's date, and the judge counted two floor offers.
    card = {
        "product_id": "p1",
        "type": "credit_card",
        "card_last4": "1903",
        "past_due": "2125.1",
        "days_late": "12",
        "minimum_payment": "637.5",
    }
    facts = _account(SPEC_A, "2026-10-14T11:00", card)
    line = next(x for x in facts.splitlines() if "SAYS THE FULL AMOUNT IS TOO MUCH" in x)
    assert "637.50 on 2026-10-16 (Friday 16 October 2026)" in line
    assert "this IS attempt 1" in line and "no other date" in line


def test_no_floor_line_without_a_floor():
    # Diff review 16: "offer exactly the floor not available on ..." for a product with no floor.
    spec = copy.deepcopy(SPEC_A)
    for t in spec["products"]["types"]:
        t["floor_field"], t["floor_percent"] = "", 0
    facts = _account(spec, "2026-10-14T11:00", LOAN_5)
    assert "SAYS THE FULL AMOUNT IS TOO MUCH" not in facts


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
