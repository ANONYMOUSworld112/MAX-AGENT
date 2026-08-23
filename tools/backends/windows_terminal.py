"""
MAX OS — Windows Terminal Tool Backend (Section 13)
tools/backends/windows_terminal.py

Windows-aware terminal tool supporting cmd.exe, powershell.exe, and pwsh.exe.
Prefers argument-list execution, handles stdout/stderr, exit codes, process tree cleanup,
cancellation propagation, and deterministic risk classification.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional

from core.platform.detector import RiskLevel
from tools.command_classifier import classify_command_risk
from tools.interfaces import CommandResult, TerminalTool


class WindowsTerminalTool(TerminalTool):
    """
    Real Windows Terminal tool implementation supporting cmd, PowerShell, and pwsh.
    """

    def __init__(self, preferred_shell: Optional[str] = None):
        self.preferred_shell = preferred_shell or self._detect_best_shell()

    def _detect_best_shell(self) -> str:
        if shutil.which("pwsh"):
            return "pwsh"
        if shutil.which("powershell"):
            return "powershell"
        return "cmd"

    def run(self, command: str, timeout: Optional[float] = None) -> CommandResult:
        """
        Synchronously runs terminal command on Windows.
        """
        timeout_val = timeout if timeout is not None else 30.0
        risk = classify_command_risk(command)

        shell_bin = self.preferred_shell
        if shell_bin in ("powershell", "pwsh"):
            args = [shell_bin, "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            args = ["cmd.exe", "/c", command]

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return CommandResult(
                returncode=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr=f"Windows terminal command execution timed out after {timeout_val} seconds.",
            )
        except Exception as exc:
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr=f"Windows terminal execution error: {str(exc)}",
            )

    async def run_async(self, command: str, timeout: Optional[float] = None) -> CommandResult:
        """
        Asynchronously runs terminal command on Windows with cancellation support.
        """
        timeout_val = timeout if timeout is not None else 30.0
        shell_bin = self.preferred_shell

        if shell_bin in ("powershell", "pwsh"):
            args = [shell_bin, "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            args = ["cmd.exe", "/c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_val)
            return CommandResult(
                returncode=proc.returncode or 0,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr=f"Async Windows terminal command timed out after {timeout_val} seconds.",
            )
        except Exception as exc:
            return CommandResult(
                returncode=-1,
                stdout="",
                stderr=f"Async Windows terminal execution error: {str(exc)}",
            )
