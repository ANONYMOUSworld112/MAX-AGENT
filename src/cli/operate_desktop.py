"""
MAX OS — Human Desktop Operator CLI (`max operate-desktop`).
Enables direct, zero-wrapper hands-free human-like screen control:
  - Takes natural language commands directly.
  - Opens applications via Win+R Run dialog.
  - Navigates browsers, Instagram, Notepad, etc.
  - Zero helper .bat files, zero temporary scripts.
"""

from __future__ import annotations

import click
from rich.console import Console

from core.kill_switch import get_kill_switch
from agents.input_control import InputControlAgent

console = Console(legacy_windows=False)


@click.command("operate-desktop")
@click.option(
    "--command",
    "-c",
    default=None,
    help="Direct natural language instruction (e.g. 'open notepad and write about yourself in E drive').",
)
@click.option(
    "--ephemeral",
    "-e",
    is_flag=True,
    default=False,
    help="Execute via an auto-purging ephemeral .bat runner in E:\\MAX_OS_RUNNERS\\ with zero residual traces.",
)
@click.option(
    "--action",
    "-a",
    type=click.Choice(["instagram", "app", "browser", "smooth-move"], case_sensitive=False),
    default="instagram",
    help="Predefined physical desktop action to execute (if no direct command given).",
)
@click.option("--app", "-p", default="notepad", help="App name or command to launch (if action=app).")
@click.option("--url", "-u", default="https://www.instagram.com/direct/inbox/", help="URL to navigate (if action=browser).")
@click.option("--message", "-m", default="hi", help="Message text to type into chat or editor.")
def operate_desktop_command(command: str | None, ephemeral: bool, action: str, app: str, url: str, message: str):
    """Directly operates your workstation like a human user."""
    ks = get_kill_switch()
    ks.reset()
    ks.arm()

    console.print(f"[bold cyan]MAX OS — Human Desktop Operator[/bold cyan] (Kill Switch: [green]ARMED[/green])")

    if ephemeral and command:
        from core.ephemeral_batch_runner import EphemeralBatchRunner
        console.print(f"⚡ [bold magenta]Ephemeral Runner Active:[/bold magenta] Staging runner in [yellow]E:\\MAX_OS_RUNNERS\\[/yellow]...")
        runner = EphemeralBatchRunner()
        res = runner.execute_instruction_ephemeral(command)
        console.print(f"[bold green]✅ Execution Complete & Auto-Purged:[/bold green] Traces Deleted = {res.get('traces_deleted')}")
        return

    agent = InputControlAgent()

    if command:
        console.print(f"🎯 Processing direct command: '[bold yellow]{command}[/bold yellow]'...")
        res = agent.execute_natural_command(command)
        console.print(f"[bold green]✅ Action Completed:[/bold green] {res.get('action')}")
        return

    if action == "instagram":
        console.print(f"🚀 Executing human-like Brave & Instagram Direct DM flow with message: '[bold yellow]{message}[/bold yellow]'...")
        res = agent.execute_human_instagram_flow(message=message)
        console.print(f"[bold green]✅ Success:[/bold green] Message dispatched to top conversation on Instagram.")

    elif action == "app":
        console.print(f"🚀 Launching application '[bold yellow]{app}[/bold yellow]' via human Win+R dialog...")
        agent.narrate(f"Launching {app} in foreground now, Sir.")
        agent.launch_app_human_mode(app, wait_seconds=1.5)
        if message:
            agent.keyboard.type_text(message + "\n", field_name=f"{app}_input")
        console.print(f"[bold green]✅ Success:[/bold green] '{app}' launched and focused.")

    elif action == "browser":
        console.print(f"🚀 Opening browser to '[bold yellow]{url}[/bold yellow]'...")
        agent.narrate(f"Opening browser to {url}, Sir.")
        agent.open_browser_and_navigate_human(url, wait_seconds=3.0)
        console.print(f"[bold green]✅ Success:[/bold green] Browser navigated to target URL.")

    elif action == "smooth-move":
        console.print("🚀 Executing smooth natural cursor trajectory across screen...")
        agent.mouse.move_to(960, 540, duration=0.6)
        console.print("[bold green]✅ Success:[/bold green] Mouse movement completed.")
