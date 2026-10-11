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


@pytest.mark.parametrize("exc", [TimeoutError("timed out"), ConnectionResetError("reset")])
def test_a_network_error_on_get_is_retried_but_not_on_post(monkeypatch, exc):
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if len(calls) == 1 or method == "POST":
            raise exc
        return {"ok": True}

    monkeypatch.setattr(rcr, "_api", api)
    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    assert rcr.api_with_retry("GET", "/api/v2/simulations/x") == {"ok": True}
    with pytest.raises(type(exc)):
        rcr.api_with_retry("POST", "/api/v2/simulations")


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


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(rcr, "_watch", {})
    monkeypatch.setattr(rcr, "_pauses", {})
    monkeypatch.setattr(rcr, "_last_workspace_check", 0.0)


def test_a_run_stuck_after_all_calls_ended_and_judged_is_paused(monkeypatch, capsys):
    # 10 Oct 21:17-21:55 and 11 Oct 01:21-08:12 UTC: a simulation stayed "running" after its calls ended
    # and its iteration completed, and blocked every new simulation; the kit polls with no timeout.
    api, _, puts = _platform()
    assert rcr.check_stuck(SIM, "running", T_END - 200, api) is None  # first poll: just remembered
    assert rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S - 1, api) is None
    msg = rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S + rcr.CHECK_EVERY_S, api)
    assert msg and msg.startswith("UNSTUCK") and SIM in msg
    assert puts == [(f"/api/v2/simulations/{SIM}", {"status": "paused"})]
    assert "UNSTUCK" in capsys.readouterr().out


def test_pauses_are_capped_per_simulation(capsys):
    api, _, puts = _platform()
    t = T_END + rcr.STUCK_AFTER_S
    rcr.check_stuck(SIM, "running", T_END - 200, api)
    for k in range(1, 6):  # it stays "running": pause, pause, then give up once, loudly
        rcr.check_stuck(SIM, "running", t + k * rcr.CHECK_EVERY_S, api)
    assert len(puts) == rcr.MAX_PAUSES
    assert capsys.readouterr().out.count("UNSTUCK FAILED") == 1


def test_a_failed_pause_is_tried_again_at_the_next_check(caplog):
    api, _, puts = _platform()
    tries = []

    def flaky(method, path, body=None, **params):
        if method == "PUT" and not tries:
            tries.append(1)
            raise RuntimeError("PUT -> 500: down")
        return api(method, path, body, **params)

    t = T_END + rcr.STUCK_AFTER_S
    rcr.check_stuck(SIM, "running", T_END - 200, flaky)
    with pytest.raises(RuntimeError):
        rcr.check_stuck(SIM, "running", t + rcr.CHECK_EVERY_S, flaky)
    assert rcr.check_stuck(SIM, "running", t + 2 * rcr.CHECK_EVERY_S, flaky)
    assert len(puts) == 1


def test_never_paused_while_a_call_is_still_going():
    api, _, puts = _platform(ended=(True, False, True))
    rcr.check_stuck(SIM, "running", T_END - 1000, api)
    assert rcr.check_stuck(SIM, "running", T_END + 3600, api) is None
    assert puts == []


def test_unjudged_runs_wait_longer_before_a_pause():
    api, _, puts = _platform(judged=False)
    rcr.check_stuck(SIM, "running", T_END - 1000, api)
    assert rcr.check_stuck(SIM, "running", T_END + rcr.STUCK_AFTER_S + 1, api) is None
    msg = rcr.check_stuck(SIM, "running", T_END + rcr.NO_JUDGE_AFTER_S + 1, api)
    assert msg and "never completed" in msg and len(puts) == 1


def test_a_simulation_older_than_the_hard_limit_is_paused_even_mid_call():
    api, _, puts = _platform(ended=(True, False))
    created = T_END - rcr.HARD_AFTER_S
    rcr.check_stuck(SIM, "running", T_END - 1000, api, created)
    assert rcr.check_stuck(SIM, "running", T_END, api, created) is not None
    assert len(puts) == 1


