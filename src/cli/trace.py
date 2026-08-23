"""
MAX OS — Trace Log Viewer CLI (Step 1.6).
Inspects `task_trace` without touching SQLite directly.
Supports `--last N`, `--agent <name>`, `--failures-only`, and `--task-id <id>`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.console import Console
from rich.table import Table

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


def query_traces(
    db_path: Optional[Path | str] = None,
    last: Optional[int] = 20,
    agent: Optional[str] = None,
    failures_only: bool = False,
    task_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetches records from task_trace table based on filter criteria."""
    db_file = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not db_file.exists():
        return []

    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    conditions = []
    params: List[Any] = []

    if task_id:
        conditions.append("task_id = ?")
        params.append(task_id)

    if agent:
        conditions.append("agent = ?")
        params.append(agent)

    if failures_only:
        conditions.append("(state IN ('FAILED', 'ROLLED_BACK') OR error_class IS NOT NULL)")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = f"LIMIT {int(last)}" if last and last > 0 else ""

    query = f"""
        SELECT task_id, idempotency_key, agent, intent, input_summary,
               priority_band, state, error_class, attempt_count,
               created_at, completed_at, duration_ms, result_summary
        FROM task_trace
        {where_clause}
        ORDER BY created_at DESC
        {limit_clause}
    """

    try:
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def render_trace_table(records: List[Dict[str, Any]], console: Optional[Console] = None) -> Table:
    """Renders records into a Rich table."""
    table = Table(title="MAX OS — Task Trace Log", show_lines=False, expand=True)
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Agent", style="magenta", overflow="fold")
    table.add_column("Intent", style="blue", overflow="fold")
    table.add_column("State", style="bold", overflow="fold")
    table.add_column("Error", style="red", overflow="fold")
    table.add_column("Duration", justify="right")
    table.add_column("Summary", style="green", overflow="fold")
    table.add_column("Created At", style="dim")

    for r in records:
        state = r["state"]
        state_style = "green" if state == "DONE" else ("red" if state in ("FAILED", "ROLLED_BACK") else "yellow")
        dur = f"{r['duration_ms']}ms" if r["duration_ms"] is not None else "-"
        err = r["error_class"] or "-"
        summary = r["result_summary"] or r["input_summary"] or "-"

        table.add_row(
            r["task_id"][:8],
            r["agent"],
            r["intent"],
            f"[{state_style}]{state}[/{state_style}]",
            err,
            dur,
            summary,
            r["created_at"][:19],
        )

    return table


@click.command(name="trace")
@click.option("--last", "-n", default=20, type=int, help="Number of recent tasks to display.")
@click.option("--agent", "-a", type=str, default=None, help="Filter by agent name.")
@click.option("--failures-only", is_flag=True, default=False, help="Show only failed or rolled-back tasks.")
@click.option("--task-id", type=str, default=None, help="Show details for a specific task ID.")
@click.option("--db-path", type=click.Path(), default=None, help="Path to max_state.db.")
def trace_command(
    last: int,
    agent: Optional[str],
    failures_only: bool,
    task_id: Optional[str],
    db_path: Optional[str],
):
    """Inspect MAX task trace log."""
    console = Console(width=120)
    records = query_traces(
        db_path=db_path,
        last=last,
        agent=agent,
        failures_only=failures_only,
        task_id=task_id,
    )

    if not records:
        console.print("[yellow]No trace records found matching criteria.[/yellow]")
        return

    table = render_trace_table(records, console=console)
    console.print(table)


if __name__ == "__main__":
    trace_command()
