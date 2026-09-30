"""
Unit tests for core/plan_validator.py — PlanValidator.
"""

import unittest
from core.capability_registry import CapabilityEntry, CapabilityRegistry
from core.contracts import TaskIntent
from core.plan_validator import PlanValidationError, PlanValidator
from core.task_graph import EdgeCondition, TaskGraph, TaskNode


class TestPlanValidator(unittest.TestCase):
    """Test validation of structural and semantic DAG constraints."""

    def setUp(self):
        self.registry = CapabilityRegistry()
        self.registry.register(CapabilityEntry(name="open_app", description="open application"))
        self.registry.register(CapabilityEntry(name="web_search", description="web search"))
        self.validator = PlanValidator(capability_registry=self.registry)

    def test_valid_graph_passes(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=TaskIntent(action="open_app"))
        n2 = TaskNode(node_id="n2", intent=TaskIntent(action="web_search"))
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge("n1", "n2", EdgeCondition.ON_SUCCESS)

        errors = self.validator.validate(graph)
        self.assertEqual(errors, [])
        self.assertTrue(self.validator.is_valid(graph))
        self.validator.assert_valid(graph)  # does not raise

    def test_empty_graph_fails(self):
        graph = TaskGraph()
        errors = self.validator.validate(graph)
        self.assertIn("TaskGraph contains no nodes", errors)
        self.assertFalse(self.validator.is_valid(graph))

    def test_unknown_capability_fails(self):
        graph = TaskGraph()
        n = TaskNode(node_id="n1", intent=TaskIntent(action="nonexistent_capability_xyz"))
        graph.add_node(n)

        errors = self.validator.validate(graph)
        self.assertTrue(any("unknown capability" in e for e in errors))
        with self.assertRaises(PlanValidationError):
            self.validator.assert_valid(graph)

    def test_over_budget_fails(self):
        graph = TaskGraph(max_nodes=2)
        graph.nodes["n1"] = TaskNode(node_id="n1", intent=TaskIntent(action="open_app"))
        graph.nodes["n2"] = TaskNode(node_id="n2", intent=TaskIntent(action="open_app"))
        graph.nodes["n3"] = TaskNode(node_id="n3", intent=TaskIntent(action="open_app"))

        errors = self.validator.validate(graph)
        self.assertTrue(any("budget" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
