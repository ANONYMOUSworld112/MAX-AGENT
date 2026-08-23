"""
MAX OS — Ephemeral Batch Execution & Auto-Purge Engine.
Manages the lifecycle of transient batch runners on the E: drive:
  1. Creates dedicated runner files in 'E:\\MAX_OS_RUNNERS\\'.
  2. Executes the runner interactively on the user's active screen.
  3. Purges and deletes all traces of the batch file upon completion.
"""

from __future__ import annotations

import os
import sys
import uuid
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed

DEFAULT_RUNNERS_DIR = Path(r"E:\MAX_OS_RUNNERS")
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


class EphemeralBatchRunner:
    """
    Manages generation, interactive execution, and zero-trace cleanup of ephemeral .bat files on E: drive.
    """

    def __init__(self, runners_dir: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self.runners_dir = runners_dir or DEFAULT_RUNNERS_DIR
        self.workspace_root = workspace_root or WORKSPACE_ROOT
        
        # Ensure runner directory exists
        try:
            self.runners_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.runners_dir = self.workspace_root / ".transient_runners"
            self.runners_dir.mkdir(parents=True, exist_ok=True)

    def generate_batch_file(
        self,
        commands: List[str],
        runner_id: Optional[str] = None,
        title: str = "MAX OS (J.A.R.V.I.S.) — Live Interactive Runner",
        self_delete: bool = True,
    ) -> Path:
        """Creates a transient .bat file in the E: drive runners directory."""
        rid = runner_id or f"runner_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        bat_path = self.runners_dir / f"{rid}.bat"

        bat_lines = [
            "@echo off",
            f"title {title}",
            "color 0b",
            f'cd /d "{self.workspace_root.resolve()}"',
            "echo ================================================================================",
            "echo       MAX OS — LIVE EPHEMERAL WORKSTATION AUTOMATION RUNNER",
            "echo ================================================================================",
            "echo.",
        ]

        for cmd in commands:
            bat_lines.append(cmd)

        bat_lines.extend([
            "echo.",
            "echo ================================================================================",
            "echo [OK] Execution finished. Auto-purging runner from E:\\MAX_OS_RUNNERS\\...",
            "echo ================================================================================",
        ])

        if self_delete:
            bat_lines.extend([
                'start /b "" cmd /c del /f /q "%~f0"&exit /b',
            ])

        bat_content = "\r\n".join(bat_lines) + "\r\n"
        bat_path.write_text(bat_content, encoding="utf-8")
        return bat_path

    def execute_and_cleanup(
        self,
        commands: List[str],
        timeout: float = 60.0,
        run_interactive: bool = True,
    ) -> Dict[str, Any]:
        """
        Generates the .bat file on E: drive, launches it interactively on the user's screen,
        and ensures all traces are deleted immediately upon completion.
        """
        require_armed(get_kill_switch())
        bat_path = self.generate_batch_file(commands=commands, self_delete=run_interactive)

        stdout_out = ""
        stderr_out = ""
        exit_code = 0

        try:
            if run_interactive:
                # Spawns interactive command window on the user's active monitor and waits for task completion
                cmd = f'cmd.exe /c start /wait "" "{bat_path.resolve()}"'
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                exit_code = proc.returncode
                stdout_out = f"Launched interactive runner on screen: {bat_path}"
            else:
                # Runs in background process
                proc = subprocess.run(
                    [str(bat_path.resolve())],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.workspace_root.resolve()),
                )
                exit_code = proc.returncode
                stdout_out = proc.stdout
                stderr_out = proc.stderr

        except subprocess.TimeoutExpired:
            exit_code = -1
            stderr_out = f"Ephemeral runner timed out after {timeout} seconds."
        except Exception as e:
            exit_code = 1
            stderr_out = str(e)
        finally:
            # Poll delay to ensure file is deleted after interactive/background run
            for _ in range(10):
                if not bat_path.exists():
                    break
                time.sleep(0.2)
                try:
                    bat_path.unlink()
                except Exception:
                    pass

        file_still_exists = bat_path.exists()

        return {
            "status": "success" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "bat_path_used": str(bat_path),
            "traces_deleted": not file_still_exists,
            "stdout": stdout_out,
            "stderr": stderr_out,
        }

    def execute_instruction_ephemeral(self, instruction: str, run_interactive: bool = True) -> Dict[str, Any]:
        """
        Takes a natural language instruction, stages an ephemeral .bat on E:,
        launches it on the screen, and purges all files upon completion.
        """
        python_cmd = f'python -m cli.main operate-desktop --command "{instruction}"'
        return self.execute_and_cleanup(commands=[python_cmd], run_interactive=run_interactive)
