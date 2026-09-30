"""
Unit tests for Task 4.1: CodingExecutor interface and contracts.
"""

import unittest
from core.coding.executor import CodingExecutor, CodingTask, CodingResult


class DummyExecutor(CodingExecutor):
    def execute(self, task: CodingTask, worktree_path: str | None = None) -> CodingResult:
        return CodingResult(
            task_id=task.id,
            success=True,
            modified_files=["main.py"],
            diff="+print('hello')",
            test_passed=True,
            test_output="1 passed in 0.1s",
        )


class TestCodingExecutorInterface(unittest.TestCase):
    def test_coding_task_creation(self):
        task = CodingTask(
            instruction="Build calculator",
            repo_path="/test/repo",
            target_files=["calc.py"],
            test_command="pytest tests/test_calc.py",
        )
        self.assertEqual(task.instruction, "Build calculator")
        self.assertEqual(task.target_files, ["calc.py"])
        self.assertEqual(task.test_command, "pytest tests/test_calc.py")
        self.assertTrue(len(task.id) > 0)

    def test_coding_result_creation(self):
        res = CodingResult(
            task_id="task-123",
            success=True,
            modified_files=["calc.py"],
            diff="+def add(a, b): return a + b",
            test_passed=True,
            test_output="5 passed in 0.2s",
        )
        self.assertEqual(res.task_id, "task-123")
        self.assertTrue(res.success)
        self.assertTrue(res.test_passed)
        self.assertIn("calc.py", res.modified_files)

    def test_executor_subclass_compliance(self):
        executor = DummyExecutor()
        task = CodingTask(instruction="Test")
        result = executor.execute(task)
        self.assertIsInstance(result, CodingResult)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
