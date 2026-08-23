"""
MAX OS — Terminal Agent (Section 8).
Executes PowerShell and Command Prompt scripts, captures stdout/stderr,
enforces timeouts, and performs deterministic exit-code verification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed
from core.security.security_gate import RiskTier, SecurityGate
from core.verification.engine import VerificationEngine
from tasks.task_system import Task
from tools.backends.terminal_subprocess import SubprocessTerminalTool
from tools.command_classifier import classify_command_risk
from tools.interfaces import TerminalTool


@dataclass
class TerminalExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    success: bool
    verified: bool


class TerminalAgent:
    """
    Command Line & Terminal Operator.
    Executes PowerShell/CLI commands with exit-code verification and execution tracing.
    Uses SubprocessTerminalTool via TerminalTool interface seam.
    """

    def __init__(
        self,
        security_gate: Optional[SecurityGate] = None,
        terminal_tool: Optional[TerminalTool] = None,
    ):
        self.security_gate = security_gate or SecurityGate()
        self.verifier = VerificationEngine()
        self.terminal_tool = terminal_tool or SubprocessTerminalTool()

    def run_command(
        self,
        command: str,
        cwd: Optional[Path | str] = None,
        timeout: float = 30.0,
        shell: str = "powershell",
        task_id: str = "term_task",
        approval_token: Optional[str] = None,
    ) -> TerminalExecutionResult:
        """
        Executes a shell command with security evaluation and exit-code verification.
        """
        require_armed(get_kill_switch())
        start_mono = time.monotonic()

        # Classify command risk
        risk_level = classify_command_risk(command)

        # Authorize via SecurityGate if command is elevated/admin
        action_type = "execute_admin_command" if any(k in command.lower() for k in ("elevated", "admin", "netsh", "diskpart")) else "run_command"
        self.security_gate.authorize_action(
            action_type=action_type,
            target=command,
            task_id=task_id,
            action_id=f"cmd_{int(time.time())}",
            approval_token=approval_token,
        )

        # Dispatch via TerminalTool backend
        if shell.lower() == "powershell":
            full_cmd = f"powershell -NoProfile -NonInteractive -Command \"{command}\""
        else:
            full_cmd = f"cmd.exe /c \"{command}\""

        res = self.terminal_tool.run(full_cmd, timeout=timeout)

        duration_ms = int((time.monotonic() - start_mono) * 1000)
        is_success = (res.returncode == 0)

        return TerminalExecutionResult(
            command=command,
            exit_code=res.returncode,
            stdout=res.stdout,
            stderr=res.stderr,
            duration_ms=duration_ms,
            success=is_success,
            verified=is_success,
        )


def terminal_agent_executor(task: Task) -> Any:
    """
    Standard agent_executor interface signature: def agent_executor(task: Task) -> Any
    """
    agent = TerminalAgent()
    res = agent.run_command(command=task.description, task_id=task.id)
    if not res.success:
        raise RuntimeError(f"Terminal execution failed (code {res.exit_code}): {res.stderr}")
    return res.stdout
