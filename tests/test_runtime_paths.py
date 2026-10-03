from pathlib import Path

from core.max_infra.snapshot import SnapshotEngine


def test_snapshot_engine_uses_repo_path_for_default_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    engine = SnapshotEngine()
    expected = (Path(__file__).resolve().parents[1] / ".snapshots")
    assert engine.base_dir == expected
