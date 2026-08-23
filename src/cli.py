"""
MAX OS — Command Line Interface (CLI)
Build Order: #26 (Layer 6B)
═══════════════════════════════════════════════════════

Thin CLI client. Communicates with daemon/API and formats rich output.
"""

from __future__ import annotations

import sys
import click
import requests
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()
API_BASE_URL = "http://127.0.0.1:8000/api"


@click.group()
def cli():
    """MAX AI Operating System CLI."""
    pass


@cli.command()
def status():
    """Show system status and health telemetry."""
    try:
        r = requests.get(f"{API_BASE_URL}/status", timeout=2)
        data = r.json()

        table = Table(title="MAX AI OS Telemetry Status")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")

        table.add_row("Status", data["status"])
        table.add_row("Version", data["version"])
        table.add_row("CPU Load", f"{data['cpu_percent']}%")
        table.add_row("RAM Usage", f"{data['ram_percent']}% ({data['ram_used_gb']}GB / {data['ram_total_gb']}GB)")
        table.add_row("Uptime", f"{data['uptime_hours']} hours")
        table.add_row("Active Tasks", str(data["active_tasks_count"]))
        table.add_row("Kill Switch Armed", "YES" if data["kill_switch_armed"] else "NO")

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Failed to connect to MAX daemon API:[/bold red] {e}")


@cli.command()
@click.argument("prompt")
@click.option("--model", default="MAX-Reasoning-v4", help="AI model target")
def execute(prompt: str, model: str):
    """Execute a command prompt in MAX OS."""
    try:
        r = requests.post(f"{API_BASE_URL}/prompt/execute", json={"prompt": prompt, "model": model}, timeout=5)
        data = r.json()
        console.print(f"[bold green]Dispatched Task:[/bold green] {data['response_summary']}")
    except Exception as e:
        console.print(f"[bold red]Execution error:[/bold red] {e}")


@cli.command()
def trace():
    """View task execution trace logs."""
    try:
        r = requests.get(f"{API_BASE_URL}/tasks", timeout=2)
        tasks = r.json().get("tasks", [])

        table = Table(title="MAX OS Task Trace Logs")
        table.add_column("Task ID", style="dim")
        table.add_column("Agent", style="cyan")
        table.add_column("Intent", style="yellow")
        table.add_column("State", style="bold green")
        table.add_column("Input Summary")

        for t in tasks[:15]:
            table.add_row(t["task_id"][:8], t["agent"], t["intent"], t["state"], t["input_summary"][:40])

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Failed to fetch trace logs:[/bold red] {e}")


@cli.command()
@click.option("--reason", default="CLI manual trigger", help="Reason for kill signal")
def kill(reason: str):
    """Trigger the Kill Switch to stop all tasks immediately."""
    try:
        r = requests.post(f"{API_BASE_URL}/kill", json={"reason": reason}, timeout=2)
        console.print(f"[bold red]KILL SWITCH ACTIVATED:[/bold red] {r.json()['reason']}")
    except Exception as e:
        console.print(f"[bold red]Kill switch call error:[/bold red] {e}")


if __name__ == "__main__":
    cli()
