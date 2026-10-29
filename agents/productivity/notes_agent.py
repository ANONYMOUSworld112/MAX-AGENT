"""Agent 19: Notes Agent.

Captures meeting notes, conversation transcripts, and user thoughts,
indexing and persisting them into long-term structured disk storage for future recall.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.notes")


class NotesAgent(BaseAgent):
    name = "NotesAgent"
    description = "Captures, indexes, and persists meeting notes and thoughts into durable memory."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        raw_note = (input_data.task_description or "Quick note").strip()
        params = input_data.parameters or {}
        action = params.get("action", "save_note")
        tags = params.get("tags", ["daily", "work"])

        root_dir = Path(__file__).resolve().parent.parent.parent
        notes_file = root_dir / "memory" / "notes.json"
        notes_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing notes
        existing_notes: List[Dict[str, Any]] = []
        if notes_file.exists():
            try:
                existing_notes = json.loads(notes_file.read_text(encoding="utf-8"))
            except Exception:
                existing_notes = []

        if action == "list_notes":
            return AgentOutput(
                success=True,
                result=f"Retrieved {len(existing_notes)} stored note(s).",
                artifacts={"notes": existing_notes, "count": len(existing_notes)},
            )

        note_id = f"note_{int(time.time() * 1000)}"
        summary = raw_note[:80] + ("..." if len(raw_note) > 80 else "")
        record = {
            "id": note_id,
            "timestamp": time.time(),
            "content": raw_note,
            "tags": tags,
            "summary": summary,
        }

        existing_notes.append(record)
        # Atomic write
        temp_file = notes_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(existing_notes, indent=2), encoding="utf-8")
        temp_file.replace(notes_file)

        logger.info("NotesAgent persisted note '%s' to %s", note_id, notes_file)

        return AgentOutput(
            success=True,
            result=f"Indexed and persisted note successfully: '{summary}'.",
            artifacts={"note_record": record, "total_notes": len(existing_notes), "storage_path": str(notes_file)},
        )
