"""Tests for per-worker in-flight vCon concurrency (PR #166).

Two layers:

  1. `get_vcon_concurrency()` reads CONSERVER_VCON_CONCURRENCY correctly and
     clamps invalid values to 1.

  2. `worker_loop()` dispatches popped vCons to a ThreadPoolExecutor when
     concurrency > 1 and back-pressures so at most N chains run in parallel.
     The default (concurrency=1) still runs strictly serially.

All Redis and chain-execution I/O is patched out — these are fast in-process
tests, no docker/redis required.

Run with:
    docker compose run --rm conserver pytest conserver/tests/test_vcon_concurrency.py -v
"""
import os
import threading
import time
from importlib import reload
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# get_vcon_concurrency()
# ---------------------------------------------------------------------------

def _reload_config():
    """Re-import settings + config so env-var changes take effect."""
    import settings
    import config
    reload(settings)
    reload(config)
    return config


def test_get_vcon_concurrency_default_is_one(monkeypatch):
    monkeypatch.delenv("CONSERVER_VCON_CONCURRENCY", raising=False)
    config = _reload_config()
    assert config.get_vcon_concurrency() == 1


def test_get_vcon_concurrency_reads_env_var(monkeypatch):
    monkeypatch.setenv("CONSERVER_VCON_CONCURRENCY", "8")
    config = _reload_config()
    assert config.get_vcon_concurrency() == 8


@pytest.mark.parametrize("raw", ["0", "-1", "-99"])
def test_get_vcon_concurrency_clamps_below_one(monkeypatch, raw):
    """Values < 1 must be coerced to 1 — never spin a zero-thread pool."""
    monkeypatch.setenv("CONSERVER_VCON_CONCURRENCY", raw)
    config = _reload_config()
    assert config.get_vcon_concurrency() == 1


# ---------------------------------------------------------------------------
# worker_loop dispatch behaviour
# ---------------------------------------------------------------------------

class _DispatchHarness:
    """Drives worker_loop with mocked Redis + a fake _handle_vcon, then
    reports per-vCon start/end timestamps so we can assert on parallelism.
    """

    def __init__(self, vcon_ids, sleep_per_vcon=0.3):
        self.vcon_ids = list(vcon_ids)
        self.sleep = sleep_per_vcon
        self._pending = list(vcon_ids)
        self._pending_lock = threading.Lock()
        self.events = []  # list of (timestamp, "BEGIN"|"END", vcon_id)
        self.events_lock = threading.Lock()
        self.in_flight_peak = 0
        self._in_flight = 0
        self._in_flight_lock = threading.Lock()

    def fake_blpop(self, _lists, timeout):  # noqa: ARG002 — mocked signature
        with self._pending_lock:
            if not self._pending:
                # No more items: signal worker_loop to exit
                import main
                main.shutdown_requested = True
                return None
            vcon_id = self._pending.pop(0)
        return ("test_ingress", vcon_id)

    def fake_handle_vcon(self, _worker_name, _ingress_list, vcon_id, _chain_details):
        with self._in_flight_lock:
            self._in_flight += 1
            self.in_flight_peak = max(self.in_flight_peak, self._in_flight)
        with self.events_lock:
            self.events.append((time.time(), "BEGIN", vcon_id))
        time.sleep(self.sleep)
        with self.events_lock:
            self.events.append((time.time(), "END", vcon_id))
        with self._in_flight_lock:
            self._in_flight -= 1

    def wall_clock(self):
        begins = [t for t, kind, _ in self.events if kind == "BEGIN"]
        ends = [t for t, kind, _ in self.events if kind == "END"]
        return max(ends) - min(begins)


@pytest.fixture
def main_module(monkeypatch):
    """Import main with the heavy module-level side effects neutralised.

    main.py registers signal handlers and creates a Redis client at import.
    For unit tests we want those to be no-ops.
    """
    monkeypatch.setenv("REDIS_URL", "redis://localhost:65535/0")  # unreachable but inert
    with patch("redis_mgr.get_client", return_value=MagicMock()):
        import main
        reload(main)
    main.shutdown_requested = False
    main.worker_processes = []
    main.imported_modules = {}
    yield main
    main.shutdown_requested = False


def _run_worker_loop(main_module, harness, concurrency):
    """Patch everything I/O-bound around worker_loop and run it to completion."""
    fake_config = {
        "chains": {
            "test": {
                "ingress_lists": ["test_ingress"],
                "links": [],
                "storages": [],
                "enabled": 1,
            }
        },
        "imports": {},
    }

    mock_r = MagicMock()
    mock_r.blpop.side_effect = harness.fake_blpop

    with patch.dict(os.environ, {"CONSERVER_VCON_CONCURRENCY": str(concurrency)}), \
         patch("main.r", mock_r), \
         patch("main.redis_mgr.get_client", return_value=mock_r), \
         patch("main.init_error_tracker"), \
         patch("main.init_tracing"), \
         patch("main.get_config", return_value=fake_config), \
         patch("main.signal.signal"), \
         patch("main._handle_vcon", side_effect=harness.fake_handle_vcon), \
         patch("main.get_vcon_concurrency", return_value=concurrency):
        main_module.worker_loop(worker_id=1)


def test_worker_loop_serial_when_concurrency_is_one(main_module):
    harness = _DispatchHarness(vcon_ids=[f"vcon-{i}" for i in range(3)], sleep_per_vcon=0.3)
    _run_worker_loop(main_module, harness, concurrency=1)

    assert harness.in_flight_peak == 1, "concurrency=1 must never have >1 vCon in flight"
    assert harness.wall_clock() >= 0.85
    sorted_events = sorted(harness.events, key=lambda e: e[0])
    last_end = None
    for ts, kind, _vcon in sorted_events:
        if kind == "BEGIN" and last_end is not None:
            assert ts >= last_end - 0.05  # tiny slack for clock resolution
        if kind == "END":
            last_end = ts


def test_worker_loop_concurrent_when_enabled(main_module):
    harness = _DispatchHarness(vcon_ids=[f"vcon-{i}" for i in range(5)], sleep_per_vcon=0.5)
    _run_worker_loop(main_module, harness, concurrency=5)

    assert harness.in_flight_peak == 5, (
        f"expected 5 concurrent vCons, peaked at {harness.in_flight_peak}"
    )
    wall = harness.wall_clock()
    assert wall < 1.5, f"wall-clock {wall:.2f}s suggests not actually concurrent"


def test_worker_loop_backpressures_at_concurrency_limit(main_module):
    """With 10 vCons and concurrency=3, peak in-flight must never exceed 3."""
    harness = _DispatchHarness(vcon_ids=[f"vcon-{i}" for i in range(10)], sleep_per_vcon=0.2)
    _run_worker_loop(main_module, harness, concurrency=3)

    assert harness.in_flight_peak == 3, (
        f"back-pressure broken — peaked at {harness.in_flight_peak} with limit=3"
    )
    wall = harness.wall_clock()
    assert 0.5 <= wall <= 2.5, f"wall-clock {wall:.2f}s outside expected band"