def test_no_platform_reads_before_the_first_check_or_between_checks():
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


def test_a_finished_run_is_forgotten():
    api, calls, _ = _platform()
    rcr.check_stuck(SIM, "running", T_END, api)
    assert rcr.check_stuck(SIM, "completed", T_END + 5000, api) is None
    assert SIM not in rcr._watch and calls == []


def test_a_refused_start_pauses_the_stuck_simulation_that_blocks_it(monkeypatch):
    # 11 Oct 01:21 UTC: rep 2's simulation went back to "running" after the client had scored it, so
    # rep 3's POST was refused ("concurrent simulations") for 30 minutes.
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


def test_a_refused_start_leaves_a_working_simulation_alone():
    api, _, puts = _platform(ended=(True, False), running=(OTHER,))
    assert rcr.unstick_workspace(T_END + 3600, api) == []
    assert puts == []


def test_the_watcher_never_ends_the_run_it_watches(monkeypatch, caplog):
    def broken(method, path, body=None, **params):
        if path.endswith("/iterations"):
            raise RuntimeError("GET iterations -> 500: down")
        return {"simulation": {"status": "running"}}

    monkeypatch.setattr(rcr, "_watch", {SIM: {"first": 0.0, "checked": 0.0}})
    monkeypatch.setattr(rcr, "api_with_retry", broken)
    out = rcr.api_watched("GET", f"/api/v2/simulations/{SIM}")
    assert out == {"simulation": {"status": "running"}}
    assert "stuck check" in caplog.text


def test_a_broken_workspace_check_keeps_the_original_refusal(monkeypatch, caplog):

    def broken(method, path, body=None, **params):
        if method == "POST":
            raise RuntimeError("POST /api/v2/simulations -> 409: too many concurrent simulations")
        raise RuntimeError("GET /api/v2/simulations -> 500: down")

    monkeypatch.setattr(rcr, "api_with_retry", broken)
    with pytest.raises(RuntimeError, match="concurrent simulations"):
        rcr.api_watched("POST", "/api/v2/simulations", {})
    assert "workspace stuck check failed" in caplog.text


def test_a_rep_without_judge_verdicts_is_repeated_once(capsys):
    # 11 Oct 08:22 UTC, M2 extra-B rep 2: "Call ended but analysis never arrived (300s)" on all 3 calls.
    unjudged = {
        "id": "PUB-11",
        "pass": False,
        "failed": ["conversation: Call ended but analysis never arrived (300s)"],
    }
    judged = {
        "id": "PUB-11",
        "pass": False,
        "failed": ["conversation: the floor was offered twice"],
    }
    reps = [
        ([unjudged], "s1", "i1", "completed", 60, 2),
        ([judged], "s2", "i2", "completed", 60, 2),
    ]
    calls = []

    def run_once(agent_id, cases, ids):
        calls.append(1)
        return reps[len(calls) - 1]

    out = rcr.repeat_unjudged(run_once)("a", [], {})
    assert out[1] == "s2" and len(calls) == 2
    assert "-- run discarded: no judge verdict for PUB-11" in capsys.readouterr().out
    calls.clear()
    reps[0] = reps[1]
    assert rcr.repeat_unjudged(run_once)("a", [], {})[1] == "s2" and len(calls) == 1


def test_unjudged_reads_only_missing_verdicts():
    rows = [
        {"id": "A", "failed": ["conversation: no verdict"]},
        {"id": "B", "failed": ["outcome (None, None), expected ('promise', None)"]},
        {"id": "C", "failed": []},
    ]
    assert rcr.unjudged(rows) == ["A"]


