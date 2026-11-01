"""Scheduler baseado em threading do LOKI CORE."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, tuple[Callable[[], None], float]] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def add_job(self, name: str, func: Callable[[], None], interval_seconds: float) -> None:
        with self._lock:
            self._jobs[name] = (func, interval_seconds)

    def remove_job(self, name: str) -> None:
        with self._lock:
            self._jobs.pop(name, None)

    def run_now(self, name: str) -> None:
        with self._lock:
            job = self._jobs.get(name)
        if job is None:
            return
        func, _ = job
        try:
            func()
        except Exception:  # noqa: BLE001
            logger.exception("scheduler_job_error", extra={"job": name})

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        self._thread = None

    def _loop(self) -> None:
        last_run: dict[str, float] = {}
        while not self._stop.is_set():
            now = time.monotonic()
            with self._lock:
                jobs = list(self._jobs.items())
            for name, (func, interval) in jobs:
                if name not in last_run or (now - last_run[name]) >= interval:
                    last_run[name] = now
                    try:
                        func()
                    except Exception:  # noqa: BLE001
                        logger.exception("scheduler_job_error", extra={"job": name})
            self._stop.wait(0.1)