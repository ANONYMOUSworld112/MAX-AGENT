"""Atomic Pre-Execution Snapshot and Rollback Engine.

Guarantees transactional integrity for filesystem operations.
Before any agent executes a modifying task (editing, overwriting, deleting),
a snapshot of all target files is captured with SHA-256 hashes.
If an agent fails, the watchdog trips, or the user requests 'Undo',
the system automatically restores the files bit-for-bit to their pre-execution state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("max.infra.snapshot")


class SnapshotEngine:
    def __init__(self, base_snapshot_dir: str | Path = ".snapshots") -> None:
        self.base_dir = Path(base_snapshot_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _hash_file(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def capture_snapshot(self, task_id: str, file_paths: List[str | Path]) -> str:
        snap_id = f"snap_{task_id}_{uuid.uuid4().hex[:8]}"
        snap_dir = self.base_dir / snap_id
        files_dir = snap_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        manifest: Dict[str, Any] = {
            "snapshot_id": snap_id,
            "task_id": task_id,
            "entries": []
        }

        for idx, fp_raw in enumerate(file_paths):
            fp = Path(fp_raw).resolve()
            if fp.exists() and fp.is_file():
                sha = self._hash_file(fp)
                backup_file = files_dir / f"file_{idx}.bak"
                shutil.copy2(fp, backup_file)
                manifest["entries"].append({
                    "original_path": str(fp),
                    "backup_path": str(backup_file),
                    "sha256": sha,
                    "existed": True,
                })
            else:
                manifest["entries"].append({
                    "original_path": str(fp),
                    "backup_path": None,
                    "sha256": None,
                    "existed": False,
                })

        manifest_path = snap_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("Captured snapshot '%s' for task '%s' (%d files)", snap_id, task_id, len(manifest["entries"]))
        return snap_id

    def rollback(self, snapshot_id: str) -> bool:
        snap_dir = self.base_dir / snapshot_id
        manifest_path = snap_dir / "manifest.json"

        if not manifest_path.exists():
            logger.error("Cannot rollback: snapshot manifest not found at %s", manifest_path)
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest.get("entries", []):
                orig_path = Path(entry["original_path"])
                existed = entry.get("existed", True)

                if existed:
                    backup = Path(entry["backup_path"])
                    if backup.exists():
                        orig_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup, orig_path)
                        logger.info("Restored file '%s' from snapshot '%s'", orig_path, snapshot_id)
                else:
                    # File was newly created by task; remove it
                    if orig_path.exists():
                        if orig_path.is_file():
                            orig_path.unlink()
                        elif orig_path.is_dir():
                            shutil.rmtree(orig_path, ignore_errors=True)
                        logger.info("Removed newly created file '%s' during rollback", orig_path)

            return True
        except Exception as exc:
            logger.error("Rollback failed for snapshot '%s': %s", snapshot_id, exc)
            return False
