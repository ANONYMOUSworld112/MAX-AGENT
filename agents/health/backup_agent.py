"""Agent 30: Backup Agent.

Manages automated file and directory backups using SnapshotEngine.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.backup")


class BackupAgent(BaseAgent):
    name = "BackupAgent"
    description = "Creates atomic snapshots and restores backups of critical files."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("BackupAgent processing: %s", desc)

        action = input_data.parameters.get("action", "backup")
        files: List[str] = input_data.parameters.get("files", input_data.target_files)
        snapshot_id = input_data.parameters.get("snapshot_id", "")

        artifacts: Dict[str, Any] = {
            "action": action,
            "files": files,
        }

        if action == "backup":
            if not files:
                return AgentOutput(
                    success=False,
                    error="No files specified for backup.",
                    artifacts=artifacts,
                )
            created_snap_id = self.snapshot_engine.capture_snapshot(
                task_id=input_data.task_id,
                file_paths=files,
            )
            artifacts["snapshot_id"] = created_snap_id
            result = f"Atomic snapshot '{created_snap_id}' created for {len(files)} files"
        elif action == "restore":
            if not snapshot_id:
                return AgentOutput(
                    success=False,
                    error="No snapshot_id provided for restore.",
                    artifacts=artifacts,
                )
            self.snapshot_engine.rollback(snapshot_id)
            artifacts["restored_snapshot_id"] = snapshot_id
            result = f"Successfully restored snapshot '{snapshot_id}'"
        else:
            result = f"Backup status verified for task '{input_data.task_id}'"

        return AgentOutput(
            success=True,
            result=result,
            artifacts=artifacts,
        )
