import pytest
from core.max_infra.task_queue import TaskQueue, TaskItem
from core.max_infra.state_db import StateDB
from core.max_infra.task_lifecycle import TaskState
from agents.router import AgentRegistry
from agents.base import AgentInput


def test_task_queue_to_agent_dispatch(tmp_path):
    # Initialize isolated StateDB and TaskQueue
    db = StateDB(db_path=tmp_path / "test_state.db")
    db.initialize()
    queue = TaskQueue()
    registry = AgentRegistry.get_instance()

    task_id = "task_dispatch_100"
    db.create_task(
        task_id=task_id,
        agent_name="DependencyMgr",
        priority_band=1,
        payload={"goal": "Audit dependencies for vulnerabilities"},
    )

    task_item = TaskItem(
        task_id=task_id,
        priority_band=1,
        agent_name="DependencyMgr",
        payload={"description": "Audit project packages"},
    )
    queue.enqueue(task_item)
    assert queue.size() == 1

    # Dequeue highest priority task
    popped = queue.dequeue()
    assert popped is not None
    assert popped.task_id == task_id

    # Select agent from registry
    agent = registry.get(popped.agent_name)
    assert agent is not None

    # Update lifecycle in StateDB to RUNNING
    db.update_task_status(task_id, TaskState.RUNNING.value)

    # Execute
    output = agent.run(AgentInput(
        task_id=task_id,
        task_description=popped.payload["description"],
    ))
    assert output.success is True

    # Record completion in StateDB
    db.update_task_status(task_id, TaskState.DONE.value, metadata={"result": output.result})
    db.log_trace(task_id, "STEP_AUDIT", "Audit completed successfully")

    task_record = db.get_task(task_id)
    assert task_record["status"] == TaskState.DONE.value
    assert "Dependency audit completed" in task_record["metadata"]["result"]
