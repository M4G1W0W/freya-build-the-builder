import io
import json
import urllib.error

import pytest

from freya_builder import llm
from freya_builder.trace import Trace


def make_trace(monkeypatch, secret="sk-test-SECRET-123456"):
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    buf = io.StringIO()
    return Trace(stream=buf), buf


def test_trace_redacts_secrets(monkeypatch):
    trace, buf = make_trace(monkeypatch)
    trace.step("oops sk-test-SECRET-123456 leaked")
    assert "sk-test-SECRET-123456" not in buf.getvalue()
    assert "***" in buf.getvalue()


def test_trace_has_required_lines(monkeypatch):
    trace, buf = make_trace(monkeypatch)
    trace.start(["brief.md"], "api.json")
    trace.model_call("m1", "extract policy", 1.25, {"prompt_tokens": 10, "completion_tokens": 5})
    trace.created("wf1", "ag1", steps=7, tools=6, version=2)
    trace.test("dry-run", True)
    trace.end(ok=True)
    out = buf.getvalue()
    for needle in ("START", "MODEL", "model=m1 purpose=extract policy", "CREATED", "TEST", "END"):
        assert needle in out


def fake_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }


SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}


def test_chat_json_parses_and_traces(monkeypatch):
    trace, buf = make_trace(monkeypatch)
    sent = {}

    def fake_post(path, body, timeout):
        sent.update(body)
        return fake_response('{"x": 7}')

    monkeypatch.setattr(llm, "_post", fake_post)
    out = llm.chat_json(trace, "unit test", "sys", "user", SCHEMA, model="m-test")
    assert out == {"x": 7}
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert "model=m-test purpose=unit test" in buf.getvalue()


def test_chat_json_retries_on_429_then_succeeds(monkeypatch):
    trace, _ = make_trace(monkeypatch)
    calls = {"n": 0}

    def flaky(path, body, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b"slow down"))
        return fake_response(json.dumps({"x": 1}))

    monkeypatch.setattr(llm, "_post", flaky)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.chat_json(trace, "p", "s", "u", SCHEMA, model="m") == {"x": 1}
    assert calls["n"] == 2


def test_chat_json_fails_fast_on_400(monkeypatch):
    trace, _ = make_trace(monkeypatch)

    def bad(path, body, timeout):
        raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b"schema invalid"))

    monkeypatch.setattr(llm, "_post", bad)
    with pytest.raises(llm.LLMError, match="schema invalid"):
        llm.chat_json(trace, "p", "s", "u", SCHEMA, model="m")


def test_model_id_requires_env(monkeypatch):
    monkeypatch.delenv("BUILDER_MODEL", raising=False)
    with pytest.raises(llm.LLMError):
        llm.model_id()
