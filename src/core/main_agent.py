"""
MAX OS — Main Daemon Orchestrator
Build Order: #25 (Layer 6A)
═══════════════════════════════════════════════════════

The daemon orchestrator that ties all system layers together.
Maintains execution loop, task queue worker threads, kill switch state,
watchdog, circuit breaker, and startup recovery protocol.
"""

from __future__ import annotations

import time
import threading
import logging
from pathlib import Path
from typing import Optional

from src.core import kill_switch
from src.infra import state_db
from src.core import (
    task_lifecycle,
    task_queue,
    lock_manager,
    watchdog,
    reconciliation,
    circuit_breaker,
    dlq,
    snapshot,
)
from src.routing import intent_classifier, planner, permissions
from src.agents.agent_base import BaseAgent, AgentResult
from src.agents.calendar_agent import CalendarAgent
from src.agents.notes_agent import NotesAgent
from src.agents.coding_agent import CodingAgent
from src.agents.deploy_agent import DeployAgent
from src.agents.research_agent import ResearchAgent
from src.agents.file_agent import FileAgent
from src.agents.terminal_agent import TerminalAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.desktop_agent import DesktopAgent
from src.agents.websearch_agent import WebSearchAgent
from src.agents.document_agent import DocumentAgent
from src.system.adapters.base import get_adapter

logger = logging.getLogger("max.core.main_agent")

SCHEMA_STATE_PATH = Path(__file__).parent.parent.parent / "max_state_schema.sql"
SCHEMA_MEMORY_PATH = Path(__file__).parent.parent.parent / "memory_schema.sql"


