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
OTHER = "a36c1d01-1003-4b83-8d5e-b5121a82bc39"
T_END = 1_791_666_000.0  # epoch seconds of the last call's end in the fake platform


def _platform(ended=(True, True, True), judged=True, running=(SIM,)):
    """A fake Freya: each simulation has one iteration with one call per entry of `ended`."""
    calls, puts = [], []

    def api(method, path, body=None, **params):
        calls.append(path)
        if method == "PUT":
            puts.append((path, body))
            return {"simulation": {"status": "paused"}}
        if path == "/api/v2/simulations":
            return {"simulations": [{"id": s, "status": "running"} for s in running]}
        if path.endswith("/iterations"):
            return {"iterations": [{"id": "it1", "status": "completed" if judged else "running"}]}
        if path.endswith("/iterations/it1"):
            return {"runs": [{"callId": f"c{i}"} for i in range(len(ended))]}
        i = int(path.rsplit("/c", 1)[1])
        end = rcr.datetime.fromtimestamp(T_END - 60 * i).isoformat() if ended[i] else None
        return {"call": {"endedAt": end}}

    return api, calls, puts


def test_a_run_stuck_after_all_calls_ended_and_judged_is_paused_once(monkeypatch, capsys):
    # 10 Oct 21:17-21:55 and 11 Oct 01:21-08:12 UTC: a simulation stayed "running" after its calls ended
    # and its iteration completed, and blocked every new simulation; the kit polls with no timeout.
    monkeypatch.setattr(rcr, "_watch", {})
    api, _, puts = _platform()
    assert rcr.check_stuck(SIM, "running", T_END - 200, api) is None  # first poll: just remembered
    assert rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S - 1, api) is None
    msg = rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S + rcr.CHECK_EVERY_S, api)
    assert msg and msg.startswith("UNSTUCK") and SIM in msg
    assert puts == [(f"/api/v2/simulations/{SIM}", {"status": "paused"})]
    assert "UNSTUCK" in capsys.readouterr().out
    assert rcr.check_stuck(SIM, "running", T_END + 10 * rcr.STUCK_AFTER_S, api) is None
    assert len(puts) == 1


def test_never_paused_while_a_call_is_still_going(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, _, puts = _platform(ended=(True, False, True))
    rcr.check_stuck(SIM, "running", T_END - 1000, api)
    assert rcr.check_stuck(SIM, "running", T_END + 3600, api) is None
    assert puts == []


def test_unjudged_runs_wait_longer_before_a_pause(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, _, puts = _platform(judged=False)
    rcr.check_stuck(SIM, "running", T_END - 1000, api)
    assert rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S + 1, api) is None
    msg = rcr.check_stuck(SIM, "running", T_END + rcr.NO_JUDGE_AFTER_S + 1, api)
    assert msg and "never completed" in msg and len(puts) == 1


def test_a_simulation_older_than_the_hard_limit_is_paused_even_mid_call(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, _, puts = _platform(ended=(True, False))
    created = T_END - rcr.HARD_AFTER_S
    rcr.check_stuck(SIM, "running", T_END - 1000, api, created)
    assert rcr.check_stuck(SIM, "running", T_END, api, created) is not None
    assert len(puts) == 1


def test_no_platform_reads_before_the_first_check_or_between_checks(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    api, calls, _ = _platform(ended=(True, False))
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
    api, calls, _ = _platform()
    rcr.check_stuck(SIM, "running", T_END, api)
    assert rcr.check_stuck(SIM, "completed", T_END + 5000, api) is None
    assert SIM not in rcr._watch and calls == []


def test_a_refused_start_pauses_the_stuck_simulation_that_blocks_it(monkeypatch):
    # 11 Oct 01:21 UTC: rep 2's simulation went back to "running" after the client had scored it, so
    # rep 3's POST was refused ("concurrent simulations") for 30 minutes.
    monkeypatch.setattr(rcr, "_last_workspace_check", 0.0)
    api, _, puts = _platform(running=(OTHER,))

    def refused(method, path, body=None, **params):
        if method == "POST":
            raise RuntimeError("POST /api/v2/simulations -> 409: too many concurrent simulations")
        return api(method, path, body, **params)

    monkeypatch.setattr(rcr, "api_with_retry", refused)
    monkeypatch.setattr(rcr.time, "time", lambda: T_END + rcr.STUCK_AFTER_S + 1)
    with pytest.raises(RuntimeError, match="concurrent simulations"):
        rcr.api_watched("POST", "/api/v2/simulations", {"agentId": "x"})
    assert puts == [(f"/api/v2/simulations/{OTHER}", {"status": "paused"})]
    with pytest.raises(RuntimeError):  # within WORKSPACE_CHECK_EVERY_S: no second look
        rcr.api_watched("POST", "/api/v2/simulations", {"agentId": "x"})
    assert len(puts) == 1


def test_a_refused_start_leaves_a_working_simulation_alone(monkeypatch):
    monkeypatch.setattr(rcr, "_last_workspace_check", 0.0)
    api, _, puts = _platform(ended=(True, False), running=(OTHER,))
    assert rcr.unstick_workspace(T_END + 3600, api) == []
    assert puts == []


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


def test_a_broken_workspace_check_keeps_the_original_refusal(monkeypatch, caplog):
    monkeypatch.setattr(rcr, "_last_workspace_check", 0.0)

    def broken(method, path, body=None, **params):
        if method == "POST":
            raise RuntimeError("POST /api/v2/simulations -> 409: too many concurrent simulations")
        raise RuntimeError("GET /api/v2/simulations -> 500: down")

    monkeypatch.setattr(rcr, "api_with_retry", broken)
    with pytest.raises(RuntimeError, match="concurrent simulations"):
        rcr.api_watched("POST", "/api/v2/simulations", {})
    assert "workspace stuck check failed" in caplog.text
