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
