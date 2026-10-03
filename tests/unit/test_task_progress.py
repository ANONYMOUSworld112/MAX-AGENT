"""
Unit tests for TaskProgressWidget (Phase 11: Task 11.1)
======================================================
"""

import os
import sys
import threading
import time
import pytest

# Ensure headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from ui.components.task_progress_widget import TaskProgressWidget, _get_or_create_qapp
from core.events import EventBus
from core.contracts import EventEnvelope


@pytest.fixture(scope="module")
def qapp():
    return _get_or_create_qapp()


def test_widget_initialization(qapp):
    widget = TaskProgressWidget()
    assert widget.count() == 0
    assert widget.get_active_tasks() == []
    assert widget.get_task_progress("non-existent") is None


def test_direct_progress_update(qapp):
    widget = TaskProgressWidget()
    
    # Step 1 of 5
    widget.update_task_progress(
        task_id="task-001",
        step_index=1,
        total_steps=5,
        step_name="Cloning repository",
        worker_status="RUNNING",
        verification_status="PENDING",
        description="Build App Feature",
    )
    
    data = widget.get_task_progress("task-001")
    assert data is not None
    assert data["step_index"] == 1
    assert data["total_steps"] == 5
    assert data["progress_pct"] == 20
    assert data["step_name"] == "Cloning repository"
    assert data["worker_status"] == "RUNNING"
    assert "task-001" in widget.get_active_tasks()

    # Advance to Step 3 of 5
    widget.update_task_progress(
        task_id="task-001",
        step_index=3,
        total_steps=5,
        step_name="Running automated test suite",
        worker_status="RUNNING",
        verification_status="VERIFIED",
    )
    data2 = widget.get_task_progress("task-001")
    assert data2["step_index"] == 3
    assert data2["progress_pct"] == 60
    assert data2["step_name"] == "Running automated test suite"
    assert data2["verification_status"] == "VERIFIED"


def test_event_bus_subscription_flow(qapp):
    bus = EventBus()
    widget = TaskProgressWidget(event_bus=bus)

    # 1. task.created
    bus.publish(
        EventEnvelope(
            event_type="task.created",
            correlation_id="task-abc-123",
            payload={"description": "Deploy to staging", "total_steps": 4},
        )
    )
    # Process Qt event loop
    qapp.processEvents()

    prog = widget.get_task_progress("task-abc-123")
    assert prog is not None
    assert prog["step_index"] == 0
    assert prog["total_steps"] == 4
    assert prog["worker_status"] == "PENDING"

    # 2. task.progress (Step 2 of 4)
    bus.publish(
        EventEnvelope(
            event_type="task.progress",
            correlation_id="task-abc-123",
            payload={
                "step_index": 2,
                "total_steps": 4,
                "step_name": "Running health checks",
                "worker_status": "RUNNING",
                "verification_status": "PENDING",
            },
        )
    )
    qapp.processEvents()

    prog = widget.get_task_progress("task-abc-123")
    assert prog["step_index"] == 2
    assert prog["progress_pct"] == 50
    assert prog["step_name"] == "Running health checks"

    # 3. verification.completed
    bus.publish(
        EventEnvelope(
            event_type="verification.completed",
            correlation_id="task-abc-123",
            payload={"outcome": "VERIFIED"},
        )
    )
    qapp.processEvents()

    prog = widget.get_task_progress("task-abc-123")
    assert prog["verification_status"] == "VERIFIED"

    # 4. task.completed
    bus.publish(
        EventEnvelope(
            event_type="task.completed",
            correlation_id="task-abc-123",
            payload={"verification_status": "VERIFIED"},
        )
    )
    qapp.processEvents()

    prog = widget.get_task_progress("task-abc-123")
    assert prog["worker_status"] == "COMPLETED"
    assert prog["progress_pct"] == 100
    assert "task-abc-123" not in widget.get_active_tasks()


def test_rapid_event_bursts(qapp):
    """Verify that hundreds of rapid events from multiple threads do not crash the widget."""
    bus = EventBus()
    widget = TaskProgressWidget(event_bus=bus)

    num_tasks = 20
    steps_per_task = 5

    def emit_worker(tid):
        for s in range(1, steps_per_task + 1):
            bus.publish(
                EventEnvelope(
                    event_type="task.progress",
                    correlation_id=f"burst-{tid}",
                    payload={
                        "step_index": s,
                        "total_steps": steps_per_task,
                        "step_name": f"Sub-step {s}",
                        "worker_status": "RUNNING",
                    },
                )
            )

    threads = [threading.Thread(target=emit_worker, args=(i,)) for i in range(num_tasks)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Flush Qt event loop
    qapp.processEvents()

    assert widget.count() == num_tasks
    for i in range(num_tasks):
        data = widget.get_task_progress(f"burst-{i}")
        assert data is not None
        assert data["step_index"] == steps_per_task
        assert data["progress_pct"] == 100


def test_clear_finished(qapp):
    widget = TaskProgressWidget()
    
    # 1 active task
    widget.update_task_progress("active-1", 1, 2, worker_status="RUNNING")
    
    # 2 completed tasks
    widget.update_task_progress("done-1", 2, 2, worker_status="COMPLETED")
    widget.update_task_progress("failed-1", 1, 2, worker_status="FAILED")

    assert widget.count() == 3
    cleared = widget.clear_finished()
    assert cleared == 2
    assert widget.count() == 1
    assert "active-1" in widget.get_active_tasks()
