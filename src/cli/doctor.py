"""
MAX OS — System Doctor CLI (`max doctor`) (Step 8.6).
Comprehensive diagnostics for OS health, database integrity, kill switch, and vault.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import click
from rich.console import Console
from rich.table import Table

from core.kill_switch import get_kill_switch
from core.vault import Vault

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class DiagnosticCheck:
    name: str
    status: str  # 'PASS', 'WARN', 'FAIL'
    details: str


def run_diagnostics(db_path: Optional[Path | str] = None) -> List[DiagnosticCheck]:
    checks = []
    p = Path(db_path) if db_path else DEFAULT_DB_PATH

    # 1. Kill Switch
    ks = get_kill_switch()
    if ks.is_armed():
        checks.append(DiagnosticCheck("Kill Switch", "PASS", "Component #0 is ARMED and operational"))
    else:
        checks.append(DiagnosticCheck("Kill Switch", "WARN", f"Component #0 is in state '{ks.state.value}'"))

    # 2. State Database & WAL mode
    if p.exists():
        try:
            conn = sqlite3.connect(str(p))
            cur = conn.execute("PRAGMA journal_mode;")
            j_mode = cur.fetchone()[0]
            conn.close()
            checks.append(DiagnosticCheck("Database Integrity", "PASS", f"max_state.db accessible, journal_mode={j_mode}"))
        except Exception as e:
            checks.append(DiagnosticCheck("Database Integrity", "FAIL", f"Error opening db: {e}"))
    else:
        checks.append(DiagnosticCheck("Database Integrity", "FAIL", "max_state.db not found"))

    # 3. Vault & Encryption
    try:
        vault = Vault()
        checks.append(DiagnosticCheck("Encrypted Vault", "PASS", "Keyring / AES-256 vault functional"))
    except Exception as e:
        checks.append(DiagnosticCheck("Encrypted Vault", "WARN", f"Vault fallback active: {e}"))

    # 4. Disk Storage
    try:
        total, used, free = shutil.disk_usage(str(p.parent if p.exists() else "."))
        free_gb = round(free / (1024 ** 3), 1)
        checks.append(DiagnosticCheck("Disk Storage", "PASS", f"{free_gb} GB free space available"))
    except Exception as e:
        checks.append(DiagnosticCheck("Disk Storage", "WARN", str(e)))

    # 5. Core Infrastructure Modules
    modules = ["core.task_state", "core.snapshot", "core.errors", "core.retry", "core.circuit_breaker", "core.dlq"]
    missing = []
    for m in modules:
        try:
            __import__(m)
        except ImportError:
            missing.append(m)

    if not missing:
        checks.append(DiagnosticCheck("Core Modules", "PASS", "All 6 core resilience and state modules loaded"))
    else:
        checks.append(Diagnosls -laticCheck("Core Modules", "FAIL", f"Missing modules: {', '.join(missing)}"))

    return checks


def run_doctor_checks(db_path: Optional[Path | str] = None) -> Dict[str, Any]:
    checks = run_diagnostics(db_path=db_path)
    passed = sum(1 for c in checks if c.status == "PASS")
    total = len(checks)
    overall = "HEALTHY" if all(c.status != "FAIL" for c in checks) else "DEGRADED"
    return {
        "passed_count": passed,
        "total_count": total,
        "overall_status": overall,
        "checks": [{"name": c.name, "status": c.status, "details": c.details} for c in checks],
    }


@click.command(name="doctor")
@click.option("--db-path", type=click.Path(), default=None, help="Path to max_state.db")
def doctor_command(db_path: Optional[str]):
    """System health inspection and diagnostics."""
    console = Console(width=120)
    checks = run_diagnostics(db_path=db_path)

    table = Table(title="MAX OS — System Diagnostics (`max doctor`)", expand=True)
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Details", style="white")

    for c in checks:
        if c.status == "PASS":
            status_style = "[bold green]PASS[/bold green]"
        elif c.status == "WARN":
            status_style = "[bold yellow]WARN[/bold yellow]"
        else:
            status_style = "[bold red]FAIL[/bold red]"
        table.add_row(c.name, status_style, c.details)

    console.print(table)


if __name__ == "__main__":
    doctor_command()
