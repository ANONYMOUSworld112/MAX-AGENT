import pytest
from pydantic import BaseModel
from agents.base import BaseAgent, AgentInput, AgentOutput
from core.max_infra.lock_manager import LockManager
from core.max_infra.circuit_breaker import CircuitBreaker

class DummyAgent(BaseAgent):
    name = "DummyAgent"
    description = "A dummy agent for testing base lifecycle"

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        return AgentOutput(
            success=True,
            result=f"Handled: {input_data.task_description}",
            artifacts={"output_val": 42}
        )

def test_base_agent_execution_cycle():
    agent = DummyAgent()
    inp = AgentInput(
        task_id="task-dummy-01",
        task_description="Execute test",
        parameters={"foo": "bar"}
    )
    output = agent.run(inp)
    assert output.success is True
    assert "Handled: Execute test" in output.result
    assert output.artifacts["output_val"] == 42

def test_base_agent_tool_definition():
    agent = DummyAgent()
    tool_def = agent.get_tool_definition()
    assert tool_def["name"] == "dummyagent"
    assert "description" in tool_def
    assert "parameters" in tool_def
