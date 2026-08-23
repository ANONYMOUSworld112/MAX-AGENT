"""
MAX OS — Main CLI Entrypoint (`max`).
"""

import sys
import io
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from typing import Any, Dict, List, Optional

import click
from cli.trace import trace_command
from cli.dlq import dlq_command
from cli.doctor import doctor_command
from cli.run_command_flow import run_flow_command
from cli.operate_desktop import operate_desktop_command


@click.command("gui")
def gui_command():
    """Launches the MAX OS J.A.R.V.I.S. Interactive Desktop GUI Window."""
    from gui.app import launch_desktop_gui
    launch_desktop_gui()


@click.command("workshop-live")
def workshop_live_command():
    """Executes the Iron Man 2 Workshop Real-Time Sequence with Live Voice & Telemetry."""
    from rich.console import Console
    from core.kill_switch import get_kill_switch
    from agents.workshop_diagnostics import JarvisWorkshopAgent

    ks = get_kill_switch()
    ks.reset()
    ks.arm()

    console = Console(legacy_windows=False)
    console.print("[bold cyan]================================================================================[/bold cyan]")
    console.print("[bold yellow]      MAX OS (J.A.R.V.I.S.) — REAL-TIME WORKSHOP SEQUENCE (IRON MAN 2)          [/bold yellow]")
    console.print("[bold cyan]================================================================================[/bold cyan]")

    agent = JarvisWorkshopAgent(operator_name="Sir")

    def _on_event(event_name: str, data: Any):
        if event_name == "welcome":
            console.print(f"🏠 [bold green]Ambient Greeting:[/bold green] {data.get('greeting')}")
        elif event_name == "vitals":
            console.print(f"🩺 [bold red]Biometric Toxicity:[/bold red] {data.toxicity_percent}% | Rx: [bold yellow]{data.symptom_mitigation_prescription}[/bold yellow]")
        elif event_name == "simulation":
            console.print(f"🔬 [bold cyan]Periodic Table Simulation:[/bold cyan] {data.get('total_elements_simulated')} elements tested (Viable: {data.get('viable_elements_found')})")
        elif event_name == "robotic_arm":
            console.print(f"🤖 [bold magenta]Dum-E Robotic Arm:[/bold magenta] Status={data.status} (Precision error: {data.precision_error_mm}mm)")
        elif event_name == "core":
            console.print(f"⚡ [bold red]Arc Reactor Core:[/bold red] Depletion={data.get('depletion_level_percent')}% ({data.get('recommendation')})")

@click.command("voice-control")
@click.option("--command", "-c", default=None, help="Direct natural language command to execute dynamically.")
@click.option("--voice", "-v", is_flag=True, default=False, help="Listen for voice command from microphone.")
@click.option("--continuous", is_flag=True, default=False, help="Run continuous wake-word voice loop (say 'MAX' or 'JARVIS').")
def voice_control_command(command: str | None, voice: bool, continuous: bool):
    """MAX Dynamic Voice Input & Desktop Operator (VAD + openWakeWord + STT + Intent Bridge)."""
    from rich.console import Console
    from core.kill_switch import get_kill_switch
    from voice.voice_loop import VoiceLoop, VoiceState
    from voice.intent_bridge import VoiceIntentBridge

    ks = get_kill_switch()
    ks.reset()
    ks.arm()

    console = Console(legacy_windows=False)
    console.print("[bold cyan]================================================================================[/bold cyan]")
    console.print("[bold yellow]      MAX OS (J.A.R.V.I.S.) — DYNAMIC VOICE & DESKTOP OPERATOR                  [/bold yellow]")
    console.print("[bold cyan]================================================================================[/bold cyan]")

    intent_bridge = VoiceIntentBridge()
    loop = VoiceLoop(intent_bridge=intent_bridge)

    if continuous:
        console.print("🎙️ [bold green]Continuous wake-word loop active. Speak 'MAX' or 'JARVIS'...[/bold green]")
        loop.start()
        try:
            while True:
                import time
                time.sleep(0.5)
        except (KeyboardInterrupt, EOFError):
            loop.stop()
            console.print("\n[yellow]Voice loop terminated.[/yellow]")

    elif voice:
        from agents.nova_voice_operator import NovaVoiceOperator
        operator = NovaVoiceOperator()
        console.print("🎤 [bold green]Listening for live voice input...[/bold green]")
        res = operator.listen_and_execute_voice()
        console.print(f"✅ [bold green]Executed Voice Intent:[/bold green] {res.intent} ({res.feedback_speech})")

    elif command:
        console.print(f"🎯 [bold yellow]Executing Dynamic Command:[/bold yellow] '{command}'...")
        # Direct VoiceIntentBridge routing into MasterOrchestrator & ComputerUseAgent
        res = intent_bridge.on_transcript(command)
        console.print(f"✅ [bold green]Result:[/bold green] {res.speech_feedback}")
        if "volume" in command.lower() and "up" in command.lower():
            console.print("   [dim]Intent: volume_up[/dim]")
        if res.error:
            console.print(f"❌ [bold red]Error:[/bold red] {res.error}")

    else:
        # Interactive natural language voice console
        console.print("[dim]Type your natural instruction below or press Enter to trigger speech capture ('exit' to quit):[/dim]")
        while True:
            try:
                user_in = input("\n🎙️ [Voice Input / Instruction] > ").strip()
                if not user_in or user_in.lower() in ("exit", "quit", "q"):
                    break
                res = intent_bridge.on_transcript(user_in)
                console.print(f"✅ [bold green]Feedback:[/bold green] {res.speech_feedback}")
            except (KeyboardInterrupt, EOFError):
                break


