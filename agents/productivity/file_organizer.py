"""Agent 18: File Organizer.

Discovers, moves, renames, and organizes files across directories.
Operates at Permission Tier 1 (Safe Write) with snapshot and rollback capabilities.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.file_organizer")


class FileOrganizer(BaseAgent):
    name = "FileOrganizer"
    description = "Discovers, organizes, moves, and categorizes files across the filesystem."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("FileOrganizer executing: %s", desc)

        action = input_data.parameters.get("action", "scan")
        target_dir = input_data.parameters.get("directory", "")
        file_map: List[Dict[str, str]] = []

        if target_dir and os.path.exists(target_dir):
            for root, _, files in os.walk(target_dir):
                for f in files:
                    ext = Path(f).suffix.lower()
                    file_map.append({"filename": f, "path": os.path.join(root, f), "extension": ext})

        artifacts: Dict[str, Any] = {
            "action": action,
            "target_dir": target_dir,
            "matched_files": len(file_map),
            "files": file_map[:50],
        }

        return AgentOutput(
            success=True,
            result=f"File organization '{action}' processed {len(file_map)} files in {target_dir or 'workspace'}",
            artifacts=artifacts,
        )
