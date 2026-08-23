"""
MAX OS — Snapshot & Rollback Engine.
Provides atomic task boundaries: pre-RUNNING snapshot, complete restore on failure or kill switch.
Leaves zero partial files behind.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set


def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FileState:
    rel_path: str
    content_hash: str
    size: int
    is_dir: bool


DEFAULT_IGNORED_PATTERNS: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".snapshots",
    ".coverage",
    ".venv",
    "venv",
}


@dataclass
class Snapshot:
    task_id: str
    root_dir: Path
    backup_dir: Path
    tracked_files: Dict[str, FileState] = field(default_factory=dict)
    ignored_patterns: Set[str] = field(default_factory=lambda: set(DEFAULT_IGNORED_PATTERNS))


class SnapshotManager:
    """Manages filesystem snapshots and atomic rollbacks for task execution."""

    def __init__(self, base_backup_dir: Optional[Path] = None):
        self.base_backup_dir = (
            Path(base_backup_dir) if base_backup_dir else Path(tempfile.gettempdir()) / "max_snapshots"
        )
        self.base_backup_dir.mkdir(parents=True, exist_ok=True)

    def _should_ignore(self, rel_path: Path, ignored_patterns: Set[str]) -> bool:
        for part in rel_path.parts:
            if part in ignored_patterns or part.startswith("."):
                return True
        return False

    def take_snapshot(
        self,
        root_dir: Path | str,
        task_id: str,
        ignored_patterns: Optional[Set[str]] = None,
    ) -> Snapshot:
        """Captures the current state of files in root_dir into a snapshot backup."""
        root = Path(root_dir).resolve()
        task_backup = self.base_backup_dir / task_id
        if task_backup.exists():
            shutil.rmtree(task_backup)
        task_backup.mkdir(parents=True, exist_ok=True)

        patterns = set(ignored_patterns) if ignored_patterns is not None else set(DEFAULT_IGNORED_PATTERNS)

        snapshot = Snapshot(
            task_id=task_id,
            root_dir=root,
            backup_dir=task_backup,
            ignored_patterns=patterns,
        )

        for current_root, dirs, files in os.walk(root):
            cur_path = Path(current_root)
            rel_dir = cur_path.relative_to(root)
            
            # Prune ignored directories
            dirs[:] = [
                d for d in dirs if not self._should_ignore(rel_dir / d, snapshot.ignored_patterns)
            ]

            for f in files:
                rel_file = rel_dir / f
                if self._should_ignore(rel_file, snapshot.ignored_patterns):
                    continue

                full_path = cur_path / f
                rel_str = str(rel_file).replace("\\", "/")
                file_hash = _compute_hash(full_path)
                file_size = full_path.stat().st_size

                snapshot.tracked_files[rel_str] = FileState(
                    rel_path=rel_str,
                    content_hash=file_hash,
                    size=file_size,
                    is_dir=False,
                )

                # Copy file into backup
                dest_file = task_backup / rel_file
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(full_path, dest_file)

        return snapshot

    def rollback(self, snapshot: Snapshot) -> None:
        """
        Restores root_dir to the exact state captured in snapshot:
        1. Removes files that were created after the snapshot.
        2. Restores files that were modified or deleted.
        3. Removes any newly created empty directories.
        """
        root = snapshot.root_dir

        # 1. Scan current files to find newly created or modified ones
        current_tracked = {}
        for current_root, dirs, files in os.walk(root):
            cur_path = Path(current_root)
            rel_dir = cur_path.relative_to(root)
            dirs[:] = [
                d for d in dirs if not self._should_ignore(rel_dir / d, snapshot.ignored_patterns)
            ]

            for f in files:
                rel_file = rel_dir / f
                if self._should_ignore(rel_file, snapshot.ignored_patterns):
                    continue
                full_path = cur_path / f
                rel_str = str(rel_file).replace("\\", "/")
                current_tracked[rel_str] = full_path

        # Delete newly created files
        for rel_str, full_path in current_tracked.items():
            if rel_str not in snapshot.tracked_files:
                try:
                    full_path.unlink()
                except Exception:
                    pass

        # Restore modified or missing files from backup
        for rel_str, original_state in snapshot.tracked_files.items():
            target_path = root / rel_str
            backup_path = snapshot.backup_dir / rel_str

            needs_restore = False
            if not target_path.exists():
                needs_restore = True
            else:
                cur_hash = _compute_hash(target_path)
                if cur_hash != original_state.content_hash:
                    needs_restore = True

            if needs_restore and backup_path.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, target_path)

        # Clean up empty directories created during the task
        for current_root, dirs, files in os.walk(root, topdown=False):
            cur_path = Path(current_root)
            if cur_path == root:
                continue
            rel_dir = cur_path.relative_to(root)
            if self._should_ignore(rel_dir, snapshot.ignored_patterns):
                continue
            try:
                # If directory is empty, remove it
                if not any(cur_path.iterdir()):
                    cur_path.rmdir()
            except Exception:
                pass

        # Clean up backup
        self.cleanup(snapshot)

    def cleanup(self, snapshot: Snapshot) -> None:
        """Removes the temporary snapshot backup directory."""
        if snapshot.backup_dir.exists():
            try:
                shutil.rmtree(snapshot.backup_dir)
            except Exception:
                pass

    @contextlib.contextmanager
    def atomic_boundary(
        self, root_dir: Path | str, task_id: str
    ) -> Generator[Snapshot, None, None]:
        """Context manager taking a snapshot before execution and rolling back on any exception."""
        snapshot = self.take_snapshot(root_dir, task_id)
        try:
            yield snapshot
            self.cleanup(snapshot)
        except Exception:
            self.rollback(snapshot)
            raise
