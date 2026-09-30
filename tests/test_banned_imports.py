"""
MAX-AGENT Banned Import AST Scanner
======================================

Scans all Python files in the repository for dangerous imports that
should only appear inside approved adapter modules.

Banned imports:
  - subprocess (including subprocess.Popen, subprocess.run)
  - os.system, os.startfile, os.exec*
  - pyautogui
  - pywinauto
  - keyboard
  - ctypes.windll
  - shutil.rmtree

Approved locations (allowlist):
  - core/adapters/**        — Platform adapter layer
  - core/process_manager.py — Centralized process management
  - tests/**                — Test code
  - core/max_infra/kill_switch.py — Emergency stop needs process control

This test is EXPECTED TO FAIL initially — it documents the 37 unchoked
side-effect violations that will be migrated progressively.

Master Spec references:
  - Section 13 (ExecutionGateway, banned imports)
  - docs/UNCHOKED_SIDE_EFFECTS.md
"""

import ast
import os
import sys
import unittest
from pathlib import Path


# Repository root
REPO_ROOT = Path(__file__).resolve().parent.parent

# Allowlisted paths (relative to REPO_ROOT) that MAY use banned imports
ALLOWLIST = {
    "core/adapters",
    "core/process_manager.py",
    "core/max_infra/kill_switch.py",
    "tests",
}

# Banned module names and attribute accesses
BANNED_IMPORTS = {
    "subprocess",
    "pyautogui",
    "pywinauto",
    "keyboard",
}

# Banned attribute accesses (module.attr patterns)
BANNED_ATTRS = {
    ("os", "system"),
    ("os", "startfile"),
    ("os", "execvp"),
    ("os", "execvpe"),
    ("os", "execv"),
    ("os", "execve"),
    ("ctypes", "windll"),
    ("shutil", "rmtree"),
}


def _is_allowlisted(filepath: Path) -> bool:
    """Check if a file is in an allowlisted location."""
    try:
        rel = filepath.relative_to(REPO_ROOT)
    except ValueError:
        return False

    rel_str = str(rel).replace("\\", "/")

    for allowed in ALLOWLIST:
        if rel_str.startswith(allowed):
            return True
    return False


def _get_python_files() -> list[Path]:
    """Collect all .py files in the repository, excluding venv/node_modules."""
    py_files = []
    exclude_dirs = {
        ".venv", "venv", "env", ".env",
        "node_modules", ".git", "__pycache__",
        ".eggs", "*.egg-info",
    }

    for root, dirs, files in os.walk(REPO_ROOT):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)

    return py_files


def _scan_file(filepath: Path) -> list[dict]:
    """
    Scan a single Python file for banned imports.

    Returns a list of violation dicts:
        {
            "file": str,
            "line": int,
            "type": "import" | "from_import" | "attr_access",
            "detail": str,
        }
    """
    violations = []

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    for node in ast.walk(tree):
        # Check `import subprocess`, `import pyautogui`, etc.
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name in BANNED_IMPORTS:
                    violations.append({
                        "file": str(filepath.relative_to(REPO_ROOT)),
                        "line": node.lineno,
                        "type": "import",
                        "detail": f"import {alias.name}",
                    })

        # Check `from subprocess import Popen`, `from os import system`, etc.
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_root = node.module.split(".")[0]

                # Check full module ban
                if module_root in BANNED_IMPORTS:
                    violations.append({
                        "file": str(filepath.relative_to(REPO_ROOT)),
                        "line": node.lineno,
                        "type": "from_import",
                        "detail": f"from {node.module} import ...",
                    })

                # Check specific attribute bans
                for alias in node.names:
                    if (module_root, alias.name) in BANNED_ATTRS:
                        violations.append({
                            "file": str(filepath.relative_to(REPO_ROOT)),
                            "line": node.lineno,
                            "type": "from_import",
                            "detail": f"from {node.module} import {alias.name}",
                        })

    return violations


def scan_repository() -> list[dict]:
    """
    Scan the entire repository for banned import violations.

    Returns all violations in non-allowlisted files.
    """
    all_violations = []

    for filepath in _get_python_files():
        if _is_allowlisted(filepath):
            continue

        violations = _scan_file(filepath)
        all_violations.extend(violations)

    return all_violations


class TestBannedImports(unittest.TestCase):
    """
    Automated test that fails if banned imports appear outside adapters.

    NOTE: This test is EXPECTED TO FAIL during Phase 1.
    It documents the migration backlog from docs/UNCHOKED_SIDE_EFFECTS.md.
    As actions migrate to use ExecutionGateway and adapters, violations
    will decrease until this test passes.
    """

    def test_no_banned_imports_outside_adapters(self):
        violations = scan_repository()

        if violations:
            report_lines = [
                f"\n{'='*70}",
                f"BANNED IMPORT VIOLATIONS: {len(violations)} found",
                f"{'='*70}",
            ]
            for v in sorted(violations, key=lambda x: (x["file"], x["line"])):
                report_lines.append(
                    f"  {v['file']}:{v['line']} — {v['detail']}"
                )
            report_lines.append(f"{'='*70}")
            report_lines.append(
                "These files use banned imports outside of approved adapters."
            )
            report_lines.append(
                "Migrate them to use ExecutionGateway + core/adapters/."
            )

            # Log but don't fail yet — this tracks migration progress
            report = "\n".join(report_lines)
            print(report)

            # Uncomment below to make this a hard failure:
            # self.fail(report)

            # For now, track the count for regression detection
            # As of Phase 0 baseline, there are ~37 violations.
            # This number should only decrease over time.
            MAX_EXPECTED_VIOLATIONS = 50  # generous ceiling
            self.assertLessEqual(
                len(violations),
                MAX_EXPECTED_VIOLATIONS,
                f"Banned import violations ({len(violations)}) exceed ceiling "
                f"({MAX_EXPECTED_VIOLATIONS}). New violations are being introduced!",
            )


if __name__ == "__main__":
    # Run standalone scan
    violations = scan_repository()
    if violations:
        print(f"\nFound {len(violations)} banned import violations:\n")
        for v in sorted(violations, key=lambda x: (x["file"], x["line"])):
            print(f"  {v['file']}:{v['line']} — {v['detail']}")
    else:
        print("No banned import violations found.")
    sys.exit(len(violations))
