import asyncio
import pytest
from unittest.mock import MagicMock
from google.genai import types
from agents.router import AgentRegistry
from agents.base import AgentInput
from core.max_infra.kill_switch import KillSwitch


@pytest.fixture(autouse=True)
def reset_kill_switch_state():
    ks = KillSwitch.get_instance()
    ks.reset()
    yield
    ks.reset()


class MockFunctionCall:
    def __init__(self, name: str, args: dict, call_id: str = "call_mock_123"):
        self.name = name
        self.args = args
        self.id = call_id


@pytest.mark.asyncio
async def test_voice_tool_call_to_agent():
    """Simulates Gemini Live sending a function call for an agent tool."""
    registry = AgentRegistry.get_instance()
    agent = registry.get("CodingAgent")
    assert agent is not None

    loop = asyncio.get_running_loop()

    # Mock tool call from Gemini session
    fc = MockFunctionCall(
        name="codingagent",
        args={
            "task_description": "Create a secure utility function",
            "action": "generate",
        },
    )

    # Route and execute as main.py does in _execute_tool
    target_agent = registry.get(fc.name)
    assert target_agent is not None

    agent_input = AgentInput(
        task_id=f"voice_task_{fc.id}",
        task_description=fc.args.get("task_description", ""),
        parameters=fc.args,
    )

    output = await loop.run_in_executor(None, target_agent.run, agent_input)
    assert output.success is True
    assert "Code generation completed" in output.result

    response = types.FunctionResponse(
        id=fc.id,
        name=fc.name,
        response={"result": output.result},
    )
    assert response.name == "codingagent"
    assert "Code generation completed" in response.response["result"]