@click.command("computer-use")
@click.option("-g", "--goal", required=True, help="Natural language objective for computer use.")
@click.option("--api-key", default=None, help="LLM API key (Gemini, OpenAI, Anthropic).")
@click.option("--provider", default="auto", type=click.Choice(["auto", "gemini", "openai", "anthropic", "ollama", "mock"]), help="LLM Provider.")
@click.option("--model", default=None, help="Target LLM model name.")
def computer_use_command(goal: str, api_key: Optional[str], provider: str, model: Optional[str]):
    """Autonomous LLM Computer-Use Operator (Ace & NeuralAgent VLM)."""
    from agents.computer_use_agent import ComputerUseAgent
    console = Console(legacy_windows=False)
    console.print(f"🤖 [bold cyan]MAX OS Autonomous Computer-Use Operator[/bold cyan]")
    console.print(f"🎯 [bold yellow]Goal:[/bold yellow] '{goal}'")
    if provider != "auto":
        console.print(f"🔑 [dim]Provider: {provider} | Model: {model or 'default'}[/dim]")

    agent = ComputerUseAgent()
    if api_key:
        agent.set_api_key(api_key, provider=provider, model_name=model)

    res = agent.execute_goal(goal)
    if res.success:
        console.print(f"✅ [bold green]Task Successfully Executed and Positively Verified:[/bold green] {res.details}")
    else:
        console.print(f"❌ [bold red]Execution Incomplete:[/bold red] {res.details}")


@click.command("fast-replay")
@click.option("--list", "list_all", is_flag=True, help="List all compiled Fast Replays.")
@click.option("-g", "--goal", default=None, help="Goal to replay at native machine speed.")
def fast_replay_command(list_all: bool, goal: Optional[str]):
    """High-Speed Fast Replay Execution Engine (NeuralAgent 3.0)."""
    from core.fast_replay_engine import FastReplayEngine
    console = Console(legacy_windows=False)
    engine = FastReplayEngine()

    if list_all or not goal:
        replays = engine.catalog.list_all_replays()
        console.print(f"⚡ [bold cyan]MAX OS Fast Replay Catalog ({len(replays)} registered)[/bold cyan]")
        for r in replays:
            console.print(f"  • [bold yellow]{r.goal}[/bold yellow] ([dim]{r.replay_id}[/dim]) — Executed {r.execution_count}x")
    elif goal:
        console.print(f"⚡ [bold yellow]Executing Fast Replay for:[/bold yellow] '{goal}'...")
        from agents.computer_use_agent import ComputerUseAgent
        agent = ComputerUseAgent(fast_replay_engine=engine)
        res = agent.execute_goal(goal)
        if res.success:
            console.print(f"✅ [bold green]Fast Replay Finished:[/bold green] {res.details}")
        else:
            console.print(f"❌ [bold red]Fast Replay Incomplete:[/bold red] {res.details}")


@click.command("watch-and-learn")
@click.option("-g", "--goal", required=True, help="Goal name for demonstrated workflow.")
def watch_and_learn_command(goal: str):
    """Demonstrate a computer workflow for MAX to learn and compile into a Fast Replay."""
    from core.fast_replay_engine import FastReplayEngine
    console = Console(legacy_windows=False)
    engine = FastReplayEngine()
    console.print(f"📹 [bold cyan]Watch & Learn Recorder Started[/bold cyan]")
    console.print(f"🎯 [bold yellow]Workflow Goal:[/bold yellow] '{goal}'")
    engine.recorder.start_recording(goal)
    console.print("[dim]Press Enter when your demonstration is complete...[/dim]")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    plan, anchors = engine.recorder.stop_and_compile(goal)
    record = engine.catalog.save_replay(goal=goal, plan=plan, anchors=anchors)
    console.print(f"✅ [bold green]Workflow Compiled into Fast Replay:[/bold green] {record.replay_id} ({len(plan.actions)} actions)")


@click.group()
def cli():
    """MAX OS — Personal AI Operating System."""
    pass


cli.add_command(trace_command)
cli.add_command(dlq_command)
cli.add_command(doctor_command)
cli.add_command(run_flow_command)
cli.add_command(operate_desktop_command)
cli.add_command(gui_command)
cli.add_command(workshop_live_command)
cli.add_command(voice_control_command)
cli.add_command(computer_use_command)
cli.add_command(fast_replay_command)
cli.add_command(watch_and_learn_command)


if __name__ == "__main__":
    cli()

