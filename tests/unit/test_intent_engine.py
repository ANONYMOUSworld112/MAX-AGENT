"""
Unit tests for core/intent_engine.py — IntentEngine, Fast Path, and Compound Decomposition.
Includes verification against all 25 golden benchmark tasks.
"""

import json
import unittest
from pathlib import Path

from core.contracts import TaskIntent
from core.intent_engine import IntentEngine
from core.task_graph import TaskGraph


class TestIntentEngineFastPath(unittest.TestCase):
    """Test single-intent fast path parsing."""

    def setUp(self):
        self.engine = IntentEngine()

    def test_open_app(self):
        res = self.engine.parse("Open Chrome.")
        self.assertIsInstance(res, TaskIntent)
        self.assertEqual(res.action, "open_app")
        self.assertEqual(res.target, "chrome")

    def test_play_media(self):
        res = self.engine.parse("Play Believer by Imagine Dragons.")
        self.assertIsInstance(res, TaskIntent)
        self.assertEqual(res.action, "youtube_video")
        self.assertIn("believer", res.target.lower())

    def test_reminder(self):
        res = self.engine.parse("Remind me in 10 minutes.")
        self.assertIsInstance(res, TaskIntent)
        self.assertEqual(res.action, "set_reminder")

    def test_emergency_stop(self):
        res = self.engine.parse("Emergency stop!")
        self.assertIsInstance(res, TaskIntent)
        self.assertEqual(res.action, "kill_switch")

    def test_undo(self):
        res = self.engine.parse("Undo last action.")
        self.assertIsInstance(res, TaskIntent)
        self.assertEqual(res.action, "undo")


class TestIntentEngineCompound(unittest.TestCase):
    """Test multi-step compound request decomposition into TaskGraph."""

    def setUp(self):
        self.engine = IntentEngine()

    def test_sequential_open_and_search(self):
        res = self.engine.parse("Open Chrome and search for Python.")
        self.assertIsInstance(res, TaskGraph)
        self.assertEqual(len(res.nodes), 2)
        self.assertEqual(len(res.edges), 1)

        # Edge from open -> search
        edge = res.edges[0]
        self.assertEqual(edge.from_node, "step_1_open")
        self.assertEqual(edge.to_node, "step_2_search")

    def test_sequential_open_and_create(self):
        res = self.engine.parse("Open VS Code and create a file.")
        self.assertIsInstance(res, TaskGraph)
        self.assertEqual(len(res.nodes), 2)
        self.assertEqual(len(res.edges), 1)

    def test_parallel_build_and_remind(self):
        res = self.engine.parse("Build my project and remind me at 8.")
        self.assertIsInstance(res, TaskGraph)
        self.assertEqual(len(res.nodes), 2)
        # Parallel execution: 0 edges between them
        self.assertEqual(len(res.edges), 0)
        self.assertIn("task_build", res.nodes)
        self.assertIn("task_remind", res.nodes)


class TestGoldenBenchmarkRoutingAccuracy(unittest.TestCase):
    """
    Test IntentEngine against all 25 golden benchmark tasks.
    Target: >= 95% routing accuracy (up from 76% in Phase 0 baseline).
    """

    def test_golden_tasks_routing_accuracy(self):
        baseline_file = Path(__file__).resolve().parent.parent.parent / "docs" / "evidence" / "p0" / "evals_baseline.json"
        self.assertTrue(baseline_file.exists(), f"Missing {baseline_file}")

        with open(baseline_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        engine = IntentEngine()
        tasks = data["results"]
        correct_count = 0

        for t in tasks:
            task_id = t["task_id"]
            prompt = t["prompt"]
            expected = t["expected_route"]

            actual = engine.route_name(prompt)
            is_correct = (actual == expected)
            if is_correct:
                correct_count += 1
            else:
                # Log any discrepancy for diagnostic clarity
                print(f"Task {task_id} mismatch: prompt='{prompt}', expected='{expected}', actual='{actual}'")

        accuracy = (correct_count / len(tasks)) * 100.0
        print(f"\nGolden Tasks Route Accuracy: {correct_count}/{len(tasks)} ({accuracy:.1f}%)")
        self.assertGreaterEqual(accuracy, 95.0, f"Routing accuracy {accuracy}% below 95% threshold")


if __name__ == "__main__":
    unittest.main()
