"""scripts/transcript_check.py: review flags on synthetic call records (no network, no runs/)."""

import json

from transcript_check import check_call, main

BANK = "https://freya-bank-mock.freyavoice.workers.dev/v1/"
NOW = "2026-10-14T11:00"
CARD = {"product_id": "p1", "type": "credit_card", "card_last4": "7740", "past_due": 365}


def _sys(t: float, event: dict) -> dict:
    return {"role": "system", "secondsFromStart": t, "message": json.dumps(event)}


def start(t: float, tool: str, body: dict, function: str = "api_call") -> dict:
    return _sys(t, {"event": "function_call_start", "function": function,
                    "args": {"url": BANK + tool, "method": "POST", "body": body}})  # fmt: skip


def done(t: float, data: dict, function: str = "api_call") -> dict:
    return _sys(t, {"event": "function_call_complete", "function": function,
                    "result": {"status": "success", "data": data}})  # fmt: skip


def say(t: float, text: str) -> dict:
    return {"role": "assistant", "secondsFromStart": t, "message": text}


def hear(t: float, text: str) -> dict:
    return {"role": "user", "secondsFromStart": t, "message": text}


def call(*messages: dict) -> dict:
    setup = _sys(0.0, {"event": "route_evaluated", "variable_table": {"now": NOW}})
    return {"id": "c1", "messages": [setup, *messages]}


def codes(c: dict, level: str | None = None) -> list[str]:
    return [f["code"] for f in check_call(c) if level is None or f["level"] == level]


def promise_call(readback: str, *between: dict) -> dict:
    return call(
        start(1.0, "get_account", {"customer_id": "c"}),
        done(1.1, {"ok": True, "products": [CARD]}),
        say(2.0, "Can you make this payment today?"),
        hear(3.0, "I will pay the full amount this Friday."),
        say(3.1, readback),
        *between,
        hear(5.0, "Yes, I confirm."),
        start(
            5.5,
            "create_promise",
            {"amount": 365, "date": "2026-10-16", "product_id": "p1"},
            function="create_promise_p1",
        ),  # fmt: skip
        done(5.6, {"ok": True}, function="create_promise_p1"),
        say(5.7, "You will receive a text message confirming this promise. Thank you and goodbye."),
        _sys(5.7, {"event": "tool_call_routing", "tool_name": "transition_to_ev_promise"}),
        start(6.0, "close_call", {"outcome": "promise", "customer_id": "c"}),
    )


def test_readback_without_the_product_is_flagged():
    c = promise_call(
        "Friday 16 October 2026 is a business day. Do you confirm you will pay 365.00?"
    )
    flags = [f for f in check_call(c) if f["code"] == "READBACK"]
    assert len(flags) == 1 and "product" in flags[0]["note"] and "date" not in flags[0]["note"]


def test_full_readback_and_a_filler_before_the_yes_are_not_flagged():
    full = "I will record a payment of 365.00 for your credit card ending 7740 on Friday 16 October 2026. Do you confirm?"
    assert codes(promise_call(full)) == []
    assert codes(promise_call(full, hear(4.0, "Well, I"), say(4.1, "Please go on."))) == []


def test_a_retry_after_a_failed_create_promise_is_one_readback():
    c = promise_call(
        "Friday 16 October 2026 is a business day. Do you confirm you will pay 365.00?"
    )
    c["messages"].insert(-4, start(5.58, "create_promise", {"amount": 365, "date": "2026-10-16",
                                                            "product_id": "p1"}))  # fmt: skip
    assert codes(c).count("READBACK") == 1


def test_create_promise_without_any_confirmation_question_is_flagged():
    c = promise_call("Friday 16 October 2026 is a business day.")
    assert any("no confirmation question" in f["evidence"] for f in check_call(c))


def test_a_wrong_weekday_is_flagged_and_a_right_one_is_not():
    bad = call(say(1.0, "Monday 27 October 2026 is a business day."))
    assert codes(bad) == ["WEEKDAY"]
    assert "Tuesday" in check_call(bad)[0]["note"]
    assert codes(call(say(1.0, "Tuesday 27 October 2026 is a business day."))) == []
    assert codes(call(say(1.0, "That would be Friday, October 17th."))) == ["WEEKDAY"]  # year: now
    assert codes(call(say(1.0, "I can offer Friday 16 October instead."))) == []


def _transfer(last_line: str | None) -> dict:
    lines = [say(2.0, last_line)] if last_line else []
    return call(
        say(1.0, "Can you make this payment today?"),
        hear(1.5, "I want lower instalments."),
        *lines,
        _sys(
            3.0,
            {
                "event": "tool_call_routing",
                "tool_name": "transition_to_ev_transferred_restructuring",
            },
        ),
        start(3.5, "transfer_to_agent", {"queue": "restructuring"}),
        start(3.6, "close_call", {"outcome": "transferred", "reason": "restructuring"}),
    )


