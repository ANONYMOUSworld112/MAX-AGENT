"""
MAX OS — Checkpoint & Transaction Rollback Engine (Phases 20 & 33).
Creates state transaction checkpoints for reversible file and system operations.
Supports immediate rollback if plan verification fails.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.snapshot import SnapshotManager


@dataclass
class TransactionRecord:
    transaction_id: str
    task_id: str
    step_index: int
    operation_type: str  # "create_file", "modify_file", "create_directory"
    target_path: str
    backup_path: Optional[str] = None
    created_new: bool = False


class CheckpointManager:
    """
    State Checkpoint and Rollback Engine for MAX High-Speed Computer Control.
    Integrates with core SnapshotManager for system rollback safety.
    """

    def __init__(self, backup_dir: Optional[Path] = None):
        self.backup_dir = backup_dir or Path(r"E:\MAX_OS_RUNNERS\.checkpoints")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_manager = SnapshotManager()
        self._records: Dict[str, List[TransactionRecord]] = {}

    def create_checkpoint(self, task_id: str, label: str = "checkpoint") -> str:
        """Takes a system snapshot checkpoint."""
        snap = self.snapshot_manager.take_snapshot(task_id=task_id, root_dir=Path.cwd())
        return snap.task_id

    def register_file_operation(
        self,
        task_id: str,
        step_index: int,
        op_type: str,
        target_path: str,
    ) -> TransactionRecord:
        """
        Backs up existing target file or registers creation of a new file for rollback tracking.
        """
        p = Path(target_path)
        tx_id = f"tx_{task_id}_{step_index}"
        backup_p: Optional[str] = None
        created_new = not p.exists()

        if p.exists() and p.is_file():
            backup_p_path = self.backup_dir / f"{tx_id}_{p.name}"
            shutil.copy2(p, backup_p_path)
            backup_p = str(backup_p_path)

        rec = TransactionRecord(
            transaction_id=tx_id,
            task_id=task_id,
            step_index=step_index,
            operation_type=op_type,
            target_path=str(p.resolve()),
            backup_path=backup_p,
            created_new=created_new,
        )

        if task_id not in self._records:
            self._records[task_id] = []
        self._records[task_id].append(rec)
        return rec

    def rollback_task(self, task_id: str) -> bool:
        """
        Reverts all registered file operations for a task in reverse order.
        """
        records = self._records.get(task_id, [])
        if not records:
            return True

        for rec in reversed(records):
            p = Path(rec.target_path)
            if rec.created_new and p.exists():
                try:
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        shutil.rmtree(p)
                except Exception:
                    pass
            elif rec.backup_path and Path(rec.backup_path).exists():
                try:
                    shutil.copy2(rec.backup_path, rec.target_path)
                except Exception:
                    pass

        try:
            self.snapshot_manager.rollback(task_id)
        except Exception:
            pass

        return True
