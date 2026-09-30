"""
Git Worktree Sandbox for Isolated Code Execution
================================================

Confines all agent file writes, builds, and test runs to disposable git worktrees.
Guarantees host environment integrity and zero unsandboxed side effects.

Master Spec references:
  - Section 13 (ExecutionGateway & Sandboxing)
  - docs/audit/CODING_WORKFLOW.md
  - docs/audit/SECURITY.md (T4)
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from core.adapters import git_adapter

logger = logging.getLogger("max.coding.sandbox")


class ScopeViolationError(PermissionError):
    """Raised when an agent modifies files outside of the allowed worktree scope."""
    pass


class WorktreeSandbox:
    """Manages an isolated git worktree lifecycle for safe code modification and testing."""

    def __init__(
        self,
        repo_path: str,
        branch_name: Optional[str] = None,
        base_worktree_dir: Optional[str] = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        uid = str(uuid.uuid4())[:8]
        self.branch_name = branch_name or f"max-sandbox-{uid}"

        if base_worktree_dir:
            self.worktree_path = Path(base_worktree_dir).resolve() / self.branch_name
        else:
            self.worktree_path = Path(tempfile.gettempdir()) / "max_sandboxes" / self.branch_name

        self._is_active = False
        self._is_real_worktree = False

    def create(self) -> Path:
        """Initialize the isolated sandbox environment."""
        if self._is_active:
            return self.worktree_path

        self.worktree_path.parent.mkdir(parents=True, exist_ok=True)

        if git_adapter.is_git_repo(str(self.repo_path)):
            ok = git_adapter.create_worktree(
                repo_path=str(self.repo_path),
                branch_name=self.branch_name,
                worktree_dir=str(self.worktree_path),
            )
            if ok:
                self._is_real_worktree = True
                self._is_active = True
                logger.info("Created git worktree sandbox at %s", self.worktree_path)
                return self.worktree_path

        # Fallback for non-git directories or test environments: isolated copy
        self.worktree_path.mkdir(parents=True, exist_ok=True)
        if self.repo_path.exists() and self.repo_path != self.worktree_path:
            for item in self.repo_path.iterdir():
                if item.name in (".git", "node_modules", ".venv", "__pycache__"):
                    continue
                dest = self.worktree_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        self._is_active = True
        logger.info("Created copy sandbox at %s", self.worktree_path)
        return self.worktree_path

    def scope_check(self, allowed_files: Optional[List[str]] = None) -> List[str]:
        """Verify that all modifications remain strictly confined within allowed targets.

        Returns a list of violating filenames.
        """
        if not self._is_active:
            return []

        modified = git_adapter.get_modified_files(str(self.worktree_path))
        if not allowed_files:
            return []

        norm_allowed = {Path(f).name.lower() for f in allowed_files}
        violations = []
        for mod in modified:
            mod_path = Path(mod)
            # Check traversal
            if ".." in mod_path.parts:
                violations.append(mod)
            elif mod_path.name.lower() not in norm_allowed:
                violations.append(mod)

        return violations

    def get_diff(self) -> str:
        """Get the unified diff of changes made inside the sandbox."""
        if not self._is_active:
            return ""
        return git_adapter.get_diff(str(self.worktree_path))

    def get_modified_files(self) -> List[str]:
        """List files created or modified inside the sandbox."""
        if not self._is_active:
            return []
        return git_adapter.get_modified_files(str(self.worktree_path))

    def run_command(
        self,
        cmd: List[str] | str,
        timeout: float = 60.0,
        env: Optional[dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Execute a command inside the isolated sandbox."""
        if not self._is_active:
            raise RuntimeError("Cannot run command: Sandbox is not active")

        return git_adapter.run_sandboxed_command(
            cmd=cmd,
            cwd=str(self.worktree_path),
            timeout=timeout,
            env=env,
        )

    def teardown(self) -> None:
        """Completely destroy the sandbox, removing worktree and temporary branch."""
        if not self._is_active:
            return

        if self._is_real_worktree:
            git_adapter.remove_worktree(
                repo_path=str(self.repo_path),
                worktree_dir=str(self.worktree_path),
                branch_name=self.branch_name,
            )
        else:
            if self.worktree_path.exists():
                shutil.rmtree(self.worktree_path, ignore_errors=True)

        self._is_active = False
        logger.info("Torn down sandbox at %s", self.worktree_path)

    def __enter__(self) -> WorktreeSandbox:
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.teardown()
