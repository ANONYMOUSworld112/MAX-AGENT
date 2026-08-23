"""
Tests for platform detection, risk engine, task queue, command risk classifier, and tool backends integrated from files directory.
"""
import pytest
from core.platform.detector import (
    ControlLevel,
    DisplayServer,
    OSFamily,
    RiskLevel,
    detect_capability_profile,
)
from core.risk_engine import ActionDecision, ActionRequest, RiskEngine
from tasks.task_system import AgentState, Task, TaskQueue
from tools.command_classifier import classify_command_risk
from tools.backends.filesystem_local import LocalFilesystemTool
from tools.backends.terminal_subprocess import SubprocessTerminalTool


def test_platform_detector_critical_gate():
    profile = detect_capability_profile()
    assert profile.can_run_autonomously(RiskLevel.CRITICAL) is False
    assert profile.os_family in (OSFamily.WINDOWS, OSFamily.LINUX, OSFamily.MACOS, OSFamily.UNKNOWN)


def test_risk_engine_critical_enforcement():
    def mock_confirmation(request: ActionRequest) -> bool:
        return True

    engine = RiskEngine(confirmation_callback=mock_confirmation)
    req = ActionRequest(
        description="Format hard drive",
        risk=RiskLevel.CRITICAL,
        agent="system",
        task_id="test-1",
    )
    decision = engine.enforce(req)
    assert decision.autonomous is False
    assert decision.approved is True
    assert "CRITICAL" in decision.reason


def test_task_queue_priority_and_dependency():
    tq = TaskQueue()
    t1 = Task(description="Step 1", agent="coding", risk=RiskLevel.LOW, priority=1)
    t2 = Task(
        description="Step 2",
        agent="deploy",
        risk=RiskLevel.MEDIUM,
        priority=1,
        depends_on=[t1.id],
    )
    tq.add(t1)
    tq.add(t2)

    # t2 depends on t1 so t2 cannot run yet
    eligible = tq.pop_next_eligible()
    assert eligible is not None
    assert eligible.id == t1.id

    # Complete t1
    t1.state = AgentState.COMPLETED

    eligible2 = tq.pop_next_eligible()
    assert eligible2 is not None
    assert eligible2.id == t2.id


def test_command_risk_classifier():
    assert classify_command_risk("rm -rf /") == RiskLevel.CRITICAL
    assert classify_command_risk("sudo apt update") == RiskLevel.CRITICAL
    assert classify_command_risk("rm file.txt") == RiskLevel.HIGH
    assert classify_command_risk("git push --force") == RiskLevel.HIGH
    assert classify_command_risk("git commit -m 'test'") == RiskLevel.MEDIUM
    assert classify_command_risk("ls -la") == RiskLevel.LOW


def test_filesystem_tool_read_write_delete(tmp_path):
    tool = LocalFilesystemTool()
    test_file = tmp_path / "sample.txt"

    tool.write(str(test_file), b"Hello MAX OS")
    assert test_file.exists()
    assert tool.read(str(test_file)) == b"Hello MAX OS"

    tool.delete(str(test_file))
    assert not test_file.exists()


def test_terminal_tool_execution():
    tool = SubprocessTerminalTool()
    res = tool.run("echo 'MAX OS Test'")
    assert res.returncode == 0
    assert "MAX OS Test" in res.stdout


def test_agent_executors_and_orchestrator():
    from core.orchestrator import Orchestrator
    orch = Orchestrator(
        risk_engine=RiskEngine(confirmation_callback=lambda req: True),
        log_dir="logs/test_orch",
    )
    assert "terminal" in orch._agents
    assert "filesystem" in orch._agents
    assert "browser" in orch._agents
    assert "computer_use" in orch._agents

