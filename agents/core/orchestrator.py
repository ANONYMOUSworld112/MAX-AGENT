"""Agent 1: Master Orchestrator.

Root task coordinator. Evaluates complex user goals, decides execution topology
(DAG vs Pipeline vs Reflex), and dispatches subtasks across the 33-agent ecosystem.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.orchestrator")


class MasterOrchestrator(BaseAgent):
    name = "MasterOrchestrator"
    description = "Root task coordinator that orchestrates multi-agent execution graphs."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        goal = input_data.task_description or "Execute scheduled daily goals"
        params = input_data.parameters or {}
        logger.info("MasterOrchestrator coordinating goal: %s", goal)

        # Map goal domains to agent clusters
        plan_steps: List[Dict[str, Any]] = []
        low_goal = goal.lower()

        if any(w in low_goal for w in ["meeting", "calendar", "schedule", "standup"]):
            plan_steps.append({"step": 1, "agent": "CalendarAgent", "action": "check_daily_schedule", "target": "calendar"})
        if any(w in low_goal for w in ["email", "inbox", "mail"]):
            plan_steps.append({"step": len(plan_steps) + 1, "agent": "EmailAgent", "action": "triage_inbox", "target": "inbox"})
        if any(w in low_goal for w in ["task", "todo", "reminder", "deadline"]):
            plan_steps.append({"step": len(plan_steps) + 1, "agent": "TaskTracker", "action": "list_pending_tasks", "target": "tasks"})
        if any(w in low_goal for w in ["code", "bug", "pr", "repo", "github", "pull request", "review", "git"]):
            plan_steps.append({"step": len(plan_steps) + 1, "agent": "CodingAgent", "action": "review_and_implement", "target": "workspace"})
        if any(w in low_goal for w in ["system", "pc", "computer", "health", "cpu"]):
            plan_steps.append({"step": len(plan_steps) + 1, "agent": "SystemMonitorAgent", "action": "collect_telemetry", "target": "host_os"})

        if not plan_steps:
            plan_steps = [
                {"step": 1, "agent": "DecompositionPlanner", "action": "decompose_goal", "target": goal},
                {"step": 2, "agent": "ValidationVerifier", "action": "verify_completion", "target": "deliverables"},
            ]

        executed_results = []
        should_execute = params.get("execute", True) and not params.get("plan_only", False) and not params.get("dry_run", False)
        if should_execute:
            from agents.router import AgentRegistry
            registry = AgentRegistry.get_instance()
            for step in plan_steps:
                ag_name = step.get("agent")
                ag = registry.get(ag_name)
                if ag:
                    sub_in = AgentInput(
                        task_id=f"{input_data.task_id}-sub-{step['step']}",
                        task_description=f"{step['action']} for {step['target']}",
                        parameters=params.get(ag_name.lower(), {}),
                    )
                    sub_out = ag.run(sub_in)
                    executed_results.append({
                        "step": step["step"],
                        "agent": ag_name,
                        "success": sub_out.success,
                        "result": sub_out.result,
                    })

        execution_plan = {
            "orchestrator": self.name,
            "goal": goal,
            "topology": "Sequential-DAG",
            "total_subtasks": len(plan_steps),
            "subtasks": plan_steps,
            "status": "COMPLETED" if executed_results else "DISPATCHED",
            "executed_results": executed_results,
        }

        if executed_results:
            summary = f"Orchestrated and executed {len(executed_results)} subtask(s): " + ", ".join(f"{r['agent']}={'OK' if r['success'] else 'ERR'}" for r in executed_results)
        else:
            summary = f"Orchestrated goal into {len(plan_steps)} subtask(s): " + ", ".join(f"{s['agent']}:{s['action']}" for s in plan_steps)

        return AgentOutput(
            success=all(r["success"] for r in executed_results) if executed_results else True,
            result=summary,
            artifacts={"execution_plan": execution_plan},
        )