def test_waits_for_a_healthy_platform_before_starting(monkeypatch, capsys):
    tries = []

    def api(method, path, body=None, **params):
        tries.append(path)
        if len(tries) < 3:
            raise RuntimeError("GET /api/v2/simulations -> 504: error code: 504")
        return {"simulations": []}

    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    rcr.wait_until_healthy(api, limit_s=10_000)
    assert len(tries) == 3 and capsys.readouterr().out.count("platform not answering") == 2


def test_gives_up_waiting_after_the_limit(monkeypatch):
    def down(method, path, body=None, **params):
        raise RuntimeError("GET /api/v2/simulations -> 504: error code: 504")

    clock = iter(range(0, 100_000, 100))
    monkeypatch.setattr(rcr.time, "time", lambda: next(clock))
    monkeypatch.setattr(rcr.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        rcr.wait_until_healthy(down, limit_s=300)


def _iteration(*runs):
    return {"runs": [dict(r) for r in runs]}


def test_a_run_still_analyzing_takes_the_judge_verdict_from_its_call_record(capsys):
    # 11 Oct 12:15 UTC, smoke 94c9e350: the run stayed "analyzing" (attempt 2/4) although its call
    # 6af560aa had successCriteriaResult.success=True; run_cases scored it "conversation: no verdict".
    seen = set()
    calls = {"c1": {"successCriteriaResult": {"success": True, "reason": "All criteria were met."}}}
    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration(
            {"id": "r1", "personaId": "p1", "outcome": "analyzing", "callId": "c1"}
        ),
        calls.__getitem__,
        seen,
    )
    run = get_iteration("s1", "i1")["runs"][0]
    assert run["outcome"] == "pass" and seen == {"c1"}
    assert "VERDICT FROM CALL RECORD" in capsys.readouterr().out


def test_a_failing_call_record_verdict_keeps_the_judges_reason():
    calls = {"c1": {"successCriteriaResult": {"success": False, "reason": "floor offered twice"}}}
    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration({"id": "r1", "outcome": None, "callId": "c1"}),
        calls.__getitem__,
        set(),
    )
    run = get_iteration("s1", "i1")["runs"][0]
    assert run["outcome"] == "fail"
    assert "floor offered twice" in run["reason"] and "call record" in run["reason"]


@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("pass", None),
        ("fail", None),
        ("fail", "Call ended but analysis never arrived (300s)"),
        ("inconclusive", "the transcript does not show which date was agreed"),
        ("error", "[after 4 attempts] No call created within 300s"),
    ],
)
def test_a_run_that_has_a_verdict_is_never_overridden(outcome, reason):
    def get_call(call_id):
        raise AssertionError("no call read for a judged run")

    seen = set()
    run = {"id": "r1", "outcome": outcome, "reason": reason, "callId": "c1"}
    get_iteration = rcr.with_call_verdicts(lambda s, i: _iteration(run), get_call, seen)
    assert get_iteration("s1", "i1")["runs"][0]["outcome"] == outcome and not seen


@pytest.mark.parametrize(
    "call",
    [
        {},
        {"successCriteriaResult": None},
        {"successCriteriaResult": {"success": None, "reason": ""}},
    ],
)
def test_a_call_record_without_a_verdict_leaves_the_run_unjudged(call):
    seen = set()
    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration({"id": "r1", "outcome": "analyzing", "callId": "c1"}),
        lambda call_id: call,
        seen,
    )
    assert get_iteration("s1", "i1")["runs"][0]["outcome"] == "analyzing" and not seen


def test_a_run_without_a_call_or_a_failed_call_read_stays_unjudged(caplog):
    def get_call(call_id):
        raise RuntimeError("GET /api/v2/call/c2 -> 504: error code: 504")

    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration(
            {"id": "r1", "outcome": "analyzing", "callId": None},
            {"id": "r2", "outcome": "analyzing", "callId": "c2"},
        ),
        get_call,
        set(),
    )
    runs = get_iteration("s1", "i1")["runs"]
    assert [r["outcome"] for r in runs] == ["analyzing", "analyzing"]
    assert "call record read for c2 failed" in caplog.text


