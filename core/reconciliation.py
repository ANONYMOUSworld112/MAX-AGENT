"""
MAX OS — Reconciliation Check Engine (Step 2.5).
Verifies agent-reported outcome against real physical/database state.
If an agent self-reports 'success' but real state is inconsistent, converts outcome to failure.
"""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class ReconciliationResult:
    matched: bool
    details: str
    mismatches: List[str]


class ReconciliationChecker:
    """
    Independent, deterministic verification engine.
    Verifies agent claims against ground-truth reality.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def reconcile_coding_task(
        self,
        expected_files: List[Path | str],
        workspace_dir: Path | str,
        must_contain: Optional[str] = None,
    ) -> ReconciliationResult:
        """Verifies that files claimed to be written by Coding Agent exist on disk and are valid."""
        ws = Path(workspace_dir).resolve()
        mismatches = []

        for f in expected_files:
            file_path = (ws / f).resolve()
            if not file_path.exists():
                mismatches.append(f"Expected file missing on disk: {file_path}")
            elif file_path.stat().st_size == 0:
                mismatches.append(f"File was created empty: {file_path}")
            elif must_contain and must_contain.lower() not in file_path.read_text(encoding="utf-8", errors="ignore").lower():
                mismatches.append(f"File {file_path} missing required text: '{must_contain}'")

        matched = len(mismatches) == 0
        details = "All expected files verified on disk." if matched else f"Reconciliation failed: {'; '.join(mismatches)}"
        return ReconciliationResult(matched=matched, details=details, mismatches=mismatches)

    def reconcile_deploy_task(
        self,
        repo_path: Path | str,
        expected_commit: Optional[str] = None,
    ) -> ReconciliationResult:
        """Verifies that Git repository and commit hash really exist in Git log."""
        path = Path(repo_path).resolve()
        mismatches = []

        if not (path / ".git").exists():
            mismatches.append(f"No git repository found at {path}")
            return ReconciliationResult(matched=False, details=f"No git repository found at {path}", mismatches=mismatches)

        if expected_commit:
            proc = subprocess.run(
                ["git", "cat-file", "-t", expected_commit],
                cwd=str(path),
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or proc.stdout.strip() != "commit":
                mismatches.append(f"Claimed commit {expected_commit} does not exist in git repo")

        matched = len(mismatches) == 0
        details = "Git commit and repository verified." if matched else f"Reconciliation failed: {'; '.join(mismatches)}"
        return ReconciliationResult(matched=matched, details=details, mismatches=mismatches)

    def reconcile_calendar_task(self, event_id: str) -> ReconciliationResult:
        """Verifies that calendar event exists in database."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM calendar_events WHERE event_id = ?", (event_id,)).fetchone()
            if not row:
                return ReconciliationResult(
                    matched=False,
                    details=f"Event {event_id} was claimed created but not found in calendar_events table",
                    mismatches=[f"Missing event {event_id}"],
                )
            return ReconciliationResult(matched=True, details="Event verified in DB", mismatches=[])
        finally:
            conn.close()

    def reconcile_notes_task(self, note_id_or_title: str) -> ReconciliationResult:
        """Verifies that note exists in database."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM notes_store WHERE note_id = ? OR title = ?",
                (note_id_or_title, note_id_or_title),
            ).fetchone()
            if not row:
                return ReconciliationResult(
                    matched=False,
                    details=f"Note '{note_id_or_title}' was claimed created but not found in notes_store table",
                    mismatches=[f"Missing note {note_id_or_title}"],
                )
            return ReconciliationResult(matched=True, details="Note verified in DB", mismatches=[])
        finally:
            conn.close()
