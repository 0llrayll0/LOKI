import time

from app.core.scheduler import Scheduler


def test_run_now_executes() -> None:
    s = Scheduler()
    state = {"n": 0}

    def job():
        state["n"] += 1

    s.add_job("j", job, 10)
    s.run_now("j")
    assert state["n"] == 1


def test_start_stop_idempotent() -> None:
    s = Scheduler()
    s.start()
    s.start()
    time.sleep(0.1)
    s.stop()
    s.stop()


def test_exception_does_not_kill() -> None:
    s = Scheduler()
    state = {"n": 0}

    def bad():
        raise RuntimeError("x")

    def good():
        state["n"] += 1

    s.add_job("bad", bad, 0.05)
    s.add_job("good", good, 0.05)
    s.start()
    time.sleep(0.3)
    s.stop()
    assert state["n"] >= 1