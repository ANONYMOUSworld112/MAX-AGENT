import pytest
from PyQt6.QtWidgets import QApplication
from ui.components.task_list_widget import TaskListWidget  # type: ignore


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_task_list_widget_creation(qapp):
    widget = TaskListWidget()
    assert widget.title_lbl.text() == "SWARM TASK QUEUE"

    # Add a task
    widget.add_or_update_task(
        task_id="task_12345",
        description="Run test suite across modules",
        agent="TestWriter",
        status="running",
        elapsed=2.5,
    )
    assert "task_12345" in widget._task_widgets
    assert widget.count_lbl.text() == "1 active"

    # Update to done
    widget.add_or_update_task(
        task_id="task_12345",
        description="Run test suite across modules",
        agent="TestWriter",
        status="done",
        elapsed=5.0,
    )
    assert widget.count_lbl.text() == "0 active"

    # Clear finished
    widget.clear_finished()
    assert len(widget._task_widgets) == 0
