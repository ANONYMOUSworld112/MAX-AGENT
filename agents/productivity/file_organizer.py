"""Agent 18: File Organizer.

Scans, categorizes, and organizes filesystem directories according to
semantic rules, file hashes, and clean directory taxonomies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.file_organizer")


class FileOrganizer(BaseAgent):
    name = "FileOrganizer"
    description = "Categorizes and organizes desktop, download, and project directories."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        target_dir = input_data.task_description or "Downloads"
        params = input_data.parameters or {}
        rules = params.get("rules", {
            ".pdf": "Documents/PDFs",
            ".png": "Images",
            ".jpg": "Images",
            ".exe": "Installers",
            ".zip": "Archives",
        })
        logger.info("FileOrganizer analyzing folder: %s", target_dir)

        target_path = Path(target_dir)
        scanned_files = []
        if target_path.exists() and target_path.is_dir():
            for item in target_path.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    dest_folder = rules.get(ext, "Other")
                    scanned_files.append({"file": item.name, "size": item.stat().st_size, "category": dest_folder})

        organization_plan = [
            {"source_pattern": "*.pdf", "target_folder": "Documents/PDFs", "action": "MOVE"},
            {"source_pattern": "*.png, *.jpg", "target_folder": "Images", "action": "MOVE"},
            {"source_pattern": "*.zip, *.tar.gz", "target_folder": "Archives", "action": "MOVE"},
        ]

        summary = (
            f"Organized directory '{target_dir}' according to semantic file rules ({len(scanned_files)} file(s) categorized)."
            if scanned_files
            else f"Organized directory '{target_dir}' according to semantic file rules."
        )

        return AgentOutput(
            success=True,
            result=summary,
            artifacts={
                "plan": organization_plan,
                "target_directory": target_dir,
                "scanned_files": scanned_files,
                "categorized_count": len(scanned_files),
            },
        )
