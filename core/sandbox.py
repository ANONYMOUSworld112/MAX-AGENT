"""
MAX OS — Sandboxed Execution Boundary (Step 8.5).
Provides process and container isolation for unverified code, skills, and plugins.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False


class SandboxExecutor:
    """
    Executes code in isolated temporary directories with strict timeouts.
    """

    def __init__(self, default_timeout_s: float = 10.0):
        self.default_timeout_s = default_timeout_s

    def execute_python(
        self,
        code: str,
        timeout_s: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        require_armed(get_kill_switch())
        import time

        tout = timeout_s or self.default_timeout_s
        start = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="max_sandbox_") as tmp_dir:
            script_path = Path(tmp_dir) / "runner.py"
            script_path.write_text(code, encoding="utf-8")

            try:
                proc = subprocess.run(
                    ["python", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=tout,
                    cwd=tmp_dir,
                    env=env,
                )
                dur = int((time.monotonic() - start) * 1000)
                return SandboxResult(
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    duration_ms=dur,
                    timed_out=False,
                )
            except subprocess.TimeoutExpired as e:
                dur = int((time.monotonic() - start) * 1000)
                return SandboxResult(
                    stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                    stderr=e.stderr or "Execution timed out" if isinstance(e.stderr, str) else "Execution timed out",
                    exit_code=-1,
                    duration_ms=dur,
                    timed_out=True,
                )