def test_a_transfer_without_thanks_and_goodbye_is_flagged():
    flags = check_call(_transfer("I can connect you with our restructuring team."))
    assert [f["code"] for f in flags] == ["NO_GOODBYE"]
    silent = check_call(_transfer(None))
    assert "said nothing after the customer's last message" in silent[0]["note"]


def test_goodbye_present_or_no_close_is_not_flagged():
    assert (
        codes(_transfer("I will connect you with our restructuring team. Thank you. Goodbye."))
        == []
    )
    hung_up = call(say(1.0, "Am I speaking with Ms Lin?"), hear(1.5, "Yes."))
    assert codes(hung_up) == []


def test_a_question_repeated_in_the_goodbye_is_flagged():
    offer = "Would you like me to connect you with the customer support team?"
    c = call(
        hear(1.0, "I lost my job last month."),
        say(1.1, f"I am sorry to hear that. {offer}"),
        hear(2.0, "No, thank you."),
        say(2.1, f"I am sorry to hear that. {offer} Thank you. Goodbye."),
        start(2.5, "close_call", {"outcome": "no_promise", "reason": "hardship"}),
    )
    flags = [f for f in check_call(c) if f["code"] == "SAID_TWICE"]
    assert {f["evidence"] for f in flags} == {offer, "I am sorry to hear that."}
    assert all(f["level"] == "review" and "final message" in f["note"] for f in flags)


def test_a_reworded_offer_or_sympathy_line_is_flagged():
    c = call(
        say(1.0, "Hello."),
        say(2.0, "I am sorry, but I cannot offer a discount on this debt."),
        hear(3.0, "Really?"),
        say(4.0, "I am sorry, but I cannot offer any discounts on the debt."),
    )
    assert codes(c, "review") == ["SAID_TWICE"]


def test_a_question_a_tool_result_asks_for_again_is_info_not_review():
    q = "What is your date of birth?"
    c = call(
        say(1.0, q),
        hear(2.0, "The 11th of July 1991."),
        start(
            2.1,
            "verify_identity",
            {"field": "date_of_birth", "answer": "1991-07-11"},
            function="verify_identity",
        ),  # fmt: skip
        done(
            2.2,
            {
                "verified": False,
                "what_to_do_next": "Wrong answer. You may ask that same question again.",
            },
            function="verify_identity",
        ),  # fmt: skip
        say(2.3, q),
    )
    flags = check_call(c)
    assert [(f["code"], f["level"]) for f in flags] == [("SAID_TWICE", "info")]
    assert "tool result asked for it again" in flags[0]["note"]


def test_stock_replies_are_not_review_flags():
    cut = "Sorry, your message was cut off. Could you give me the whole answer in a few words?"
    c = call(
        say(1.0, "What is your date of birth?"),
        hear(2.0, "It is the 12th of"),
        say(2.1, cut),
        hear(3.0, "It is the 21st of"),
        say(3.1, cut),
        hear(4.0, "Well, I"),
        say(4.1, "Please go on."),
        hear(5.0, "Uh"),
        say(5.1, "Please go on."),
    )
    assert codes(c, "review") == []


def test_an_offer_and_its_readback_are_not_a_repeat():
    c = call(
        say(1.0, "Hello."),
        say(2.0, "Can you make a payment of 365.00 on Friday 16 October 2026?"),
        hear(3.0, "Yes."),
        say(
            4.0,
            "I will record a payment of 365.00 for your credit card on Friday 16 October 2026. Do you confirm?",
        ),
    )
    assert codes(c) == []


def test_unverified_close_without_a_refusal_is_review_and_with_one_info():
    def close_after(customer: str) -> dict:
        return call(
            say(1.0, "What is your date of birth?"),
            hear(2.0, customer),
            say(2.1, "Thank you. Goodbye."),
            start(2.5, "close_call", {"outcome": "not_verified", "reason": "declined"}),
        )

    assert codes(close_after("The 17th of May 1986."), "review") == ["UNVERIFIED"]
    refusal = close_after("I don't want to answer that.")
    assert [(f["code"], f["level"]) for f in check_call(refusal)] == [("UNVERIFIED", "info")]


def test_a_verified_close_and_a_refused_tool():
    c = call(
        start(1.0, "verify_identity", {"field": "date_of_birth"}, function="verify_identity"),
        say(2.0, "Thank you. Goodbye."),
        start(2.5, "close_call", {"outcome": "not_verified", "reason": "failed"}),
    )
    assert codes(c) == []
    refused = call(_sys(1.0, {"event": "route_evaluated", "variable_table": {
        "verify_identity_response": "The function `verify_identity` is not currently available."}}))  # fmt: skip
    assert codes(refused) == ["TOOL_REFUSED"]


