import pytest
from agents.base import AgentInput
from agents.core.orchestrator import MasterOrchestrator
from agents.core.planner import DecompositionPlanner
from agents.core.verifier import ValidationVerifier
from agents.core.model_router import ModelRouter
from agents.core.critic import AdversarialCritic

def test_cluster_core_agents():
    # 1. Orchestrator
    orch = MasterOrchestrator()
    out = orch.run(AgentInput(task_id="t1", task_description="Coordinate refactoring auth.py"))
    assert out.success is True

    # 2. Planner
    planner = DecompositionPlanner()
    out_plan = planner.run(AgentInput(task_id="t2", task_description="Build JWT auth feature"))
    assert out_plan.success is True
    assert "subtasks" in out_plan.artifacts

    # 3. Verifier
    verifier = ValidationVerifier()
    out_ver = verifier.run(AgentInput(task_id="t3", task_description="Verify unit tests pass", parameters={"exit_code": 0}))
    assert out_ver.success is True
    assert out_ver.artifacts["verdict"] == "PASS"

    # 4. Model Router
    mrouter = ModelRouter()
    out_mr = mrouter.run(AgentInput(task_id="t4", task_description="Select model for real-time voice"))
    assert out_mr.success is True
    assert out_mr.artifacts["selected_model"] == "gemini-2.5-flash"

    # 5. Critic
    critic = AdversarialCritic()
    out_crit = critic.run(AgentInput(task_id="t5", task_description="Critique plan", parameters={"plan": ["Step 1: delete root", "Step 2: restart"]}))
    assert out_crit.success is True
    assert "critique" in out_crit.artifacts
