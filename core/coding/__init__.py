"""
MAX-AGENT Sandboxed Coding Workflow Subsystem
=============================================

Provides provider-agnostic coding execution, git worktree isolation,
and independent test verification.
"""

from __future__ import annotations

from core.coding.executor import CodingExecutor, CodingTask, CodingResult
from core.coding.sandbox import WorktreeSandbox
from core.coding.test_verifier import TestVerifier, TestReport

__all__ = [
    "CodingExecutor",
    "CodingTask",
    "CodingResult",
    "WorktreeSandbox",
    "TestVerifier",
    "TestReport",
]
