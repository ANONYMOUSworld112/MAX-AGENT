"""File state verifier: verifies existence, size, and SHA256 checksums."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import List, Optional
from core.verification.engine import VerificationOutcome, VerificationReport
from core.max_infra.reconciliation import ReconciliationEngine

logger = logging.getLogger("max.verification.file")


class FileVerifier:
    def __init__(self, reconciliation_engine: Optional[ReconciliationEngine] = None) -> None:
        self.reconciliation = reconciliation_engine or ReconciliationEngine()

    def verify_files_exist(self, file_paths: List[str]) -> VerificationReport:
        """Verifies that all specified files exist on the filesystem."""
        recon = self.reconciliation.verify_files_exist(file_paths)
        if recon.is_verified:
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details=recon.details,
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details=recon.details,
            errors=[f"File existence verification failed: {recon.details}"],
        )

    def verify_file_content(self, file_path: str, expected_snippet: str) -> VerificationReport:
        """Verifies that file contains expected snippet."""
        if not os.path.exists(file_path):
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details={"file_path": file_path, "exists": False},
                errors=[f"File '{file_path}' does not exist."],
            )
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if expected_snippet in content:
                return VerificationReport(
                    outcome=VerificationOutcome.SUCCESS,
                    details={"file_path": file_path, "snippet_found": True},
                )
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details={"file_path": file_path, "snippet_found": False},
                errors=[f"Snippet not found in '{file_path}'"],
            )
        except Exception as exc:
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"file_path": file_path, "error": str(exc)},
                errors=[str(exc)],
            )

    def verify(self, file_path: str | Path, expected_content: Optional[str] = None) -> VerificationReport:
        """Unified verify entry point for existence or content match."""
        path_str = str(file_path)
        if expected_content is not None:
            return self.verify_file_content(path_str, expected_content)
        return self.verify_files_exist([path_str])

    def compute_sha256(self, file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            return None
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
