"""
Unit tests for LockManager Resource Leases & Dijkstra Resource Ordering
========================================================================

Covers:
- Exclusive locking (desktop-input, audio-out)
- Shared locking (gpu-vram, shared project access)
- Dijkstra canonical sorting preventing deadlocks
- Lease expiration and TTL reclamation
- Heartbeat and lease renewal
- Canonical resource catalog naming
"""

import threading
import time
from datetime import datetime, timezone
import pytest

from core.clock import FakeClock
from core.max_infra.lock_manager import (
    LockManager,
    LockMode,
    LockTimeoutError,
    ResourceRequest,
    RESOURCE_AUDIO_OUT,
    RESOURCE_DESKTOP_INPUT,
    RESOURCE_GPU_VRAM,
    RESOURCE_SYSTEM_SETTINGS,
    canonical_file_resource,
    canonical_project_resource,
)


def test_exclusive_lock_blocks_concurrent():
    lm = LockManager(default_ttl=5.0)

    with lm.acquire([RESOURCE_DESKTOP_INPUT], task_id="task_gui_1", timeout=0.5):
        assert lm.is_locked(RESOURCE_DESKTOP_INPUT)
        assert lm.get_holder(RESOURCE_DESKTOP_INPUT) == "task_gui_1"

        # Another task attempting to acquire the same exclusive lock should timeout
        with pytest.raises(LockTimeoutError) as exc_info:
            with lm.acquire([RESOURCE_DESKTOP_INPUT], task_id="task_gui_2", timeout=0.1):
                pass
        assert "timed out waiting for lock" in str(exc_info.value)

    # After exit, lock is released
    assert not lm.is_locked(RESOURCE_DESKTOP_INPUT)


def test_shared_locks_permit_concurrent_holders():
    lm = LockManager(default_ttl=5.0)

    # Both task_1 and task_2 acquire gpu-vram in SHARED mode
    req1 = ResourceRequest(RESOURCE_GPU_VRAM, LockMode.SHARED)
    req2 = ResourceRequest(RESOURCE_GPU_VRAM, LockMode.SHARED)

    with lm.acquire([req1], task_id="task_ai_1", timeout=0.5):
        assert lm.is_locked(RESOURCE_GPU_VRAM)
        assert "task_ai_1" in lm.get_holders(RESOURCE_GPU_VRAM)

        with lm.acquire([req2], task_id="task_ai_2", timeout=0.5):
            holders = lm.get_holders(RESOURCE_GPU_VRAM)
            assert "task_ai_1" in holders
            assert "task_ai_2" in holders
            assert lm.get_lock_mode(RESOURCE_GPU_VRAM) == LockMode.SHARED

    assert not lm.is_locked(RESOURCE_GPU_VRAM)


def test_exclusive_blocks_shared_and_vice_versa():
    lm = LockManager(default_ttl=5.0)
    res = "shared_db"

    # 1. Shared held -> Exclusive blocked
    with lm.acquire([(res, LockMode.SHARED)], task_id="reader_1", timeout=0.5):
        with pytest.raises(LockTimeoutError):
            with lm.acquire([(res, LockMode.EXCLUSIVE)], task_id="writer_1", timeout=0.1):
                pass

    # 2. Exclusive held -> Shared blocked
    with lm.acquire([(res, LockMode.EXCLUSIVE)], task_id="writer_1", timeout=0.5):
        with pytest.raises(LockTimeoutError):
            with lm.acquire([(res, LockMode.SHARED)], task_id="reader_1", timeout=0.1):
                pass


def test_dijkstra_canonical_sorting_prevents_deadlock():
    lm = LockManager(default_ttl=10.0)
    res_a = "resource_alpha"
    res_b = "resource_beta"

    t1_started = threading.Event()
    t2_started = threading.Event()
    results = {"t1": False, "t2": False}

    def worker_1():
        # Request in order [B, A]
        with lm.acquire([res_b, res_a], task_id="worker_1", timeout=2.0) as locked:
            assert locked == [res_a, res_b]  # Sorted canonical order
            t1_started.set()
            time.sleep(0.05)
            results["t1"] = True

    def worker_2():
        # Request in order [A, B]
        t1_started.wait()
        with lm.acquire([res_a, res_b], task_id="worker_2", timeout=2.0) as locked:
            assert locked == [res_a, res_b]
            results["t2"] = True

    th1 = threading.Thread(target=worker_1)
    th2 = threading.Thread(target=worker_2)
    th1.start()
    th2.start()
    th1.join(timeout=3.0)
    th2.join(timeout=3.0)

    assert results["t1"] is True
    assert results["t2"] is True


def test_lease_expiry_with_fake_clock():
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)
    lm = LockManager(default_ttl=10.0, clock=clock)

    res = "expiring_res"

    # Manually hold a lock or use acquire
    with lm.acquire([res], task_id="task_holder", timeout=1.0, ttl=5.0):
        assert lm.is_locked(res)
        assert lm.get_holder(res) == "task_holder"

        # Advance clock by 3 seconds - still locked
        clock.advance(seconds=3)
        assert lm.is_locked(res)

        # Advance clock past 5s TTL
        clock.advance(seconds=3)
        # Lock should now be considered expired and reclaimed
        assert not lm.is_locked(res)
        assert lm.get_holder(res) is None


def test_heartbeat_and_lease_renewal():
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)
    lm = LockManager(default_ttl=10.0, clock=clock)

    res = "long_job_res"

    with lm.acquire([res], task_id="long_job", timeout=1.0, ttl=10.0):
        # After 8s, only 2s remain
        clock.advance(seconds=8)
        assert lm.is_locked(res)

        # Heartbeat extends it by another 10s
        renewed = lm.heartbeat(task_id="long_job", additional_ttl=10.0)
        assert res in renewed

        # Advance another 5s (total 13s since start). Without heartbeat it would be dead.
        clock.advance(seconds=5)
        assert lm.is_locked(res)
        assert lm.get_holder(res) == "long_job"


def test_canonical_resource_catalog():
    p1 = canonical_project_resource("F:\\MAX-AGENT\\subfolder")
    assert p1.startswith("project:")
    assert "\\" not in p1

    f1 = canonical_file_resource("F:\\MAX-AGENT\\core\\scheduler.py")
    assert f1.startswith("file:")
    assert "\\" not in f1
