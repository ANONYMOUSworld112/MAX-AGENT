"""
MAX-AGENT TaskGraph Engine
===========================

Directed Acyclic Graph (DAG) data structure for multi-step task
decomposition and execution planning.

Features:
  - TaskNode: atomic unit of execution with TaskIntent and status
  - TaskEdge: dependency links with conditions (ALWAYS, ON_SUCCESS, ON_FAILURE)
  - Topological sort with Kahn's algorithm for execution ordering
  - Cycle detection preventing deadlocks
  - Expansion budget enforcement (default max 20 nodes)
  - Ready-node evaluation considering dependency outcomes
  - Full serialization round-trip for StateDB persistence

Master Spec references:
  - Section 8 (Task Execution, multi-step graphs)
  - Section 9 (TaskGraph representation)
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.contracts import ActionResult, Task, TaskIntent, _new_id


class EdgeCondition(str, Enum):
    """Conditions governing edge traversal between task nodes."""
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"


class NodeStatus(str, Enum):
    """Execution status of an individual graph node."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CycleDetectedError(Exception):
    """Raised when a dependency cycle is detected in the TaskGraph."""
    pass


class BudgetExceededError(Exception):
    """Raised when graph node count exceeds the configured expansion budget."""
    pass


@dataclass
class TaskEdge:
    """Directed dependency edge between two TaskNodes."""
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ON_SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "condition": self.condition.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskEdge:
        return cls(
            from_node=data["from_node"],
            to_node=data["to_node"],
            condition=EdgeCondition(data.get("condition", "on_success")),
        )


@dataclass
class TaskNode:
    """A single executable node in the TaskGraph."""
    node_id: str
    intent: TaskIntent
    task: Optional[Task] = None
    status: NodeStatus = NodeStatus.PENDING
    dependencies: set[str] = field(default_factory=set)
    result: Optional[ActionResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "intent": self.intent.to_dict(),
            "task": self.task.to_dict() if self.task else None,
            "status": self.status.value,
            "dependencies": sorted(list(self.dependencies)),
            "result": self.result.to_dict() if self.result else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskNode:
        intent = TaskIntent.from_dict(data["intent"])
        task = Task.from_dict(data["task"]) if data.get("task") else None
        result = ActionResult.from_dict(data["result"]) if data.get("result") else None
        return cls(
            node_id=data["node_id"],
            intent=intent,
            task=task,
            status=NodeStatus(data.get("status", "pending")),
            dependencies=set(data.get("dependencies", [])),
            result=result,
        )


class TaskGraph:
    """
    Directed Acyclic Graph representing a decomposed multi-step plan.
    """

    DEFAULT_MAX_NODES = 20

    def __init__(self, graph_id: Optional[str] = None, max_nodes: int = DEFAULT_MAX_NODES) -> None:
        self.graph_id = graph_id or _new_id()
        self.max_nodes = max_nodes
        self.nodes: dict[str, TaskNode] = {}
        self.edges: list[TaskEdge] = []

    def add_node(self, node: TaskNode) -> None:
        """Add a TaskNode to the graph, enforcing the node budget."""
        if len(self.nodes) >= self.max_nodes:
            raise BudgetExceededError(
                f"Cannot add node '{node.node_id}': graph has reached maximum budget of {self.max_nodes} nodes"
            )
        self.nodes[node.node_id] = node

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: EdgeCondition = EdgeCondition.ON_SUCCESS,
    ) -> None:
        """Add a dependency edge (from_node must execute before to_node)."""
        if from_node not in self.nodes:
            raise KeyError(f"Source node '{from_node}' does not exist in graph")
        if to_node not in self.nodes:
            raise KeyError(f"Target node '{to_node}' does not exist in graph")

        edge = TaskEdge(from_node=from_node, to_node=to_node, condition=condition)
        self.edges.append(edge)
        self.nodes[to_node].dependencies.add(from_node)

        # Validate that adding this edge did not introduce a cycle
        self.topological_sort()

    def topological_sort(self) -> list[TaskNode]:
        """
        Sort nodes in dependency order using Kahn's algorithm.

        Raises CycleDetectedError if a cycle exists.
        """
        in_degree: dict[str, int] = {node_id: 0 for node_id in self.nodes}
        adj: dict[str, list[str]] = defaultdict(list)

        for edge in self.edges:
            adj[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1

        queue = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        sorted_nodes: list[TaskNode] = []

        while queue:
            curr = queue.popleft()
            sorted_nodes.append(self.nodes[curr])

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(self.nodes):
            remaining = [nid for nid, deg in in_degree.items() if deg > 0]
            raise CycleDetectedError(f"Dependency cycle detected involving nodes: {remaining}")

        return sorted_nodes

    def get_ready_nodes(
        self,
        completed_nodes: set[str],
        failed_nodes: set[str],
    ) -> list[TaskNode]:
        """
        Find all PENDING nodes whose dependencies have been satisfied.

        Evaluates edge conditions:
          - ON_SUCCESS: dependency must be in completed_nodes
          - ON_FAILURE: dependency must be in failed_nodes
          - ALWAYS: dependency must be in completed_nodes OR failed_nodes
        """
        ready: list[TaskNode] = []

        # Map edges arriving at each node
        incoming_edges: dict[str, list[TaskEdge]] = defaultdict(list)
        for edge in self.edges:
            incoming_edges[edge.to_node].append(edge)

        for node_id, node in self.nodes.items():
            if node.status != NodeStatus.PENDING:
                continue
            if node_id in completed_nodes or node_id in failed_nodes:
                continue

            edges = incoming_edges.get(node_id, [])
            if not edges:
                # No dependencies -> ready immediately
                ready.append(node)
                continue

            # Check if all incoming edge conditions are satisfied
            satisfied = True
            for edge in edges:
                dep = edge.from_node
                cond = edge.condition

                if cond == EdgeCondition.ON_SUCCESS:
                    if dep not in completed_nodes:
                        satisfied = False
                        break
                elif cond == EdgeCondition.ON_FAILURE:
                    if dep not in failed_nodes:
                        satisfied = False
                        break
                elif cond == EdgeCondition.ALWAYS:
                    if dep not in completed_nodes and dep not in failed_nodes:
                        satisfied = False
                        break

            if satisfied:
                ready.append(node)

        return ready

    def is_complete(self) -> bool:
        """Check if all nodes in the graph have reached a terminal state."""
        terminal_statuses = {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED}
        return all(node.status in terminal_statuses for node in self.nodes.values())

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary for JSON/StateDB storage."""
        return {
            "graph_id": self.graph_id,
            "max_nodes": self.max_nodes,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskGraph:
        """Deserialize graph from dictionary."""
        graph = cls(graph_id=data["graph_id"], max_nodes=data.get("max_nodes", cls.DEFAULT_MAX_NODES))
        for nid, ndata in data.get("nodes", {}).items():
            graph.nodes[nid] = TaskNode.from_dict(ndata)
        for edata in data.get("edges", []):
            graph.edges.append(TaskEdge.from_dict(edata))
        return graph
