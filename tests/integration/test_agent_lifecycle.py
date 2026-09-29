import pytest
from agents.base import AgentInput, AgentOutput
from agents.software.coding_agent import CodingAgent
from core.max_infra.circuit_breaker import CircuitBreaker
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError
from core.max_infra.lock_manager import LockManager
from core.max_infra.snapshot import SnapshotEngine
from core.max_infra.reconciliation import ReconciliationEngine


def test_agent_full_lifecycle_envelope(tmp_path):
    lock_mgr = LockManager()
    cb = CircuitBreaker()
    snapshot = SnapshotEngine(base_snapshot_dir=tmp_path / "snapshots")
    reconciliation = ReconciliationEngine()

    agent = CodingAgent(
        lock_manager=lock_mgr,
        circuit_breaker=cb,
        snapshot_engine=snapshot,
        reconciliation_engine=reconciliation,
    )

    target_file = tmp_path / "module.py"
    target_file.write_text("# Initial code\n", encoding="utf-8")

    agent_input = AgentInput(
        task_id="lifecycle_1",
        task_description="Update module with helper function",
        target_files=[str(target_file)],
        required_resources=[f"file:{target_file}"],
        parameters={
            "filepath": str(target_file),
            "code": "# Initial code\ndef helper(): return 42\n",
            "action": "write",
        },
    )

    # 1. Run lifecycle
    output = agent.run(agent_input)
    assert output.success is True
    assert "Successfully wrote" in output.result
    assert "def helper()" in target_file.read_text(encoding="utf-8")

    # 2. Verify circuit breaker recorded success
    assert cb.is_allowed(agent.name) is True

    # 3. Verify kill switch stops execution
    ks = KillSwitch.get_instance()
    try:
        ks.trip("Emergency test trip")
        with pytest.raises(KillSwitchTrippedError):
            agent.run(agent_input)
    finally:
        ks.reset()
