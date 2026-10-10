import pytest
import run_cases_retry as rcr


def _fake(errors):
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if errors:
            raise RuntimeError(f"{method} {path} -> {errors.pop(0)}: down")
        return {"ok": True}

    return api, calls


def test_get_on_5xx_is_retried_until_it_works(monkeypatch):
    api, calls = _fake([503, 502])
    monkeypatch.setattr(rcr, "_api", api)
    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    assert rcr.api_with_retry("GET", "/api/v2/simulations/x") == {"ok": True}
    assert calls == ["GET", "GET", "GET"]


@pytest.mark.parametrize("method,status", [("POST", 503), ("GET", 404), ("PUT", 500)])
def test_post_or_4xx_is_never_retried(monkeypatch, method, status):
    api, calls = _fake([status])
    monkeypatch.setattr(rcr, "_api", api)
    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        rcr.api_with_retry(method, "/api/v2/simulations")
    assert calls == [method]


def test_retries_are_bounded(monkeypatch):
    api, calls = _fake([503] * 20)
    monkeypatch.setattr(rcr, "_api", api)
    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        rcr.api_with_retry("GET", "/api/v2/simulations/x")
    assert len(calls) == len(rcr.DELAYS) + 1
