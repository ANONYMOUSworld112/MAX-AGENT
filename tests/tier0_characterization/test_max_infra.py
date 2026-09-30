"""Tier 0 Characterization Test: MAX Infrastructure Modules.

Tests StateDB, LockManager, TaskLifecycleFSM, TaskQueue, KillSwitch,
CircuitBreaker, DataBoundary, and VerificationEngine.
"""
import pytest
import time
from pathlib import Path
from core.max_infra.lock_manager import LockManager, LockTimeoutError
from core.max_infra.task_lifecycle import TaskLifecycleFSM, TaskState, InvalidStateTransitionError
from core.max_infra.task_queue import TaskQueue, TaskItem
from core.max_infra.state_db import StateDB
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError
from core.max_infra.circuit_breaker import CircuitBreaker
from core.max_infra.data_boundary import DataBoundary
from core.verification.engine import VerificationEngine, VerificationReport, VerificationOutcome


def test_lock_manager_sorted_and_timeout():
    lm = LockManager(default_ttl=5.0)

    # Acquire resource A and B
    with lm.acquire(["res_b", "res_a"], task_id="t1", timeout=1.0) as locked:
        assert locked == ["res_a", "res_b"]
        assert lm.is_locked("res_a")
        assert lm.get_holder("res_a") == "t1"

        # Conflicting acquisition should timeout
        with pytest.raises(LockTimeoutError):
            with lm.acquire(["res_a"], task_id="t2", timeout=0.1):
                pass

    # Released after context exit
    assert not lm.is_locked("res_a")
    assert not lm.is_locked("res_b")


def test_task_lifecycle_fsm():
    fsm = TaskLifecycleFSM(task_id="task_1", initial_state=TaskState.CREATED)
    assert fsm.current_state == TaskState.CREATED

    fsm.transition_to(TaskState.QUEUED)
    assert fsm.current_state == TaskState.QUEUED

    fsm.transition_to(TaskState.LOCK_WAIT)
    fsm.transition_to(TaskState.RUNNING)
    fsm.transition_to(TaskState.RECONCILING)
    fsm.transition_to(TaskState.DONE)
    assert fsm.current_state == TaskState.DONE

    # Illegal transition from terminal state
    with pytest.raises(InvalidStateTransitionError):
        fsm.transition_to(TaskState.RUNNING)


def test_task_queue_prioritization_and_aging():
    tq = TaskQueue(aging_threshold_seconds=1.0)

    # Normal priority
    t_normal = TaskItem(task_id="t_norm", priority_band=3, created_at=time.time() - 10.0)
    # Critical priority but created recently
    t_crit = TaskItem(task_id="t_crit", priority_band=1, created_at=time.time())

    tq.enqueue(t_normal)
    tq.enqueue(t_crit)

    # t_normal aged by 10s with threshold 1s => 10 promotions -> effective band 0 (max(0, 3-10))
    # so aged task gets served first or prioritized
    popped = tq.dequeue(timeout=0.1)
    assert popped is not None
    assert popped.task_id == "t_norm"


def test_state_db_initialization_and_tasks(tmp_path: Path):
    db_file = tmp_path / "test_state.db"
    sdb = StateDB(db_path=db_file)
    assert "WAL" in sdb.get_journal_mode().upper()

    tables = sdb.get_tables()
    assert "tasks" in tables
    assert "task_traces" in tables
    assert "resource_locks" in tables
    assert "audit_log" in tables

    # Task creation & status update
    sdb.create_task("task_100", agent_name="CodingAgent", priority_band=1, payload={"cmd": "build"})
    t = sdb.get_task("task_100")
    assert t is not None
    assert t["agent_name"] == "CodingAgent"
    assert t["status"] == "CREATED"
    assert t["payload"]["cmd"] == "build"

    sdb.update_task_status("task_100", "RUNNING", metadata={"progress": 50})
    t_updated = sdb.get_task("task_100")
    assert t_updated["status"] == "RUNNING"
    assert t_updated["metadata"]["progress"] == 50

    sdb.close()


def test_kill_switch_guard():
    ks = KillSwitch.get_instance()
    ks.reset()
    assert not ks.is_tripped()

    ks.guard()  # Should not raise

    ks.trip("Test emergency stop")
    assert ks.is_tripped()

    with pytest.raises(KillSwitchTrippedError):
        ks.guard()

    ks.reset()
    assert not ks.is_tripped()


def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.2)
    target = "test_agent"
    assert cb.is_allowed(target)

    # 3 failures trip it
    cb.record_failure(target)
    cb.record_failure(target)
    assert cb.is_allowed(target)
    cb.record_failure(target)

    assert not cb.is_allowed(target)

    # Cooldown expires
    time.sleep(0.25)
    assert cb.is_allowed(target)

    # Success closes it
    cb.record_success(target)
    assert cb.is_allowed(target)


def test_data_boundary_scrubbing():
    db = DataBoundary()
    raw = "My OpenAI key is sk-1234567890abcdef1234567890 and email is dev@example.com"
    res = db.scrub(raw)
    assert "sk-" not in res.scrubbed_text
    assert "dev@example.com" not in res.scrubbed_text
    assert "[REDACTED_API_KEY_1]" in res.scrubbed_text
    assert "[REDACTED_EMAIL_2]" in res.scrubbed_text

    unscrubbed = db.unscrub(res.scrubbed_text, res.token_map)
    assert unscrubbed == raw


def test_verification_engine_aggregation():
    ve = VerificationEngine()

    r1 = VerificationReport(outcome=VerificationOutcome.SUCCESS, details={"step": 1})
    r2 = VerificationReport(outcome=VerificationOutcome.SUCCESS, details={"step": 2})
    agg = ve.evaluate([r1, r2])
    assert agg.outcome == VerificationOutcome.SUCCESS

    r_fail = VerificationReport(outcome=VerificationOutcome.FAILURE, errors=["Process exited with 1"])
    agg_fail = ve.evaluate([r1, r_fail])
    assert agg_fail.outcome == VerificationOutcome.FAILURE
    assert "Process exited with 1" in agg_fail.errors

    r_unk = VerificationReport(outcome=VerificationOutcome.UNKNOWN, details={"reason": "Window not found"})
    agg_unk = ve.evaluate([r1, r_unk])
    assert agg_unk.outcome == VerificationOutcome.UNKNOWN
