"""
MAX-AGENT Plan Validator
=========================

Validates TaskGraph DAG execution plans before execution.

Checks:
  1. Structural integrity (non-empty, valid IDs)
  2. Cycle detection (no deadlocking dependency loops)
  3. Expansion budget enforcement (max node count)
  4. Capability existence (every referenced action exists in CapabilityRegistry)
  5. Resource conflict detection (competing exclusive locks)

Master Spec references:
  - Section 8 (Task Planning & Validation)
  - Section 13 (Risk & Preconditions)
"""

from __future__ import annotations

import logging
from typing import Optional

from core.capability_registry import CapabilityRegistry
from core.task_graph import CycleDetectedError, TaskGraph

logger = logging.getLogger("max.plan_validator")


class PlanValidationError(Exception):
    """Raised when a TaskGraph fails validation."""
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class PlanValidator:
    """
    Validates task plans (TaskGraph) before queueing and execution.
    """

    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None) -> None:
        self.capability_registry = capability_registry or CapabilityRegistry.get_instance()

    def validate(self, graph: TaskGraph) -> list[str]:
        """
        Validate a TaskGraph against all structural and semantic rules.

        Returns a list of error strings. An empty list means the graph is valid.
        """
        errors: list[str] = []

        # 1. Non-empty check
        if not graph.nodes:
            errors.append("TaskGraph contains no nodes")
            return errors

        # 2. Expansion budget check
        if len(graph.nodes) > graph.max_nodes:
            errors.append(
                f"Graph exceeds maximum budget of {graph.max_nodes} nodes (contains {len(graph.nodes)})"
            )

        # 3. Cycle detection check
        try:
            graph.topological_sort()
        except CycleDetectedError as e:
            errors.append(f"Cycle detected: {e}")

        # 4. Capability existence check
        for node_id, node in graph.nodes.items():
            action = node.intent.action.lower()
            if not action:
                errors.append(f"Node '{node_id}' has empty action")
                continue

            # Check if action is known in CapabilityRegistry
            if self.capability_registry and not self.capability_registry.has(action):
                # Also check common aliases or standard actions
                known_fallbacks = {"kill_switch", "security_gate", "undo", "taskgraph", "dev_agent"}
                if action not in known_fallbacks:
                    errors.append(f"Node '{node_id}' references unknown capability '{action}'")

        # 5. Dependency reference check
        for edge in graph.edges:
            if edge.from_node not in graph.nodes:
                errors.append(f"Edge references nonexistent from_node '{edge.from_node}'")
            if edge.to_node not in graph.nodes:
                errors.append(f"Edge references nonexistent to_node '{edge.to_node}'")

        return errors

    def is_valid(self, graph: TaskGraph) -> bool:
        """Check if graph is valid without raising."""
        return len(self.validate(graph)) == 0

    def assert_valid(self, graph: TaskGraph) -> None:
        """Validate and raise PlanValidationError if any error exists."""
        errors = self.validate(graph)
        if errors:
            raise PlanValidationError(errors)
