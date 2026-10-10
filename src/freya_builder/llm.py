"""The builder's only LLM door: OpenAI chat completions with strict JSON-schema output (stdlib).

The phone agent never uses this; it runs on Freya's fixed model. Configure with env vars:
OPENAI_API_KEY (required), BUILDER_MODEL (model id), OPENAI_BASE_URL (optional).
Strict schemas must list every property in `required` and set additionalProperties false.
"""

import json
import os
import time
import urllib.error
import urllib.request

from .trace import Trace

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


def model_id() -> str:
    model = os.environ.get("BUILDER_MODEL", "").strip()
    if not model:
        raise LLMError("BUILDER_MODEL is not set (see .env.example)")
    return model


def _post(path: str, body: dict, timeout: float) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise LLMError("OPENAI_API_KEY is not set")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat_json(
    trace: Trace,
    purpose: str,
    system: str,
    user: str,
    schema: dict,
    schema_name: str = "result",
    model: str | None = None,
    retries: int = 2,
    timeout: float = 600,
) -> dict:
    """One structured call. Returns the parsed JSON object. Logs one trace line per success."""
    model = model or model_id()
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
    }
    last = ""
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            resp = _post("/chat/completions", body, timeout)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}"
            if e.code in RETRY_STATUS and attempt < retries:
                trace.warn(f"model call '{purpose}' failed ({last[:120]}), retrying")
                time.sleep(2 * (attempt + 1))
                continue
            raise LLMError(f"{purpose}: {last}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            if attempt < retries:
                trace.warn(f"model call '{purpose}' network error ({last[:120]}), retrying")
                time.sleep(2 * (attempt + 1))
                continue
            raise LLMError(f"{purpose}: {last}") from None
        message = resp["choices"][0]["message"]
        if message.get("refusal"):
            raise LLMError(f"{purpose}: model refused: {message['refusal'][:300]}")
        trace.model_call(model, purpose, time.monotonic() - t0, resp.get("usage"))
        try:
            return json.loads(message.get("content") or "")
        except json.JSONDecodeError as e:
            last = f"invalid JSON: {e}"
            if attempt < retries:
                trace.warn(f"model call '{purpose}' returned invalid JSON, retrying")
                continue
            raise LLMError(f"{purpose}: {last}") from None
    raise LLMError(f"{purpose}: {last}")