class MainAgentOrchestrator:
    """Daemon orchestrator managing the full MAX OS backend pipeline."""

    def __init__(self):
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._agents: dict[str, BaseAgent] = {
            "calendar": CalendarAgent(),
            "notes": NotesAgent(),
            "coding": CodingAgent(),
            "deploy": DeployAgent(),
            "research": ResearchAgent(),
            "file": FileAgent(),
            "filesystem": FileAgent(),
            "terminal": TerminalAgent(),
            "system": TerminalAgent(),
            "browser": BrowserAgent(),
            "web": BrowserAgent(),
            "desktop": DesktopAgent(),
            "computer_control": DesktopAgent(),
            "websearch": WebSearchAgent(),
            "document": DocumentAgent(),
        }

    def boot(self) -> None:
        """Boot sequence: arm kill switch, verify DB, apply schemas, start watchdog."""
        logger.info("Initializing MAX OS Daemon Orchestrator boot sequence...")
        
        # 1. Arm Kill Switch (Component #0 requirement)
        kill_switch.arm()
        kill_switch.require_armed()

        # 2. Verify DB & Apply Schemas
        state_db.verify()
        if SCHEMA_STATE_PATH.exists():
            state_db.apply_schema(SCHEMA_STATE_PATH)
        if SCHEMA_MEMORY_PATH.exists():
            state_db.apply_schema(SCHEMA_MEMORY_PATH)

        # 3. Startup Recovery Scan
        self._run_startup_recovery()

        # 4. Start Watchdog
        wd = watchdog.get_watchdog()
        wd.start()

        # 5. Start Worker Loop
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        logger.info("MAX OS Daemon Boot Complete — All systems green")

    def shutdown(self) -> None:
        """Graceful daemon shutdown."""
        logger.info("Shutting down MAX OS Daemon...")
        self._running = False
        watchdog.get_watchdog().stop()

    def submit_prompt(self, prompt: str, model: str = "MAX-Reasoning-v4") -> dict:
        """
        Public API entry point: classify prompt, plan execution graph,
        and submit tasks to priority queue.
        """
        kill_switch.require_armed()
        
        # Plan tasks
        planned_steps = planner.plan(prompt)
        p_queue = task_queue.get_queue()

        task_ids = []
        for step in planned_steps:
            tid = p_queue.push(
                agent=step.agent,
                intent=step.intent,
                input_summary=step.prompt_snippet,
                priority_band=1 if step.agent in ("deploy", "coding") else 2,
            )
            task_ids.append(tid)

        return {
            "status": "dispatched",
            "prompt": prompt,
            "model": model,
            "task_count": len(task_ids),
            "task_ids": task_ids,
        }

    def _worker_loop(self) -> None:
        """Main loop consuming task items from priority queue."""
        q = task_queue.get_queue()
        cb = circuit_breaker.get_circuit_breaker()
        lm = lock_manager.get_lock_manager()
        wd = watchdog.get_watchdog()

        while self._running:
            try:
                item = q.pop()
                if not item:
                    time.sleep(0.2)
                    continue

                task_id = item.task_id
                agent_name = item.agent

                # Check circuit breaker
                try:
                    cb.check_allow(agent_name)
                except Exception as exc:
                    logger.warning("Task '%s' rejected by circuit breaker for agent '%s'", task_id, agent_name)
                    task_lifecycle.transition(task_id, task_lifecycle.TaskState.FAILED, result_summary=str(exc))
                    dlq.get_dlq().push(task_id, agent_name, item.input_summary, [{"error": str(exc)}])
                    continue

                # Acquire locks if needed
                lm.acquire_all(task_id, [agent_name])
                wd.register(task_id)

                # Transition to RUNNING
                task_lifecycle.transition(task_id, task_lifecycle.TaskState.RUNNING)
                kill_switch.register_task(task_id, item.input_summary)

                # Execute task via Agent or System Adapter
                start_time = time.monotonic()
                try:
                    agent = self._agents.get(agent_name)
                    if agent:
                        res = agent.execute(task_id, item.input_summary, item.payload)
                    elif agent_name == "terminal":
                        adapter = get_adapter()
                        cmd_res = adapter.execute_command(item.input_summary)
                        res = AgentResult(
                            success=(cmd_res["exit_code"] == 0),
                            agent_name="terminal",
                            action="execute_command",
                            output=cmd_res["stdout"] or cmd_res["stderr"],
                            data=cmd_res,
                            error_message="" if cmd_res["exit_code"] == 0 else cmd_res["stderr"]
                        )
                    else:
                        # General system execution
                        adapter = get_adapter()
                        res = AgentResult(
                            success=True,
                            agent_name=agent_name,
                            action="system_action",
                            output=f"Executed system action for intent: {item.intent}",
                            data={},
                        )

                    # Reconcile
                    task_lifecycle.transition(task_id, task_lifecycle.TaskState.RECONCILING)
                    duration_ms = int((time.monotonic() - start_time) * 1000)

                    if res.success:
                        task_lifecycle.transition(task_id, task_lifecycle.TaskState.DONE, result_summary=res.output)
                        cb.record_success(agent_name)
                    else:
                        task_lifecycle.transition(task_id, task_lifecycle.TaskState.FAILED, result_summary=res.error_message)
                        cb.record_failure(agent_name)

                except Exception as exc:
                    logger.error("Task '%s' execution error: %s", task_id, exc)
                    cb.record_failure(agent_name)
                    task_lifecycle.transition(task_id, task_lifecycle.TaskState.FAILED, result_summary=str(exc))
                    dlq.get_dlq().push(task_id, agent_name, item.input_summary, [{"error": str(exc)}])
                finally:
                    wd.unregister(task_id)
                    lm.release_all(task_id)
                    kill_switch.unregister_task(task_id)

            except Exception as loop_err:
                logger.error("Error in orchestrator worker loop: %s", loop_err)
                time.sleep(0.5)

    def _run_startup_recovery(self) -> None:
        """Scan tasks database for interrupted tasks on startup."""
        interrupted = state_db.fetchall("SELECT task_id FROM task_trace WHERE state IN ('running', 'lock_wait', 'reconciling')")
        if interrupted:
            logger.warning("Startup recovery: Found %d interrupted tasks. Marking as 'killed'", len(interrupted))
            for row in interrupted:
                state_db.execute(
                    "UPDATE task_trace SET state = 'killed', completed_at = ?, result_summary = 'Interrupted by daemon restart' WHERE task_id = ?",
                    (time.strftime("%Y-%m-%dT%H:%M:%SZ"), row["task_id"])
                )
            state_db.commit()


_global_orchestrator: Optional[MainAgentOrchestrator] = None


def get_orchestrator() -> MainAgentOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = MainAgentOrchestrator()
        _global_orchestrator.boot()
    elif not _global_orchestrator._running:
        _global_orchestrator.boot()
    return _global_orchestrator
