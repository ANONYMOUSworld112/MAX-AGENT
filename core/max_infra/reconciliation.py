"""State Reconciliation Engine.

Verifies actual operating system truth against agent assertions.
Ensures that files claimed to be created actually exist on disk, are non-empty,
and commands exited with expected status codes before tasks are marked DONE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger("max.infra.reconciliation")


@dataclass
class ReconciliationReport:
    is_verified: bool
    details: List[str] = field(default_factory=list)


class ReconciliationEngine:
    def verify_files_exist(self, file_paths: List[str | Path]) -> ReconciliationReport:
        missing = []
        empty = []
        details = []

        for p_raw in file_paths:
            p = Path(p_raw)
            if not p.exists():
                missing.append(str(p))
            elif p.is_file() and p.stat().st_size == 0:
                empty.append(str(p))

        if missing:
            details.append(f"Missing expected files: {', '.join(missing)}")
        if empty:
            details.append(f"Files are empty (0 bytes): {', '.join(empty)}")

        is_ok = len(missing) == 0 and len(empty) == 0
        if is_ok:
            details.append("All expected files verified and non-empty.")

        return ReconciliationReport(is_verified=is_ok, details=details)

    def verify_file_exists(self, file_path: str | Path) -> bool:
        report = self.verify_files_exist([file_path])
        return report.is_verified

    def verify_exit_code(self, exit_code: int, expected: int = 0) -> bool:
        return exit_code == expected
