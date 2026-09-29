import pytest
from agents.base import AgentInput
from agents.router import AgentRegistry
from agents.safety import (
    ComputerUseAgent,
    DesktopAgent,
    BrowserAgent,
    InputArbiter,
    SecurityGate,
    RecoveryEngine,
)
from core.max_infra.kill_switch import KillSwitch


def test_cluster_safety_agents_instantiation_and_tiers():
    agents = [
        (ComputerUseAgent(), "ComputerUseAgent", 2),
        (DesktopAgent(), "DesktopAgent", 1),
        (BrowserAgent(), "BrowserAgent", 1),
        (InputArbiter(), "InputArbiter", 2),
        (SecurityGate(), "SecurityGate", 3),
        (RecoveryEngine(), "RecoveryEngine", 0),
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


def test_cluster_safety_execution_cycle():
    # 1. ComputerUseAgent
    cua = ComputerUseAgent()
    out_cua = cua.run(AgentInput(
        task_id="safe_1",
        task_description="Click Submit button in CRM",
        parameters={"action": "click", "target": "Submit Button"},
    ))
    assert out_cua.success is True
    assert out_cua.artifacts["loop_stages"] == ["OBSERVE", "THINK", "ACT", "VERIFY"]

    # 2. DesktopAgent
    desk = DesktopAgent()
    out_desk = desk.run(AgentInput(
        task_id="safe_2",
        task_description="Bring Visual Studio Code to focus",
        parameters={"action": "focus", "app": "Code"},
    ))
    assert out_desk.success is True
    assert out_desk.artifacts["window_state"] == "MODIFIED"

    # 3. BrowserAgent
    browser = BrowserAgent()
    out_browser = browser.run(AgentInput(
        task_id="safe_3",
        task_description="Navigate to documentation",
        parameters={"action": "navigate", "url": "https://docs.python.org"},
    ))
    assert out_browser.success is True
    assert out_browser.artifacts["url"] == "https://docs.python.org"

    # 4. InputArbiter
    arb = InputArbiter()
    out_arb = arb.run(AgentInput(
        task_id="safe_4",
        task_description="Acquire input focus for agent",
        parameters={"action": "acquire", "agent": "ComputerUseAgent"},
    ))
    assert out_arb.success is True
    assert out_arb.artifacts["holder"] == "ComputerUseAgent"

    # 5. SecurityGate (Safe query)
    gate = SecurityGate()
    out_gate_safe = gate.run(AgentInput(
        task_id="safe_5a",
        task_description="Read system memory metrics",
    ))
    assert out_gate_safe.success is True
    assert out_gate_safe.artifacts["is_safe"] is True

    # 5b. SecurityGate (Blocked command)
    out_gate_blocked = gate.run(AgentInput(
        task_id="safe_5b",
        task_description="format c: /q",
    ))
    assert out_gate_blocked.success is False
    assert "SECURITY_ALERT" in out_gate_blocked.error

    # 6. RecoveryEngine
    rec = RecoveryEngine()
    out_rec1 = rec.run(AgentInput(
        task_id="safe_6a",
        task_description="Window element not found",
        parameters={"attempt": 1},
    ))
    assert out_rec1.success is True
    assert out_rec1.artifacts["recommended_step"] == "re-observe"

    out_rec8 = rec.run(AgentInput(
        task_id="safe_6b",
        task_description="Window element permanently missing",
        parameters={"attempt": 8},
    ))
    assert out_rec8.success is True
    assert out_rec8.artifacts["recommended_step"] == "ask_user"
    assert out_rec8.artifacts["escalate_to_user"] is True
