"""
MAX OS — Dead Letter Queue Viewer CLI (`max dlq`).
Inspects exhausted-retry tasks with full history and supports requeueing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.dlq import DeadLetterQueue

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@click.command(name="dlq")
@click.option("--list", "-l", "list_all", is_flag=True, default=False, help="List tasks in Dead Letter Queue.")
@click.option("--task-id", "-t", type=str, default=None, help="Inspect detailed history of a DLQ task.")
@click.option("--requeue", "-r", type=str, default=None, help="Mark task as requeued.")
@click.option("--db-path", type=click.Path(), default=None, help="Path to max_state.db.")
def dlq_command(
    list_all: bool,
    task_id: Optional[str],
    requeue: Optional[str],
    db_path: Optional[str],
):
    """Dead Letter Queue inspection and management."""
    console = Console(width=120)
    dlq = DeadLetterQueue(db_path=db_path)

    if requeue:
        success = dlq.mark_requeued(requeue)
        if success:
            console.print(f"[green]Task {requeue} marked as requeued.[/green]")
        else:
            console.print(f"[red]Task {requeue} not found in DLQ.[/red]")
        return

    if task_id:
        record = dlq.get_record(task_id)
        if not record:
            console.print(f"[red]Task {task_id} not found in Dead Letter Queue.[/red]")
            return

        attempts_formatted = json.dumps(record.attempts, indent=2)
        panel_content = (
            f"[bold cyan]Task ID:[/bold cyan] {record.task_id}\n"
            f"[bold magenta]Agent:[/bold magenta] {record.agent}\n"
            f"[bold yellow]Died At:[/bold yellow] {record.died_at}\n"
            f"[bold green]Original Input:[/bold green] {record.original_input}\n"
            f"[bold red]Requeued:[/bold red] {bool(record.requeued)}\n\n"
            f"[bold]Attempt History:[/bold]\n{attempts_formatted}"
        )
        console.print(Panel(panel_content, title=f"DLQ Task: {record.task_id[:8]}", expand=False))
        return

    # Default to listing DLQ
    records = dlq.list_records(include_requeued=True)
    if not records:
        console.print("[green]Dead Letter Queue is empty (0 failed tasks).[/green]")
        return

    table = Table(title="MAX OS — Dead Letter Queue", expand=True)
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Agent", style="magenta")
    table.add_column("Original Input", style="white")
    table.add_column("Attempts", justify="right")
    table.add_column("Died At", style="dim")
    table.add_column("Requeued", style="bold")

    for r in records:
        req_status = "[green]YES[/green]" if r.requeued else "[red]NO[/red]"
        input_preview = r.original_input if len(r.original_input) <= 40 else r.original_input[:37] + "..."
        table.add_row(
            r.task_id[:12],
            r.agent,
            input_preview,
            str(len(r.attempts)),
            r.died_at[:19],
            req_status,
        )

    console.print(table)


if __name__ == "__main__":
    dlq_command()
