"""
MAX OS — Dependency Graph Planner (Step 2.6).
Decomposes multi-agent tasks into an acyclic dependency graph (DAG) and executes them in topological order.
Example: 'Build it, deploy it, remind me' -> [Coding Agent, Deploy Agent, Calendar Agent].
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


class CyclicDependencyError(Exception):
    """Raised when a dependency cycle is detected in the execution plan."""
    pass


@dataclass
class PlanNode:
    node_id: str
    agent: str
    intent: str
    description: str
    spec: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    nodes: Dict[str, PlanNode] = field(default_factory=dict)

    def add_node(self, node: PlanNode) -> None:
        self.nodes[node.node_id] = node

    def get_topological_order(self) -> List[PlanNode]:
        """Returns nodes in valid topological execution order. Raises CyclicDependencyError if cyclic."""
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        graph: Dict[str, List[str]] = {node_id: [] for node_id in self.nodes}

        for node_id, node in self.nodes.items():
            for dep in node.depends_on:
                if dep in graph:
                    graph[dep].append(node_id)
                    in_degree[node_id] += 1

        queue = collections.deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        ordered: List[PlanNode] = []

        while queue:
            curr_id = queue.popleft()
            ordered.append(self.nodes[curr_id])
            for neighbor in graph[curr_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(self.nodes):
            raise CyclicDependencyError("Cyclic dependency detected in execution plan DAG.")

        return ordered


class DependencyPlanner:
    """
    Dependency Planner.
    Analyzes complex user intents and decomposes them into ordered multi-agent subtasks.
    """

    def decompose(self, multi_agent_request: str) -> ExecutionPlan:
        plan = ExecutionPlan()
        text = multi_agent_request.lower()

        # Check for multi-action components
        has_build = bool(re.search(r"\b(build|code|write|create script|implement)\b", text))
        has_deploy = bool(re.search(r"\b(deploy|push|publish|release)\b", text))
        has_remind = bool(re.search(r"\b(remind|schedule|calendar|meeting)\b", text))
        has_note = bool(re.search(r"\b(note|save notes|document)\b", text))

        last_node_id: Optional[str] = None

        if has_build:
            node_id = "step-1-build"
            plan.add_node(
                PlanNode(
                    node_id=node_id,
                    agent="coding",
                    intent="write_code",
                    description="Build requested code",
                    spec={"prompt": multi_agent_request},
                    depends_on=[],
                )
            )
            last_node_id = node_id

        if has_deploy:
            node_id = "step-2-deploy"
            deps = [last_node_id] if last_node_id else []
            plan.add_node(
                PlanNode(
                    node_id=node_id,
                    agent="deploy",
                    intent="deploy_repo",
                    description="Deploy built artifacts",
                    spec={"commit_message": "deploy: automated build"},
                    depends_on=deps,
                )
            )
            last_node_id = node_id

        if has_remind:
            node_id = "step-3-remind"
            deps = [last_node_id] if last_node_id else []
            plan.add_node(
                PlanNode(
                    node_id=node_id,
                    agent="calendar",
                    intent="add_reminder",
                    description="Create follow-up reminder / event",
                    spec={"title": "Check deployment status", "start_time": "2026-08-15T09:00:00Z"},
                    depends_on=deps,
                )
            )

        if has_note:
            node_id = "step-4-note"
            deps = [last_node_id] if last_node_id else []
            plan.add_node(
                PlanNode(
                    node_id=node_id,
                    agent="notes",
                    intent="create_note",
                    description="Record project notes",
                    spec={"title": "Build and Deploy Summary"},
                    depends_on=deps,
                )
            )

        return plan
