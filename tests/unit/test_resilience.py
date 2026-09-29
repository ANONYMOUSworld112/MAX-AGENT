import time
import pytest
from core.max_infra.circuit_breaker import CircuitBreaker, CircuitState
from core.max_infra.watchdog import Watchdog
from core.max_infra.reconciliation import ReconciliationEngine

def test_circuit_breaker_tripping_and_cooldown():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.2)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_allowed("test_agent") is True

    # Record 3 failures
    cb.record_failure("test_agent")
    cb.record_failure("test_agent")
    cb.record_failure("test_agent")

    # Circuit should now be OPEN
    assert cb.state == CircuitState.OPEN
    assert cb.is_allowed("test_agent") is False

    # Wait for cooldown
    time.sleep(0.25)
    # Should be HALF_OPEN
    assert cb.is_allowed("test_agent") is True
    
    # Success closes the circuit
    cb.record_success("test_agent")
    assert cb.state == CircuitState.CLOSED

def test_watchdog_timeout_detection():
    timed_out_tasks = []
    wd = Watchdog(check_interval=0.05, timeout_callback=lambda tid: timed_out_tasks.append(tid))
    wd.start()

    # Register task with 0.1s timeout
    wd.register_heartbeat("task-fast-timeout", timeout_seconds=0.1)
    time.sleep(0.25)

    assert "task-fast-timeout" in timed_out_tasks
    wd.stop()

def test_reconciliation_engine(tmp_path):
    recon = ReconciliationEngine()
    test_file = tmp_path / "created.py"
    test_file.write_text("print('hello')", encoding="utf-8")

    # Reconciliation succeeds when file exists and non-empty
    report = recon.verify_files_exist([str(test_file)])
    assert report.is_verified is True

    # Reconciliation fails when expected file missing
    report_missing = recon.verify_files_exist([str(tmp_path / "missing.py")])
    assert report_missing.is_verified is False
