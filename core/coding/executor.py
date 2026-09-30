"""
CodingExecutor Interface & Data Contracts
==========================================

Provider-agnostic coding abstraction supporting OpenCode, Codex,
Claude Code, and local LLM developer workers.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class CodingTask:
    """Specification of a sandboxed coding task."""
    id: str = field(default_factory=_new_id)
    instruction: str = ""
    repo_path: str = ""
    target_files: List[str] = field(default_factory=list)
    test_command: str = "pytest"
    timeout_seconds: float = 120.0
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodingResult:
    """The verifiable outcome of a coding execution."""
    task_id: str
    success: bool
    modified_files: List[str] = field(default_factory=list)
    diff: str = ""
    test_passed: bool = False
    test_output: str = ""
    error_message: Optional[str] = None
    duration_ms: float = 0.0


class CodingExecutor(ABC):
    """Abstract protocol for coding workers."""

    @abstractmethod
    def execute(self, task: CodingTask, worktree_path: Optional[str] = None) -> CodingResult:
        """Execute a coding task inside an isolated worktree and return a verifiable result."""
        raise NotImplementedError
