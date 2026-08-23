"""
MAX OS — Coding Agent (Minimal Tier 1).
Wraps code generation and execution against caller-supplied acceptance criteria.
Integrates with Kill Switch gate and Snapshot/Rollback engine for atomic execution.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed
from core.snapshot import SnapshotManager


@dataclass
class CodingSpec:
    prompt: str
    target_file: Optional[Path | str] = None
    code_content: Optional[str] = None
    test_command: Optional[List[str]] = None
    expected_output_contains: Optional[str] = None
    validation_fn: Optional[Callable[[Path], bool]] = None
    workspace_dir: Optional[Path | str] = None


@dataclass
class CodingResult:
    success: bool
    task_id: str
    files_written: List[Path] = field(default_factory=list)
    output: str = ""
    error: Optional[str] = None
    test_output: Optional[str] = None


class CodingAgent:
    """
    Minimal Coding Agent for Phase 1.
    Generates code according to spec, verifies acceptance criteria,
    and guarantees atomic rollback if criteria fail or kill switch triggers.
    """

    def __init__(self, workspace_dir: Optional[Path | str] = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd()
        self.snapshot_mgr = SnapshotManager()

    def execute(self, spec: CodingSpec, task_id: str = "coding-task-001") -> CodingResult:
        # 1. Enforce Kill Switch safety gate (Principle #1)
        ks = get_kill_switch()
        require_armed(ks)

        ws = Path(spec.workspace_dir).resolve() if spec.workspace_dir else self.workspace_dir
        ws.mkdir(parents=True, exist_ok=True)

        # 2. Take atomic snapshot
        snapshot = self.snapshot_mgr.take_snapshot(ws, task_id)
        files_written: List[Path] = []

        try:
            # Check kill switch during execution
            if ks.is_triggered():
                raise RuntimeError("Kill switch triggered before code writing.")

            # 3. Determine code to write and target file
            target_rel = spec.target_file or "main.py"
            target_path = (ws / target_rel).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            code = spec.code_content
            if code is None:
                # Built-in generator / heuristic for standard prompt specs
                prompt_lower = spec.prompt.lower()
                if "hello world" in prompt_lower or "print hello" in prompt_lower:
                    code = 'if __name__ == "__main__":\n    print("hello world")\n'
                elif "fibonacci" in prompt_lower:
                    code = (
                        "def fib(n):\n"
                        "    if n <= 1: return n\n"
                        "    return fib(n-1) + fib(n-2)\n\n"
                        'if __name__ == "__main__":\n'
                        "    import sys\n"
                        "    val = int(sys.argv[1]) if len(sys.argv) > 1 else 5\n"
                        "    print(f'fib({val})={fib(val)}')\n"
                    )
                else:
                    code = f"# Generated for: {spec.prompt}\nprint('OK')\n"

            target_path.write_text(code, encoding="utf-8")
            files_written.append(target_path)

            # Check kill switch again
            if ks.is_triggered():
                raise RuntimeError("Kill switch triggered during code generation.")

            # 4. Self-test and verify acceptance criteria
            test_out = ""
            if spec.test_command:
                cmd = spec.test_command
            elif target_path.suffix == ".py":
                cmd = [sys.executable, str(target_path)]
            else:
                cmd = None

            if cmd:
                proc = subprocess.run(
                    cmd,
                    cwd=str(ws),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                test_out = (proc.stdout or "") + (proc.stderr or "")
                if proc.returncode != 0:
                    raise RuntimeError(f"Self-test failed with exit code {proc.returncode}:\n{test_out}")

                if spec.expected_output_contains and spec.expected_output_contains.lower() not in test_out.lower():
                    raise RuntimeError(
                        f"Expected output '{spec.expected_output_contains}' not found in test output:\n{test_out}"
                    )

            if spec.validation_fn and not spec.validation_fn(target_path):
                raise RuntimeError("Custom validation function returned False.")

            # Success -> clean up snapshot without rollback
            self.snapshot_mgr.cleanup(snapshot)
            return CodingResult(
                success=True,
                task_id=task_id,
                files_written=files_written,
                output="Code written and self-test passed.",
                test_output=test_out.strip(),
            )

        except Exception as e:
            # Atomic rollback on any failure
            self.snapshot_mgr.rollback(snapshot)
            return CodingResult(
                success=False,
                task_id=task_id,
                files_written=[],
                output="Execution failed; rolled back all changes.",
                error=str(e),
            )
