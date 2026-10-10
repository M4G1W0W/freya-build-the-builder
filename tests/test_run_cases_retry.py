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


SIM = "1f458199-ff13-4528-8915-a2818d5febc5"
T_END = 1_791_666_000.0  # epoch seconds of the last call's end in the fake platform


def _platform(ended=(True, True, True)):
    """A fake read-only Freya: one iteration with one call per entry of `ended`."""
    calls = []

    def api(method, path, body=None, **params):
        calls.append(path)
        if path == f"/api/v2/simulations/{SIM}/iterations":
            return {"iterations": [{"id": "it1"}]}
        if path == f"/api/v2/simulations/{SIM}/iterations/it1":
            return {"runs": [{"callId": f"c{i}"} for i in range(len(ended))]}
        i = int(path.rsplit("/c", 1)[1])
        end = "2026-10-10T21:16:40+00:00" if ended[i] else None
        return {"call": {"endedAt": end and rcr.datetime.fromtimestamp(T_END - 60 * i).isoformat()}}

    return api, calls


def test_a_run_stuck_after_all_calls_ended_is_reported_once(monkeypatch):
    # 10 Oct 21:17-21:55 UTC: simulation 1f458199 stayed "running" after its 3 calls ended and
    # blocked every new simulation; the kit polls with no timeout.
    monkeypatch.setattr(rcr, "_watch", {})
    api, _ = _platform()
    start = T_END - 200
    assert rcr.check_stuck(SIM, "running", start, api) is None  # first poll: just remembered
    msg = rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S + 1, api)
    assert msg and SIM in msg and "STUCK" in msg and '{"status": "paused"}' in msg
    assert "needs the user's OK" in msg
    assert rcr.check_stuck(SIM, "running", T_END + 2 * rcr.STUCK_AFTER_S, api) is None


def test_no_report_while_a_call_is_still_going(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, _ = _platform(ended=(True, False, True))
    rcr.check_stuck(SIM, "running", T_END - 1000, api)
    assert rcr.check_stuck(SIM, "running", T_END + 3600, api) is None


def test_no_platform_reads_before_the_first_check_or_between_checks(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, calls = _platform(ended=(True, False))
    t0 = T_END
    rcr.check_stuck(SIM, "running", t0, api)
    rcr.check_stuck(SIM, "running", t0 + rcr.FIRST_CHECK_S - 1, api)
    assert calls == []
    rcr.check_stuck(SIM, "running", t0 + rcr.FIRST_CHECK_S, api)
    n = len(calls)
    assert n > 0
    rcr.check_stuck(SIM, "running", t0 + rcr.FIRST_CHECK_S + rcr.CHECK_EVERY_S - 1, api)
    assert len(calls) == n


def test_a_finished_run_is_forgotten(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, calls = _platform()
    rcr.check_stuck(SIM, "running", T_END, api)
    assert rcr.check_stuck(SIM, "completed", T_END + 5000, api) is None
    assert SIM not in rcr._watch and calls == []


def test_the_watcher_never_ends_the_run_it_watches(monkeypatch, caplog):
    def broken(method, path, body=None, **params):
        if path.endswith("/iterations"):
            raise RuntimeError("GET iterations -> 500: down")
        return {"simulation": {"status": "running"}}

    monkeypatch.setattr(rcr, "_watch", {SIM: {"first": 0.0, "checked": 0.0, "reported": False}})
    monkeypatch.setattr(rcr, "api_with_retry", broken)
    out = rcr.api_watched("GET", f"/api/v2/simulations/{SIM}")
    assert out == {"simulation": {"status": "running"}}
    assert "stuck check" in caplog.text
