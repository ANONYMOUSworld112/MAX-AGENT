import pytest
from core.reflex.triage import ReflexTriage
from core.reflex.intent_router import ReflexIntentRouter, LaneType
from core.max_infra.task_queue import TaskQueue, TaskItem
from core.max_infra.state_db import StateDB
from core.max_infra.task_lifecycle import TaskState
from core.verification.engine import VerificationEngine
from core.verification.file_verifier import FileVerifier
from agents.router import AgentRegistry
from agents.base import AgentInput


def test_full_autonomous_task_flow(tmp_path):
    # 1. User Natural Language Input
    user_prompt = "Write a python module for user authentication with unit test assertions"

    # 2. Reflex Triage & Lane Routing
    triage = ReflexTriage(fallback_mode=True)
    priority_band = triage.assign_priority(user_prompt)
    assert priority_band in (1, 2)

    router = ReflexIntentRouter(fallback_mode=True)
    decision = router.route_input(user_prompt)
    assert decision.lane == LaneType.LANE_B
    assert decision.is_modifying is True

    # 3. StateDB & TaskQueue Setup
    db = StateDB(db_path=tmp_path / "flow_state.db")
    db.initialize()
    task_queue = TaskQueue()
    task_id = "e2e_full_flow_001"

    db.create_task(
        task_id=task_id,
        agent_name="CodingAgent",
        priority_band=priority_band,
        payload={"goal": user_prompt},
    )

    task_queue.enqueue(TaskItem(
        task_id=task_id,
        priority_band=priority_band,
        agent_name="CodingAgent",
        payload={"description": user_prompt},
    ))
    db.update_task_status(task_id, TaskState.QUEUED.value)

    # 4. Dequeue & Lock Wait
    task = task_queue.dequeue()
    assert task is not None
    db.update_task_status(task_id, TaskState.LOCK_WAIT.value)

    # 5. Agent Execution
    registry = AgentRegistry.get_instance()
    agent = registry.get(task.agent_name)
    assert agent is not None

    db.update_task_status(task_id, TaskState.RUNNING.value)

    target_file = tmp_path / "auth_service.py"
    target_code = "def authenticate(user, pwd):\n    return user == 'admin' and pwd == 'secret'\n"

    agent_input = AgentInput(
        task_id=task_id,
        task_description=user_prompt,
        target_files=[str(target_file)],
        required_resources=[f"file:{target_file}"],
        parameters={"filepath": str(target_file), "code": target_code, "action": "write"},
    )

    output = agent.run(agent_input)
    assert output.success is True

    # 6. Verification Engine
    db.update_task_status(task_id, TaskState.RECONCILING.value)

    file_verifier = FileVerifier()
    rep_exist = file_verifier.verify_files_exist([str(target_file)])
    rep_content = file_verifier.verify_file_content(str(target_file), "authenticate(user, pwd)")

    v_engine = VerificationEngine()
    final_verification = v_engine.evaluate([rep_exist, rep_content])
    assert final_verification.is_verified is True

    # 7. Complete Task
    db.update_task_status(task_id, TaskState.DONE.value, metadata={"result": output.result})
    db.log_trace(task_id, "STEP_E2E", "Full pipeline successfully verified")

    final_task_record = db.get_task(task_id)
    assert final_task_record["status"] == TaskState.DONE.value
    assert "Successfully wrote" in final_task_record["metadata"]["result"]