def test_rows_say_where_their_verdict_came_from():
    rows = [
        {"id": "A", "call_id": "c1"},
        {"id": "B", "call_id": "c2"},
        {"id": "C", "call_id": None},
    ]
    rcr.mark_verdict_source(rows, {"c1"})
    assert [r["verdict_source"] for r in rows] == ["call", "run", "run"]


def test_every_scored_rep_is_marked_with_its_verdict_sources():
    rows = [{"id": "PUB-01", "pass": True, "failed": [], "call_id": "c1"}]
    seen = {"c1"}
    out = rcr.repeat_unjudged(lambda a, c, i: (rows, "s1", "i1", "paused", 60, 2), seen)(
        "a", [], {}
    )
    assert out[0][0]["verdict_source"] == "call"


@pytest.mark.parametrize("result", ["pending", [{"success": True}]])
def test_a_call_record_verdict_of_another_shape_leaves_the_run_unjudged(result):
    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration({"id": "r1", "outcome": "analyzing", "callId": "c1"}),
        lambda call_id: {"successCriteriaResult": result},
        set(),
    )
    assert get_iteration("s1", "i1")["runs"][0]["outcome"] == "analyzing"


def test_the_call_record_is_read_once_without_retries(monkeypatch):
    # review of 4631971: through freya.get_call the read inherited ~17 min of GET retries per stuck run,
    # all before the ledger is read. One plain read; a failure leaves the run unjudged.
    reads = []

    def api(method, path, body=None, **params):
        reads.append(path)
        raise RuntimeError(f"{method} {path} -> 504: error code: 504")

    monkeypatch.setattr(rcr, "_api", api)
    monkeypatch.setattr(rcr.time, "sleep", lambda s: pytest.fail("no retry sleep"))
    assert rcr.read_call_once("c1") is None and reads == ["/api/v2/call/c1"]


def test_rows_carry_the_attempt_count_of_their_run():
    attempts = {}
    get_iteration = rcr.with_call_verdicts(
        lambda s, i: _iteration(
            {"id": "r1", "outcome": "analyzing", "callId": "c1", "attempts": 2},
            {"id": "r2", "outcome": "pass", "callId": "c2", "attempts": 0},
        ),
        lambda call_id: {"successCriteriaResult": {"success": True, "reason": ""}},
        set(),
        attempts,
    )
    get_iteration("s1", "i1")
    rows = [
        {"id": "A", "call_id": "c1"},
        {"id": "B", "call_id": "c2"},
        {"id": "C", "call_id": None},
    ]
    rcr.mark_verdict_source(rows, {"c1"}, attempts)
    assert [(r["verdict_source"], r["attempts"]) for r in rows] == [
        ("call", 2),
        ("run", 0),
        ("run", None),
    ]


@pytest.mark.parametrize(
    "outcome,reason",
    [
        (
            "error",
            "Call ended but analysis never arrived (300s)",
        ),  # 6d0c9464 run 06d16b86, call ed7f5328
        ("inconclusive", None),  # 6d0c9464 run b94597c3, call babc4608
    ],
)
def test_a_run_whose_judge_never_arrived_takes_the_call_record_verdict(outcome, reason):
    # user-approved 12:31 UTC: both such 6d0c9464 runs had successCriteriaResult.success on their call record
    seen = set()
    calls = {"c1": {"successCriteriaResult": {"success": False, "reason": "floor offered twice"}}}
    run = {"id": "r1", "outcome": outcome, "reason": reason, "callId": "c1", "attempts": 3}
    get_iteration = rcr.with_call_verdicts(lambda s, i: _iteration(run), calls.__getitem__, seen)
    out = get_iteration("s1", "i1")["runs"][0]
    assert out["outcome"] == "fail" and "floor offered twice" in out["reason"] and seen == {"c1"}
