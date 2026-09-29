import os
import tempfile
import pytest
from core.confirm import bind, request, resolve, pending_title
from core.undo import push_undo, undo_last, can_undo, clear
from core.max_infra.snapshot import SnapshotEngine

def test_confirm_flow():
    shown = []
    bind(
        show=lambda t, d: shown.append((t, d)),
        hide=lambda: shown.clear(),
        log=lambda m: None
    )

    executed = []
    resp = request("t1", "Delete database", "Drop all tables", lambda: executed.append(1))
    assert "[CONFIRMATION_PENDING]" in resp
    assert len(shown) == 1
    assert pending_title() == "Delete database"

    # User confirms
    resolve(accepted=True)
    import time
    time.sleep(0.1) # allow worker thread to run
    assert len(executed) == 1
    assert pending_title() == ""

def test_undo_with_snapshot(tmp_path):
    clear()
    engine = SnapshotEngine(base_snapshot_dir=str(tmp_path / ".snapshots"))
    test_file = tmp_path / "hello.py"
    test_file.write_text("v1", encoding="utf-8")

    snap_id = engine.capture_snapshot("task-undo-1", [str(test_file)])
    test_file.write_text("v2", encoding="utf-8")

    push_undo("Edit hello.py", lambda: "Rolled back" if engine.rollback(snap_id) else "Failed")
    assert can_undo() is True

    res = undo_last()
    assert "Undone: Edit hello.py" in res
    assert test_file.read_text(encoding="utf-8") == "v1"
