"""
MAX OS — File Agent (Section 8).
Handles file and directory discovery, move, copy, rename, existence verification,
and content hash validation under SecurityGate and Transaction rollback protection.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed
from core.security.security_gate import RiskTier, SecurityGate, SecurityGateBlockedError
from core.transaction import TransactionManager
from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationResult
from tasks.task_system import Task
from tools.backends.filesystem_local import LocalFilesystemTool
from tools.interfaces import FilesystemTool


@dataclass
class FileMetadata:
    path: str
    name: str
    exists: bool
    is_dir: bool
    size_bytes: int
    modified_at: float
    sha256: str = ""


class FileAgent:
    """
    File and Filesystem Operator.
    Discovers, verifies, and manipulates files and folders with integrity checks.
    Uses LocalFilesystemTool via FilesystemTool interface seam.
    """

    def __init__(
        self,
        security_gate: Optional[SecurityGate] = None,
        transaction_manager: Optional[TransactionManager] = None,
        filesystem_tool: Optional[FilesystemTool] = None,
    ):
        self.security_gate = security_gate or SecurityGate()
        self.tx_manager = transaction_manager or TransactionManager(security_gate=self.security_gate)
        self.verifier = VerificationEngine()
        self.fs_tool = filesystem_tool or LocalFilesystemTool()

    def get_file_info(self, file_path: Path | str) -> FileMetadata:
        """Retrieves verified metadata and hash for a target file."""
        p = Path(file_path).resolve()
        if not p.exists():
            return FileMetadata(
                path=str(p),
                name=p.name,
                exists=False,
                is_dir=False,
                size_bytes=0,
                modified_at=0.0,
                sha256="",
            )

        st = p.stat()
        sha = ""
        if p.is_file():
            try:
                content = self.fs_tool.read(str(p))
                sha = hashlib.sha256(content).hexdigest()
            except Exception:
                pass

        return FileMetadata(
            path=str(p),
            name=p.name,
            exists=True,
            is_dir=p.is_dir(),
            size_bytes=st.st_size,
            modified_at=st.st_mtime,
            sha256=sha,
        )

    def find_files(
        self, search_dir: Path | str, pattern: str = "*", recursive: bool = True
    ) -> List[FileMetadata]:
        """Finds all files matching pattern within a directory."""
        root = Path(search_dir).resolve()
        if not root.exists() or not root.is_dir():
            return []

        results: List[FileMetadata] = []
        found_paths = self.fs_tool.search(str(root), pattern)

        for p_str in found_paths:
            p = Path(p_str)
            if p.is_file():
                results.append(self.get_file_info(p))

        return results

    def copy_file(
        self, source_path: Path | str, dest_path: Path | str, overwrite: bool = False
    ) -> bool:
        """Copies file from source to dest and verifies integrity."""
        require_armed(get_kill_switch())
        src = Path(source_path).resolve()
        dst = Path(dest_path).resolve()

        if not src.exists():
            return False

        if dst.exists() and not overwrite:
            return False

        content = self.fs_tool.read(str(src))
        self.fs_tool.write(str(dst), content)

        # Verify destination exists and matches source size
        return dst.exists() and dst.stat().st_size == src.stat().st_size

    def move_file_transactional(
        self,
        source_path: Path | str,
        dest_path: Path | str,
        task_id: str = "file_task",
        approval_token: Optional[str] = None,
    ) -> VerificationResult:
        """
        Moves a file wrapped in a Tier 2 transactional rollback wrapper.
        """
        require_armed(get_kill_switch())
        src = Path(source_path).resolve()
        dst = Path(dest_path).resolve()

        def _action():
            self.fs_tool.move(str(src), str(dst))

        will_overwrite = dst.exists()
        action_type = "overwrite_file" if will_overwrite else "move_file"

        tx, _ = self.tx_manager.execute_transactional_action(
            action_type=action_type,
            target=str(dst),
            task_id=task_id,
            workspace_root=src.parent,
            action_fn=_action,
            expected_result={"path": str(dst)},
            approval_token=approval_token,
            action_payload={"source": str(src), "overwrite": will_overwrite},
        )

        return tx.verification or VerificationResult(
            outcome=VerificationOutcome.SUCCESS if dst.exists() else VerificationOutcome.FAILURE,
            evidence=f"Moved '{src.name}' to '{dst}'",
        )


def file_agent_executor(task: Task) -> Any:
    """
    Standard agent_executor interface signature: def agent_executor(task: Task) -> Any
    """
    agent = FileAgent()
    info = agent.get_file_info(task.description)
    return {"path": info.path, "exists": info.exists, "size": info.size_bytes}
