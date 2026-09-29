import pytest
from agents.base import AgentInput
from agents.router import AgentRegistry
from agents.health import (
    SystemMonitorAgent,
    NetworkAgent,
    BackupAgent,
    UpdateAgent,
    PerformanceAgent,
    HealthCheck,
)


def test_cluster_health_agents_instantiation_and_tiers():
    agents = [
        (SystemMonitorAgent(), "SystemMonitorAgent", 0),
        (NetworkAgent(), "NetworkAgent", 0),
        (BackupAgent(), "BackupAgent", 1),
        (UpdateAgent(), "UpdateAgent", 2),
        (PerformanceAgent(), "PerformanceAgent", 0),
        (HealthCheck(), "HealthCheck", 0),
    ]

    registry = AgentRegistry()

    for agent, expected_name, expected_tier in agents:
        assert agent.name == expected_name
        assert agent.permission_tier == expected_tier
        tool_def = agent.get_tool_definition()
        assert tool_def["name"] == expected_name.lower()
        assert "parameters" in tool_def

        registry.register(agent)
        retrieved = registry.get(expected_name)
        assert retrieved is not None
        assert retrieved.name == expected_name


def test_cluster_health_execution_cycle(tmp_path):
    # 1. SystemMonitorAgent
    sys_mon = SystemMonitorAgent()
    out_sys = sys_mon.run(AgentInput(
        task_id="health_1",
        task_description="Collect host performance metrics",
    ))
    assert out_sys.success is True
    assert "metrics" in out_sys.artifacts

    # 2. NetworkAgent
    net = NetworkAgent()
    out_net = net.run(AgentInput(
        task_id="health_2",
        task_description="Check loopback connectivity",
        parameters={"host": "127.0.0.1", "port": 80, "timeout": 0.5},
    ))
    assert out_net.success is True
    assert "status" in out_net.artifacts

    # 3. BackupAgent
    test_file = tmp_path / "config.json"
    test_file.write_text('{"v": 1}', encoding="utf-8")

    backup = BackupAgent()
    out_backup = backup.run(AgentInput(
        task_id="health_3",
        task_description="Backup config.json",
        parameters={"action": "backup", "files": [str(test_file)]},
    ))
    assert out_backup.success is True
    snap_id = out_backup.artifacts["snapshot_id"]

    # Modify file and restore
    test_file.write_text('{"v": 2}', encoding="utf-8")
    out_restore = backup.run(AgentInput(
        task_id="health_3b",
        task_description="Restore config.json",
        parameters={"action": "restore", "snapshot_id": snap_id},
    ))
    assert out_restore.success is True
    assert test_file.read_text(encoding="utf-8") == '{"v": 1}'

    # 4. UpdateAgent
    update = UpdateAgent()
    out_up = update.run(AgentInput(
        task_id="health_4",
        task_description="Check for system package updates",
        parameters={"action": "check"},
    ))
    assert out_up.success is True
    assert out_up.artifacts["requires_confirmation"] is True

    # 5. PerformanceAgent
    perf = PerformanceAgent()
    out_perf = perf.run(AgentInput(
        task_id="health_5",
        task_description="Profile system dispatch latency",
        parameters={"component": "IntentRouter"},
    ))
    assert out_perf.success is True
    assert out_perf.artifacts["status"] == "OPTIMAL"

    # 6. HealthCheck
    hc = HealthCheck()
    out_hc = hc.run(AgentInput(
        task_id="health_6",
        task_description="Run full subsystem integrity check",
    ))
    assert out_hc.success is True
    assert out_hc.artifacts["overall_health"] == "HEALTHY"
