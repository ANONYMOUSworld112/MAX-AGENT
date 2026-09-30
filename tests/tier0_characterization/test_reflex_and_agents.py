"""Tier 0 Characterization Test: Reflex Engine & Agent Registry.

Tests ReflexGuardrails, ReflexIntentRouter, and AgentRegistry.
"""
from core.reflex.guardrails import ReflexGuardrails, RiskTier
from core.reflex.intent_router import ReflexIntentRouter, LaneType
from agents.router import AgentRegistry
from agents.base import AgentInput


def test_reflex_guardrails_classification():
    rg = ReflexGuardrails(fallback_mode=True)

    # Tier 3 Hard-blocked
    r_blocked = rg.check_safety("Please format c: and delete system")
    assert r_blocked.risk_tier == RiskTier.TIER_3_HARD_BLOCKED
    assert not r_blocked.is_safe

    # Tier 2 Confirm on write
    r_confirm = rg.check_safety("delete the old archive folder")
    assert r_confirm.risk_tier == RiskTier.TIER_2_CONFIRM_ON_WRITE
    assert r_confirm.is_safe

    # Tier 1 Safe write
    r_safe_write = rg.check_safety("create a new scratchpad file")
    assert r_safe_write.risk_tier == RiskTier.TIER_1_SAFE_WRITE

    # Tier 0 Auto / Read-only
    r_auto = rg.check_safety("what is the weather today?")
    assert r_auto.risk_tier == RiskTier.TIER_0_AUTO


def test_reflex_intent_router():
    router = ReflexIntentRouter()

    # Read/query tools map to Lane A
    intent_a = router.route("system_status", {})
    assert intent_a.lane == LaneType.LANE_A

    # Modifying/task execution routes to Lane B
    intent_b = router.route("codingagent", {"instruction": "write python function to process files"})
    assert intent_b.lane == LaneType.LANE_B
    assert intent_b.is_modifying is True


def test_agent_registry_contains_33_agents():
    registry = AgentRegistry.get_instance()
    all_agents = registry.list_all()

    # Verify registration count
    assert len(all_agents) == 33

    # Check key agents by canonical name and alias
    assert registry.get("codingagent") is not None
    assert registry.get("polyglotdeveloper") is not None  # alias
    assert registry.get("calendaragent") is not None
    assert registry.get("securitygate") is not None
    assert registry.get("computeruseagent") is not None

    # Verify BaseAgent tool definition generation
    coding_tool = registry.get("codingagent").get_tool_definition()
    assert coding_tool["name"] == "codingagent"
    assert "parameters" in coding_tool


def test_agent_stub_execution_behavior():
    """Characterizes the existing agent stub execution (noting mocked outcomes)."""
    registry = AgentRegistry.get_instance()
    cal_agent = registry.get("calendaragent")

    inp = AgentInput(
        task_id="test_cal_1",
        task_description="Schedule meeting with Alice tomorrow at 3pm",
        parameters={"title": "Alice sync", "start_time": "2026-10-01T15:00:00"},
    )
    out = cal_agent.run(inp)
    assert out.success is True
    assert "Alice sync" in out.result
    # Baseline characterization: calendar agent returns CONFIRMED without interacting with real calendar
    assert out.artifacts.get("status") == "CONFIRMED"
