import os
import tempfile
import pytest
from core.max_infra.snapshot import SnapshotEngine

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)

def test_snapshot_capture_and_rollback(temp_dir: str):
    engine = SnapshotEngine(base_snapshot_dir=os.path.join(temp_dir, ".snapshots"))
    
    file_a = os.path.join(temp_dir, "auth.py")
    with open(file_a, "w", encoding="utf-8") as f:
        f.write("def login(): return 'original'")

    # Capture snapshot
    snap_id = engine.capture_snapshot(task_id="task-100", file_paths=[file_a])
    assert snap_id is not None

    # Corrupt or modify file
    with open(file_a, "w", encoding="utf-8") as f:
        f.write("def login(): return 'corrupted'")
    assert open(file_a).read() == "def login(): return 'corrupted'"

    # Execute rollback
    ok = engine.rollback(snap_id)
    assert ok is True
    assert open(file_a).read() == "def login(): return 'original'"

def test_snapshot_rollback_newly_created_file(temp_dir: str):
    engine = SnapshotEngine(base_snapshot_dir=os.path.join(temp_dir, ".snapshots"))
    file_new = os.path.join(temp_dir, "brand_new.py")
    
    # Capture snapshot before it exists
    snap_id = engine.capture_snapshot(task_id="task-101", file_paths=[file_new])
    
    # File created during task
    with open(file_new, "w", encoding="utf-8") as f:
        f.write("brand new content")
    assert os.path.exists(file_new)

    # Rollback should remove the newly created file
    engine.rollback(snap_id)
    assert not os.path.exists(file_new)
