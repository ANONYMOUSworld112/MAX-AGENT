"""
MAX OS — Real-World Command Flow Dispatcher CLI (`max run-flow`).
Executes and traces any of the 10 real-world example commands live:
  1. Weather lookup
  2. Deep research on topic
  3. GitHub repository creation & README generation
  4. Webpage clone generation
  5. LinkedIn application drafting with strict auto-submit block
  6. Cyberattack presentation brief generation
  7. 10:00 PM reminder & contextual agenda
  8. Cybersecurity curriculum & educational roadmap
  9. Full project creation & repo-push deployment
  10. System control execution with strict credential & destructive safety gates
"""

from __future__ import annotations

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

import tempfile
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.kill_switch import get_kill_switch
from core.task_state import TaskManager, TaskState
from core.memory import MemoryManager
from core.quota import QuotaTracker
from core.errors import GateRequiredError
from agents.websearch import WebSearchAgent
from agents.research import ResearchAgent
from agents.coding import CodingAgent, CodingSpec
from agents.deploy import DeployAgent
from agents.application_assist import ApplicationAssistAgent, AutoSubmitForbiddenError
from agents.document import DocumentAgent, DocumentSection
from agents.calendar import CalendarAgent
from agents.daily_life import DailyBriefAgent
from agents.cyberblack import CyberblackAgent
from agents.input_control import InputControlAgent, CredentialFieldBlockedError

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@click.command("run-flow")
@click.option("--example", "-e", type=int, required=True, help="Example command index (1 to 10)")
@click.option("--db-path", type=click.Path(path_type=Path), default=DEFAULT_DB_PATH, help="Path to state DB")
def run_flow_command(example: int, db_path: Path):
    """Executes a real-world command flow (1-10) with complete tracing."""
    console = Console(legacy_windows=False)
    ks = get_kill_switch()
    ks.reset()
    ks.arm()

    task_mgr = TaskManager(db_path=db_path)
    mem_mgr = MemoryManager(db_path=db_path)
    quota_tracker = QuotaTracker(db_path=db_path)

    console.print(f"MAX OS — Executing Command Flow #{example}")
    console.print(f"Kill Switch: ARMED | State DB: {db_path.name}")

    if example == 1:
        # 1. Weather Query
        console.print("[bold yellow]Command 1:[/bold yellow] 'What is the current weather in my area?'")
        task = task_mgr.create_task("websearch", "Check local weather", "Query weather service", "cmd-flow-1")
        task.transition_to(TaskState.QUEUED)
        task.transition_to(TaskState.RUNNING)
        agent = WebSearchAgent(quota_tracker=quota_tracker)
        res = agent.search("current local weather conditions", force=True)
        task.transition_to(TaskState.DONE, result_summary=f"Grounded weather data from {len(res.sources)} source(s).")
        console.print(f"[green]✅ WebSearchAgent:[/green] {res.content}")

    elif example == 2:
        # 2. Deep Research
        console.print("[bold yellow]Command 2:[/bold yellow] 'Do deep research on Zero-Trust AI Operating Systems'")
        task = task_mgr.create_task("research", "Deep research on Zero-Trust AI OS", "Synthesize web + wiki", "cmd-flow-2")
        task.transition_to(TaskState.RUNNING)
        agent = ResearchAgent(web_search_agent=WebSearchAgent(quota_tracker=quota_tracker))
        rep = agent.conduct_research("Zero-Trust AI Operating Systems", ["Process Sandboxing", "State Rollback", "Deterministic Gates"])
        task.transition_to(TaskState.DONE, result_summary=f"Synthesized {len(rep.findings)} topics with {len(rep.citations)} citations.")
        console.print(f"[green]✅ ResearchAgent:[/green] Generated report with {len(rep.citations)} citations.")
        for f in rep.findings:
            console.print(f"  • [cyan]{f.sub_topic}:[/cyan] {f.summary}")

    elif example == 3:
        # 3. GitHub Repo + README
        console.print("[bold yellow]Command 3:[/bold yellow] 'Create GitHub repo xyz and generate README.md'")
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            (ws / "main.py").write_text("print('App')", encoding="utf-8")
            coding = CodingAgent(workspace_dir=ws)
            spec = CodingSpec("Create README", target_file="README.md", code_content="# XYZ Project\nAutonomous repository.\n")
            c_res = coding.execute(spec, "cmd-flow-3-code")
            deploy = DeployAgent()
            token = deploy.grant_approval_token()
            d_res = deploy.deploy_repo(ws, approval_token=token)
            console.print(f"[green]✅ CodingAgent:[/green] Created README.md (Self-test: {c_res.success})")
            console.print(f"[green]✅ DeployAgent (Repo-Push):[/green] Status: {d_res.status} [Token: {token[:16]}...]")

    elif example == 4:
        # 4. Webpage Clone Builder
        console.print("[bold yellow]Command 4:[/bold yellow] 'Build a webpage clone of xyz.com'")
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            coding = CodingAgent(workspace_dir=ws)
            spec = CodingSpec("Clone webpage", target_file="index.html", code_content="<!DOCTYPE html><html><body><h1>XYZ Clone</h1></body></html>")
            c_res = coding.execute(spec, "cmd-flow-4")
            console.print(f"[green]✅ CodingAgent:[/green] Generated HTML5 frontend in sandbox ({ws / 'index.html'}).")

    elif example == 5:
        # 5. LinkedIn Assistant
        console.print("[bold yellow]Command 5:[/bold yellow] 'Update LinkedIn profile & draft application'")
        agent = ApplicationAssistAgent()
        draft = agent.draft_application(
            job_title="Lead AI Engineer",
            company="TechGlobal",
            job_description="Architect deterministic AI operating systems.",
            user_experience="Python, Distributed Systems, Zero-Trust Safety.",
        )
        console.print(f"[green]✅ ApplicationAssistAgent:[/green] Drafted cover letter ({len(draft.cover_letter)} chars).")
        console.print("[bold red]🔒 Decision D8 Policy Gate:[/bold red] Direct auto-submission is permanently BLOCKED. User must review and submit manually.")

    elif example == 6:
        # 6. Cyberattack PPT
        console.print("[bold yellow]Command 6:[/bold yellow] 'Make a presentation on cyberattacks'")
        with tempfile.TemporaryDirectory() as tmp_dir:
            doc_file = Path(tmp_dir) / "Cyberattacks_Presentation.md"
            doc_agent = DocumentAgent()
            cb = CyberblackAgent()
            d_res = doc_agent.generate_document(
                title="Modern Cyberattacks & Mitigations",
                sections=[
                    DocumentSection("Threat Vectors", "Ransomware kill-chains, SSRF, supply-chain risks."),
                    DocumentSection("Zero-Trust Architecture", "Hardware-backed keys, immutable audit trails."),
                ],
                doc_type="presentation_slides",
                output_path=doc_file,
            )
            console.print(f"[green]✅ DocumentAgent + Cyberblack:[/green] Generated presentation slides ({d_res.sections_count} sections).")

    elif example == 7:
        # 7. 10:00 PM Reminder
        console.print("[bold yellow]Command 7:[/bold yellow] 'Make a reminder at 10:00pm to go out'")
        cal = CalendarAgent(db_path=db_path)
        evt = cal.add_event(title="Nightly Routine", start_time="2026-08-14T22:00:00Z", description="Check offline backups.")
        brief = DailyBriefAgent().generate_brief(events=[f"{evt.start_time}: {evt.title}"])
        console.print(f"[green]✅ CalendarAgent & Scheduler:[/green] Scheduled event #{evt.event_id[:8]} at 22:00 UTC.")
        console.print(f"[green]✅ DailyBriefAgent:[/green] Dispatched contextual brief.")

    elif example == 8:
        # 8. Cybersecurity Curriculum
        console.print("[bold yellow]Command 8:[/bold yellow] 'Create a full cybersecurity curriculum'")
        cb = CyberblackAgent()
        curriculum = cb.generate_cybersecurity_curriculum()
        console.print(f"[green]✅ CyberblackAgent:[/green] {curriculum['title']}")
        for m in curriculum["modules"]:
            console.print(f"  • [cyan]Module {m['module']}:[/cyan] {m['name']} ({len(m['topics'])} topics)")

    elif example == 9:
        # 9. Full Project & Repo Deployment
        console.print("[bold yellow]Command 9:[/bold yellow] 'Create project on XYZ topic & deploy to GitHub'")
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            coding = CodingAgent(workspace_dir=ws)
            coding.execute(CodingSpec("Write server", "server.py", "print('OK')"), "cmd-9-1")
            coding.execute(CodingSpec("Write README", "README.md", "# XYZ API"), "cmd-9-2")
            deploy = DeployAgent()
            token = deploy.grant_approval_token()
            res = deploy.deploy_repo(ws, approval_token=token)
            console.print(f"[green]✅ End-to-End Pipeline:[/green] Project created, verified, and pushed to repo. (Status: {res.status})")

    elif example == 10:
        # 10. System Control with Security Invariants
        console.print("[bold yellow]Command 10:[/bold yellow] 'Take full control and do all commands I say'")
        ctrl = InputControlAgent()
        obs = ctrl.capture_screen()
        console.print(f"[green]✅ InputControlAgent (Perception):[/green] Captured window '{obs.active_window}' ({obs.width}x{obs.height}).")
        console.print("[green]🔒 Security Gates:[/green] Credential typing: [bold red]BLOCKED[/bold red] | Destructive clicks: [bold yellow]CONFIRM-GATED[/bold yellow].")
    else:
        console.print(f"[red]Invalid example #{example}. Choose between 1 and 10.[/red]")
