"""
Unit tests for core/task_graph.py — TaskGraph, TaskNode, TaskEdge.
"""

import unittest
from core.contracts import TaskIntent
from core.task_graph import (
    BudgetExceededError,
    CycleDetectedError,
    EdgeCondition,
    NodeStatus,
    TaskEdge,
    TaskGraph,
    TaskNode,
)


def _make_intent(action: str, raw: str = "") -> TaskIntent:
    return TaskIntent(action=action, raw_input=raw or f"run {action}")


class TestTaskGraphBasic(unittest.TestCase):
    """Test node addition, serialization, and budget limits."""

    def test_add_nodes_and_serialization(self):
        graph = TaskGraph(graph_id="g1")
        n1 = TaskNode(node_id="step1", intent=_make_intent("open_app"))
        n2 = TaskNode(node_id="step2", intent=_make_intent("web_search"))

        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge("step1", "step2", EdgeCondition.ON_SUCCESS)

        data = graph.to_dict()
        self.assertEqual(data["graph_id"], "g1")
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 1)

        # Round trip
        restored = TaskGraph.from_dict(data)
        self.assertEqual(restored.graph_id, "g1")
        self.assertEqual(len(restored.nodes), 2)
        self.assertEqual(restored.nodes["step2"].dependencies, {"step1"})

    def test_budget_exceeded(self):
        graph = TaskGraph(max_nodes=3)
        for i in range(3):
            graph.add_node(TaskNode(node_id=f"n{i}", intent=_make_intent(f"act{i}")))

        with self.assertRaises(BudgetExceededError):
            graph.add_node(TaskNode(node_id="n3", intent=_make_intent("overflow")))


class TestTopologicalSortAndCycles(unittest.TestCase):
    """Test dependency ordering and cycle detection."""

    def test_linear_chain(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("a1"))
        n2 = TaskNode(node_id="n2", intent=_make_intent("a2"))
        n3 = TaskNode(node_id="n3", intent=_make_intent("a3"))
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        graph.add_edge("n1", "n2")
        graph.add_edge("n2", "n3")

        order = [node.node_id for node in graph.topological_sort()]
        self.assertEqual(order, ["n1", "n2", "n3"])

    def test_diamond_dag(self):
        # A -> B, A -> C, B -> D, C -> D
        graph = TaskGraph()
        for nid in ["A", "B", "C", "D"]:
            graph.add_node(TaskNode(node_id=nid, intent=_make_intent(nid)))

        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("B", "D")
        graph.add_edge("C", "D")

        order = [node.node_id for node in graph.topological_sort()]
        self.assertEqual(order[0], "A")
        self.assertEqual(order[-1], "D")
        self.assertIn("B", order[1:3])
        self.assertIn("C", order[1:3])

    def test_cycle_detection_on_add_edge(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("a1"))
        n2 = TaskNode(node_id="n2", intent=_make_intent("a2"))
        graph.add_node(n1)
        graph.add_node(n2)

        graph.add_edge("n1", "n2")
        with self.assertRaises(CycleDetectedError):
            graph.add_edge("n2", "n1")  # Cycle!


class TestConditionalExecution(unittest.TestCase):
    """Test get_ready_nodes under various edge conditions."""

    def test_on_success_condition(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("build"))
        n2 = TaskNode(node_id="n2", intent=_make_intent("deploy"))
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge("n1", "n2", EdgeCondition.ON_SUCCESS)

        # Initially, only n1 is ready
        ready = graph.get_ready_nodes(completed_nodes=set(), failed_nodes=set())
        self.assertEqual([n.node_id for n in ready], ["n1"])

        # Once n1 succeeds, n2 is ready
        ready_after = graph.get_ready_nodes(completed_nodes={"n1"}, failed_nodes=set())
        self.assertEqual([n.node_id for n in ready_after], ["n2"])

        # If n1 fails, n2 is NOT ready
        ready_fail = graph.get_ready_nodes(completed_nodes=set(), failed_nodes={"n1"})
        self.assertEqual(ready_fail, [])

    def test_on_failure_condition(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("deploy"))
        n_rollback = TaskNode(node_id="rollback", intent=_make_intent("rollback"))
        graph.add_node(n1)
        graph.add_node(n_rollback)
        graph.add_edge("n1", "rollback", EdgeCondition.ON_FAILURE)

        # If n1 succeeds, rollback is not ready
        self.assertEqual(graph.get_ready_nodes(completed_nodes={"n1"}, failed_nodes=set()), [])

        # If n1 fails, rollback IS ready
        ready = graph.get_ready_nodes(completed_nodes=set(), failed_nodes={"n1"})
        self.assertEqual([n.node_id for n in ready], ["rollback"])

    def test_always_condition(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("task"))
        n_cleanup = TaskNode(node_id="cleanup", intent=_make_intent("cleanup"))
        graph.add_node(n1)
        graph.add_node(n_cleanup)
        graph.add_edge("n1", "cleanup", EdgeCondition.ALWAYS)

        # Cleanup runs on success OR failure
        self.assertEqual(len(graph.get_ready_nodes(completed_nodes={"n1"}, failed_nodes=set())), 1)
        self.assertEqual(len(graph.get_ready_nodes(completed_nodes=set(), failed_nodes={"n1"})), 1)

    def test_parallel_compound_request(self):
        # "Build project and remind me at 8" -> 2 independent root nodes
        graph = TaskGraph()
        n_build = TaskNode(node_id="build", intent=_make_intent("codingagent", "Build project"))
        n_remind = TaskNode(node_id="remind", intent=_make_intent("set_reminder", "Remind me at 8"))
        graph.add_node(n_build)
        graph.add_node(n_remind)

        # Both are immediately ready (parallel execution)
        ready = graph.get_ready_nodes(completed_nodes=set(), failed_nodes=set())
        self.assertEqual(set(n.node_id for n in ready), {"build", "remind"})

    def test_is_complete(self):
        graph = TaskGraph()
        n1 = TaskNode(node_id="n1", intent=_make_intent("a1"))
        graph.add_node(n1)
        self.assertFalse(graph.is_complete())

        n1.status = NodeStatus.COMPLETED
        self.assertTrue(graph.is_complete())


if __name__ == "__main__":
    unittest.main()
