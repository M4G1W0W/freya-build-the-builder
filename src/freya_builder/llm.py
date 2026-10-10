"""The builder's only LLM door: OpenAI chat completions with strict JSON-schema output (stdlib).

The phone agent never uses this; it runs on Freya's fixed model. Configure with env vars:
OPENAI_API_KEY (required); BUILDER_MODEL and BUILDER_MODEL_FALLBACKS (optional, tried before
DEFAULT_MODELS); OPENAI_BASE_URL (optional).
Strict schemas must list every property in `required` and set additionalProperties false.
"""

import json
import os
import time
import urllib.error
import urllib.request

from .trace import Trace

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Benchmarked in exp02/exp03 (Decision log 2026-10-10 14:40). In code, so a fresh-clone re-run needs only the key.
DEFAULT_MODELS = ("gpt-6.1-sol", "gpt-5.5", "gpt-5.4")


class LLMError(RuntimeError):
    pass


def model_id() -> str:
    return model_chain()[0]


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


class ModelUnavailable(LLMError):
    pass


def model_chain() -> list[str]:
    """Env models first (BUILDER_MODEL, then BUILDER_MODEL_FALLBACKS), then DEFAULT_MODELS."""
    env = [os.environ.get("BUILDER_MODEL", "")] + os.environ.get(
        "BUILDER_MODEL_FALLBACKS", ""
    ).split(",")
    return list(dict.fromkeys([m.strip() for m in env if m.strip()] + list(DEFAULT_MODELS)))


def _unavailable(code: int, text: str) -> bool:
    low = text.lower()
    missing = (
        code in (400, 403, 404)
        and "model" in low
        and (
            "not found" in low
            or "does not exist" in low
            or "access" in low
            or "model_not_found" in low
        )
    )
    # A model that cannot do strict JSON output is as good as missing for this builder.
    unsupported = code == 400 and ("json_schema" in low or "response_format" in low)
    return missing or unsupported


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
    """One structured call. Returns the parsed JSON object. Logs one trace line per success.

    Without an explicit `model`, tries BUILDER_MODEL then BUILDER_MODEL_FALLBACKS, moving on only
    when a model is unavailable to the key (so a re-run elsewhere still works)."""
    chain = [model] if model else model_chain()
    for i, candidate in enumerate(chain):
        try:
            return _chat_once(
                trace, purpose, system, user, schema, schema_name, candidate, retries, timeout
            )
        except ModelUnavailable as e:
            if i == len(chain) - 1:
                raise
            trace.warn(
                f"model {candidate} unavailable ({str(e)[:120]}); falling back to {chain[i + 1]}"
            )
    raise LLMError(f"{purpose}: no model available")


def _chat_once(trace, purpose, system, user, schema, schema_name, model, retries, timeout) -> dict:
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
            text = e.read().decode(errors="replace")[:500]
            last = f"HTTP {e.code}: {text}"
            if _unavailable(e.code, text):
                raise ModelUnavailable(f"{purpose}: {last}") from None
            if e.code in RETRY_STATUS and attempt < retries:
                trace.warn(f"model call '{purpose}' to {model} failed ({last[:120]}), retrying")
                time.sleep(2 * (attempt + 1))
                continue
            trace.warn(f"model call '{purpose}' to {model} failed ({last[:120]})")
            if e.code in RETRY_STATUS:  # rate limit or outage after retries: try the next model
                raise ModelUnavailable(f"{purpose}: {last}") from None
            raise LLMError(f"{purpose}: {last}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            if attempt < retries:
                trace.warn(
                    f"model call '{purpose}' to {model} network error ({last[:120]}), retrying"
                )
                time.sleep(2 * (attempt + 1))
                continue
            trace.warn(f"model call '{purpose}' to {model} network error ({last[:120]})")
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
