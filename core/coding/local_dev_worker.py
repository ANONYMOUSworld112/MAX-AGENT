"""
Local Developer Worker Implementing CodingExecutor
===================================================

Replaces the unsandboxed actions/dev_agent.py pipeline.
Executes code generation and modification strictly inside a WorktreeSandbox
with independent test verification.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from core.coding.executor import CodingExecutor, CodingResult, CodingTask
from core.coding.sandbox import WorktreeSandbox
from core.coding.test_verifier import TestVerifier

logger = logging.getLogger("max.coding.local_dev_worker")


class LocalDevWorker(CodingExecutor):
    """Sandboxed coding worker."""

    def __init__(
        self,
        code_generator_fn: Optional[Callable[[str, list[str]], dict[str, str]]] = None,
        test_verifier: Optional[TestVerifier] = None,
    ) -> None:
        self.code_generator_fn = code_generator_fn
        self.test_verifier = test_verifier or TestVerifier()

    def execute(self, task: CodingTask, worktree_path: Optional[str] = None) -> CodingResult:
        start_t = time.time()
        modified_files: list[str] = []

        # Determine sandbox
        if worktree_path:
            wt_path = Path(worktree_path)
            owns_sandbox = False
            sandbox = None
        else:
            sandbox = WorktreeSandbox(repo_path=task.repo_path)
            wt_path = sandbox.create()
            owns_sandbox = True

        try:
            # 1. Generate code modifications
            if self.code_generator_fn:
                file_updates = self.code_generator_fn(task.instruction, task.target_files)
                for rel_path, content in file_updates.items():
                    target_file = wt_path / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(content, encoding="utf-8")
                    modified_files.append(rel_path)

            # 2. Scope check (ensure no escape from sandbox)
            if sandbox:
                violations = sandbox.scope_check(allowed_files=task.target_files)
                if violations:
                    return CodingResult(
                        task_id=task.id,
                        success=False,
                        error_message=f"Scope violation: modified unauthorized files {violations}",
                        duration_ms=(time.time() - start_t) * 1000,
                    )

            # 3. Independent test verification
            diff_text = sandbox.get_diff() if sandbox else ""
            test_ok, test_rep, test_violations = self.test_verifier.run_and_verify(
                worktree_path=wt_path,
                test_command=task.test_command,
                timeout=task.timeout_seconds,
            )

            success = test_ok and len(test_violations) == 0

            return CodingResult(
                task_id=task.id,
                success=success,
                modified_files=modified_files,
                diff=diff_text,
                test_passed=test_ok,
                test_output=test_rep.raw_output,
                error_message="; ".join(test_violations) if test_violations else None,
                duration_ms=(time.time() - start_t) * 1000,
            )

        except Exception as exc:
            logger.error("Coding execution failed: %s", exc)
            return CodingResult(
                task_id=task.id,
                success=False,
                error_message=str(exc),
                duration_ms=(time.time() - start_t) * 1000,
            )

        finally:
            if owns_sandbox and sandbox:
                sandbox.teardown()
