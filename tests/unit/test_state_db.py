import os
import tempfile
import pytest
from core.max_infra.state_db import StateDB

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = StateDB(path)
    db.initialize()
    yield db
    db.close()
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

def test_state_db_initialization(temp_db: StateDB):
    mode = temp_db.get_journal_mode()
    assert mode.lower() == "wal"

    tables = temp_db.get_tables()
    expected = {"tasks", "task_traces", "resource_locks", "circuit_breakers", "memory_layers", "snapshots", "audit_log"}
    assert expected.issubset(set(tables))

def test_task_lifecycle_crud(temp_db: StateDB):
    task_id = "task-001"
    temp_db.create_task(
        task_id=task_id,
        agent_name="PolyglotDeveloper",
        priority_band=2,
        payload={"action": "refactor", "file": "auth.py"}
    )

    task = temp_db.get_task(task_id)
    assert task is not None
    assert task["agent_name"] == "PolyglotDeveloper"
    assert task["status"] == "CREATED"
    assert task["priority_band"] == 2

    temp_db.update_task_status(task_id, "RUNNING", metadata={"worker_pid": 1234})
    updated = temp_db.get_task(task_id)
    assert updated["status"] == "RUNNING"

def test_trace_logging(temp_db: StateDB):
    task_id = "task-002"
    temp_db.create_task(task_id, "SystemArchitect", 1, {})
    temp_db.log_trace(task_id, "STEP_PLAN", "Created architectural blueprint")

    traces = temp_db.get_traces(task_id)
    assert len(traces) == 1
    assert traces[0]["step"] == "STEP_PLAN"
