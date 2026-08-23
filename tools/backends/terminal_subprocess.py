"""
MAX OS - Subprocess Terminal Tool Backend
tools/backends/terminal_subprocess.py
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Optional

from tools.interfaces import CommandResult, TerminalTool


class SubprocessTerminalTool(TerminalTool):
    """
    Subprocess-backed implementation of TerminalTool interface.
    Prefers non-shell subprocess execution where possible, handling
    timeouts and capturing returncode, stdout, and stderr.
    """

    def run(self, command: str, timeout: Optional[float] = None) -> CommandResult:
        timeout_val = timeout if timeout is not None else 30.0
        try:
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_val,
            )
            return CommandResult(res.returncode, res.stdout, res.stderr)
        except subprocess.TimeoutExpired:
            return CommandResult(-1, "", f"Execution timed out after {timeout_val}s")
        except Exception as exc:
            return CommandResult(-1, "", f"Subprocess error: {str(exc)}")

    async def run_async(self, command: str, timeout: Optional[float] = None) -> CommandResult:
        timeout_val = timeout if timeout is not None else 30.0
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_val)
            return CommandResult(
                proc.returncode or 0,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return CommandResult(-1, "", f"Execution timed out after {timeout_val}s")
        except Exception as exc:
            return CommandResult(-1, "", f"Async subprocess error: {str(exc)}")
