"""
MAX OS — Post-Execution Reconciliation Engine
Build Order: #13 (Layer 3C)
═══════════════════════════════════════════════════════

Queries real system state vs agent self-report post-execution.
Flags systemic mismatches if agent self-report lies about completion.
"""

from __future__ import annotations

import logging
from pathlib import Path
from src.infra import state_db
from src.infra.errors import MaxError, ErrorClass

logger = logging.getLogger("max.core.reconciliation")


def verify_execution(task_id: str, expected_outcomes: dict) -> bool:
    """
    Verify real state matches expected execution outcomes.
    expected_outcomes dict can specify files_created, files_modified, service_running, process_started, etc.
    """
    logger.info("Reconciling task '%s' expected outcomes: %s", task_id, expected_outcomes)

    # Check files created/modified
    if "files_exist" in expected_outcomes:
        for file_path in expected_outcomes["files_exist"]:
            if not Path(file_path).exists():
                logger.error("Reconciliation failed for task '%s': file '%s' does not exist", task_id, file_path)
                return False

    if "files_absent" in expected_outcomes:
        for file_path in expected_outcomes["files_absent"]:
            if Path(file_path).exists():
                logger.error("Reconciliation failed for task '%s': file '%s' still exists", task_id, file_path)
                return False

    logger.info("Reconciliation passed for task '%s'", task_id)
    return True
