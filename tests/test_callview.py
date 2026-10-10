import json

from callview import format_messages


def sys_msg(event: dict, t: float = 1.0) -> dict:
    return {"role": "system", "message": json.dumps(event), "secondsFromStart": t}


MESSAGES = [
    {"role": "assistant", "message": "Am I speaking with Mr Reyes?", "secondsFromStart": 0.5},
    {"role": "user", "message": "Yes, speaking.", "secondsFromStart": 2.0},
    sys_msg({"event": "node_enter", "node": "identity", "from_node": "start"}),
    sys_msg(
        {
            "event": "function_call_start",
            "function": "verify_identity",
            "args": {"url": "https://bank/v1/verify_identity", "body": {"field": "phone_last4"}},
        }
    ),
    sys_msg(
        {
            "event": "function_call_complete",
            "function": "verify_identity",
            "result": {"status": "success", "data": {"ok": True, "verified": False}},
        }
    ),
    sys_msg({"event": "route_evaluated", "matched": False, "from_node": "identity"}),
    sys_msg(
        {
            "event": "route_evaluated",
            "matched": True,
            "from_node": "a",
            "target": "b",
            "reason": "r",
        }
    ),
    sys_msg({"event": "error", "message": "boom", "details": {"x": 1}}),
    {"role": "system", "message": "not json", "secondsFromStart": 3.0},
]


def test_dialogue_lines_are_labelled():
    lines = format_messages(MESSAGES)
    assert lines[0].endswith("AGENT: Am I speaking with Mr Reyes?")
    assert lines[1].endswith("CUST : Yes, speaking.")


def test_tool_calls_show_body_and_result_data():
    text = "\n".join(format_messages(MESSAGES))
    assert '-> verify_identity {"field": "phone_last4"}' in text
    assert '<- verify_identity {"ok": true, "verified": false}' in text
    assert "https://bank" not in text


def test_only_matched_routes_unless_verbose():
    quiet = "\n".join(format_messages(MESSAGES))
    assert "route a -> b: r" in quiet
    assert "(stay)" not in quiet
    assert "(stay)" in "\n".join(format_messages(MESSAGES, verbose=True))


def test_errors_shown_and_garbage_skipped():
    text = "\n".join(format_messages(MESSAGES))
    assert "!! error boom" in text
    assert "not json" not in text
