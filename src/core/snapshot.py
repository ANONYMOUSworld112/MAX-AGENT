"""
MAX OS — Task Snapshot & Rollback Manager
Build Order: #9 (Layer 2D)
═══════════════════════════════════════════════════════

Captures state snapshots before running destructive or file-modifying tasks.
On task failure or kill signal, executes full rollback to clean state.
"""

from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("max.core.snapshot")

SNAPSHOT_DIR = Path.home() / ".max_os" / "snapshots"


class SnapshotManager:
    """Manages file and workspace snapshots for task rollback."""

    def __init__(self):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, task_id: str, paths: list[str | Path]) -> Path:
        """Create a backup snapshot of specified paths."""
        task_snap_dir = SNAPSHOT_DIR / task_id
        task_snap_dir.mkdir(parents=True, exist_ok=True)

        for path in paths:
            p = Path(path)
            if not p.exists():
                continue
            dest = task_snap_dir / p.name
            if p.is_dir():
                shutil.copytree(p, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(p, dest)

        logger.info("Created snapshot for task '%s' at %s", task_id, task_snap_dir)
        return task_snap_dir

    def rollback(self, task_id: str, paths_map: dict[str, str]) -> bool:
        """Restore original files from snapshot."""
        task_snap_dir = SNAPSHOT_DIR / task_id
        if not task_snap_dir.exists():
            logger.warning("No snapshot found for task '%s' to rollback", task_id)
            return False

        try:
            for original_path, snap_name in paths_map.items():
                snap_file = task_snap_dir / snap_name
                if snap_file.exists():
                    orig = Path(original_path)
                    orig.parent.mkdir(parents=True, exist_ok=True)
                    if snap_file.is_dir():
                        shutil.copytree(snap_file, orig, dirs_exist_ok=True)
                    else:
                        shutil.copy2(snap_file, orig)
            logger.info("Rollback successful for task '%s'", task_id)
            return True
        except Exception as e:
            logger.error("Failed rollback for task '%s': %s", task_id, e)
            return False
        finally:
            self.discard_snapshot(task_id)

    def discard_snapshot(self, task_id: str) -> None:
        """Clean up snapshot files after successful completion."""
        task_snap_dir = SNAPSHOT_DIR / task_id
        if task_snap_dir.exists():
            shutil.rmtree(task_snap_dir, ignore_errors=True)


_global_snapshot_mgr: Optional[SnapshotManager] = None


def get_snapshot_manager() -> SnapshotManager:
    global _global_snapshot_mgr
    if _global_snapshot_mgr is None:
        _global_snapshot_mgr = SnapshotManager()
    return _global_snapshot_mgr
