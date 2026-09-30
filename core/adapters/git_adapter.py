"""
Git & Sandboxed Subprocess Adapter
===================================

Allowlisted platform adapter for git worktree management and sandboxed command execution.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger("max.adapters.git")


def run_git_command(
    args: List[str],
    cwd: str,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess:
    """Run a git command in the specified working directory."""
    full_cmd = ["git"] + args
    return subprocess.run(
        full_cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_sandboxed_command(
    cmd: List[str] | str,
    cwd: str,
    timeout: float = 60.0,
    env: Optional[dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Run a sandboxed shell/CLI command inside a worktree directory with timeout."""
    is_shell = isinstance(cmd, str)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=is_shell,
            env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        logger.error("Command timed out after %.1f seconds: %s", timeout, cmd)
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as exc:
        logger.error("Failed to execute command: %s", exc)
        return -1, "", str(exc)


def is_git_repo(path: str) -> bool:
    """Check if the given path is inside a git working tree."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def create_worktree(repo_path: str, branch_name: str, worktree_dir: str) -> bool:
    """Create a new git worktree with a dedicated branch."""
    os.makedirs(worktree_dir, exist_ok=True)
    res = subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, worktree_dir, "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    if res.returncode != 0:
        logger.error("git worktree add failed: %s", res.stderr)
        return False
    return True


def remove_worktree(repo_path: str, worktree_dir: str, branch_name: Optional[str] = None) -> bool:
    """Remove a git worktree and clean up the temporary branch."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", worktree_dir],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
    except Exception as exc:
        logger.warning("git worktree remove failed: %s", exc)

    if os.path.exists(worktree_dir):
        try:
            shutil.rmtree(worktree_dir, ignore_errors=True)
        except Exception:
            pass

    if branch_name:
        try:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10.0,
            )
        except Exception:
            pass

    return True


def get_diff(worktree_dir: str) -> str:
    """Get unstaged and staged git diff inside the worktree."""
    try:
        res = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return ""


def get_modified_files(worktree_dir: str) -> List[str]:
    """Get list of modified and untracked files inside the worktree."""
    files: List[str] = []
    try:
        # Changed tracked files
        res1 = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if res1.returncode == 0:
            files.extend([f.strip() for f in res1.stdout.splitlines() if f.strip()])

        # Untracked files
        res2 = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if res2.returncode == 0:
            for line in res2.stdout.splitlines():
                if line.startswith("??"):
                    files.append(line[3:].strip())
    except Exception as exc:
        logger.warning("Failed to query git status: %s", exc)

    return list(dict.fromkeys(files))
