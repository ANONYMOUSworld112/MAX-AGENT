import asyncio
import pytest
from unittest.mock import MagicMock
from core.reflex.intent_router import ReflexIntentRouter, LaneType
from agents.router import AgentRegistry
from agents.base import AgentInput


@pytest.fixture
def agent_registry():
    return AgentRegistry.get_instance()


@pytest.fixture
def intent_router():
    return ReflexIntentRouter(fallback_mode=True)


def test_dual_lane_intent_router(intent_router):
    # Lane A: fast reads / status
    res_a = intent_router.route_input("What is the current CPU temperature?")
    assert res_a.lane == LaneType.LANE_A

    # Lane B: modifying developer task
    res_b = intent_router.route_input("Refactor and write unit tests for the auth module")
    assert res_b.lane == LaneType.LANE_B
    assert res_b.is_modifying is True


def test_agent_registry_tool_declarations(agent_registry):
    tool_defs = agent_registry.get_all_tool_definitions()
    assert len(tool_defs) == 33
    tool_names = [td["name"] for td in tool_defs]
    assert "codingagent" in tool_names
    assert "emailagent" in tool_names
    assert "systemmonitoragent" in tool_names
    assert "computeruseagent" in tool_names


@pytest.mark.asyncio
async def test_dual_lane_mock_execution(agent_registry, intent_router):
    loop = asyncio.get_running_loop()

    # Simulate tool call to CodingAgent
    tool_name = "codingagent"
    args = {"task_description": "Create sample test component", "action": "generate"}

    agent = agent_registry.get(tool_name)
    assert agent is not None

    agent_input = AgentInput(
        task_id="dual_lane_test_1",
        task_description=args["task_description"],
        parameters=args,
    )

    output = await loop.run_in_executor(None, agent.run, agent_input)
    assert output.success is True
    assert "sample test component" in output.result


@pytest.mark.asyncio
async def test_dual_lane_router_dispatch(agent_registry, intent_router):
    loop = asyncio.get_running_loop()

    # Given an unmapped tool name that expresses modifying developer intent
    unmapped_tool = "custom_dev_task"
    args = {"task_description": "Refactor python function with pytest"}

    decision = intent_router.route(unmapped_tool, args)
    assert decision.lane == LaneType.LANE_B

    target_agent_name = decision.target_agent
    target_agent = agent_registry.get(target_agent_name)
    # If target_agent is e.g. PolyglotDeveloper or MasterOrchestrator
    if not target_agent:
        target_agent = agent_registry.get("MasterOrchestrator")

    assert target_agent is not None
    output = await loop.run_in_executor(
        None,
        target_agent.run,
        AgentInput(task_id="dual_lane_test_2", task_description=args["task_description"]),
    )
    assert output.success is True
