import pytest
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError
from core.max_infra.snapshot import SnapshotEngine
from core.max_infra.lock_manager import LockManager
from core.max_infra.circuit_breaker import CircuitBreaker
from core.max_infra.reconciliation import ReconciliationEngine
from agents.software.coding_agent import CodingAgent
from agents.safety.input_arbiter import InputArbiter
from agents.base import AgentInput


@pytest.fixture(autouse=True)
def reset_kill_switch_state():
    ks = KillSwitch.get_instance()
    ks.reset()
    yield
    ks.reset()


def test_kill_switch_cascade_rollback(tmp_path):
    ks = KillSwitch.get_instance()
    ks.reset()

    snap_engine = SnapshotEngine(base_snapshot_dir=tmp_path / "snapshots")
    agent = CodingAgent(
        lock_manager=LockManager(),
        circuit_breaker=CircuitBreaker(),
        snapshot_engine=snap_engine,
        reconciliation_engine=ReconciliationEngine(),
    )

    arbiter = InputArbiter()

    # Step 1: InputArbiter acquires input
    res_input = arbiter.run(AgentInput(
        task_id="ks_task_1",
        task_description="Acquire lease",
        parameters={"action": "acquire", "agent": "CodingAgent"},
    ))
    assert res_input.success is True

    # Step 2: Trip KillSwitch
    try:
        ks.trip("Emergency Red Button Pressed")

        # Step 3: All agents must immediately reject tasks via BaseAgent lifecycle
        with pytest.raises(KillSwitchTrippedError):
            agent.run(AgentInput(
                task_id="ks_task_2",
                task_description="Attempt write during shutdown",
            ))

        # Step 4: Input arbiter execution is blocked by KillSwitch guard
        with pytest.raises(KillSwitchTrippedError):
            arbiter.run(AgentInput(
                task_id="ks_task_3",
                task_description="Attempt input lease during emergency",
                parameters={"action": "acquire", "agent": "CodingAgent"},
            ))
    finally:
        ks.reset()