def test_cli_reads_a_folder_and_maps_cases(tmp_path, capsys):
    c = _transfer("I can connect you with our restructuring team.")
    (tmp_path / "c1.json").write_text(json.dumps(c))
    (tmp_path / "notes.json").write_text(json.dumps({"no": "messages"}))
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({"rows": [{"id": "PUB-09", "call_id": "c1"}]}) + "\n")
    out = tmp_path / "flags.json"
    assert main([str(tmp_path), "--rows", str(rows), "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "PUB-09" in printed and "NO_GOODBYE" in printed and "1 calls" in printed
    assert json.loads(out.read_text())[0]["flags"][0]["code"] == "NO_GOODBYE"


def test_an_end_node_farewell_after_close_call_is_info():
    c = _transfer(None)
    c["messages"].append(say(3.7, "Thank you. Goodbye."))
    flags = check_call(c)
    assert [(f["code"], f["level"]) for f in flags] == [("NO_GOODBYE", "info")]
    assert "end node said the goodbye after close_call" in flags[0]["note"]


def test_a_goodbye_said_only_after_close_call_by_the_model_without_routing_is_not_counted_early():
    c = call(
        say(2.0, "Payments can take one business day to appear."),
        start(3.0, "close_call", {"outcome": "paid"}),
        say(4.5, "Thank you. Goodbye."),
    )
    assert [(f["code"], f["level"]) for f in check_call(c)] == [("NO_GOODBYE", "info")]


def test_weekday_with_an_iso_date_or_month_the_day():
    assert codes(call(say(1.0, "Can you pay 637.50 on Monday 2026-10-20?"))) == ["WEEKDAY"]
    assert codes(call(say(1.0, "Can you pay 637.50 on Tuesday 2026-10-20?"))) == []
    assert codes(call(say(1.0, "Can you pay on Friday, October the 17th?"))) == ["WEEKDAY"]


def test_readback_wrong_amount_wrong_date_and_tomorrow():
    rb = "I will record a payment of 356.00 for your credit card ending 7740 on Friday 16 October 2026. Do you confirm?"
    assert "amount" in check_call(promise_call(rb))[0]["note"]
    rb = "I will record a payment of 365.00 for your credit card ending 7740 on Friday 23 October 2026. Do you confirm?"
    assert "date" in check_call(promise_call(rb))[0]["note"]
    c = promise_call(
        "I will record 365.00 for your credit card ending 7740 tomorrow. Do you confirm?"
    )
    c["messages"][0] = _sys(
        0.0, {"event": "route_evaluated", "variable_table": {"now": "2026-10-15T11:00"}}
    )
    assert codes(c) == []


def test_reasking_an_answered_question_is_review_even_when_the_tool_lists_it():
    q = "What is your date of birth?"
    listed = "Correct. Now ask the next security question. The questions in order: 1. What is your date of birth?"
    c = call(
        say(1.0, q),
        hear(2.0, "The 19th of October 1983."),
        done(2.2, {"verified": True, "what_to_do_next": listed}, function="verify_identity"),
        say(2.3, f"Correct. {q}"),
    )
    assert [(f["code"], f["level"]) for f in check_call(c)] == [("SAID_TWICE", "review")]


def test_a_repeat_after_the_customers_question_is_info():
    ask = "Am I speaking with Mr Bell?"
    c = call(
        say(1.0, f"I am a digital assistant calling from Freya Bank. {ask}"),
        hear(2.0, "Hello?"),
        say(2.1, ask),
    )
    assert [(f["code"], f["level"]) for f in check_call(c)] == [("SAID_TWICE", "info")]


def test_a_repeated_offer_after_complete_refusals_is_review():
    offer = "Can you pay 365.00 on Friday 16 October 2026?"
    c = call(
        say(1.0, "Hello."),
        hear(1.2, "Hi there"),
        say(2.0, offer),
        hear(3.0, "No, I can't"),
        say(4.0, offer),
        hear(5.0, "No, not right now"),
        say(6.0, offer),
    )
    assert codes(c, "review") == ["SAID_TWICE"]


def test_more_refusal_wordings_make_an_unverified_close_info():
    for words in (
        "None of your business.",
        "I'm not giving you that.",
        "Forget it, I'm hanging up.",
    ):
        c = call(
            say(1.0, "What is your date of birth?"),
            hear(2.0, words),
            say(2.1, "Thank you. Goodbye."),
            start(2.5, "close_call", {"outcome": "not_verified", "reason": "declined"}),
        )
        assert [(f["code"], f["level"]) for f in check_call(c)] == [("UNVERIFIED", "info")], words


def test_an_unreadable_file_is_skipped(tmp_path, capsys):
    (tmp_path / "a.json").write_text('{"id": "x", "messages": [')
    (tmp_path / "b.json").write_text(json.dumps(_transfer(None)))
    assert main([str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "skipped" in printed and "NO_GOODBYE" in printed
