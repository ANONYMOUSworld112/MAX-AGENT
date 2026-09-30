"""
Unit tests for Task 4.3: LocalDevWorker implementing CodingExecutor.
"""

import tempfile
import unittest
from pathlib import Path

from core.coding.executor import CodingTask, CodingResult
from core.coding.local_dev_worker import LocalDevWorker
from core.coding.test_verifier import TestReport, TestVerifier


class MockTestVerifier(TestVerifier):
    def __init__(self, succeed: bool = True):
        self.succeed = succeed

    def run_and_verify(self, worktree_path, test_command="pytest", baseline_report=None, timeout=60.0):
        if self.succeed:
            rep = TestReport(passed=5, failed=0, total=5, exit_code=0, raw_output="5 passed in 0.1s")
            return True, rep, []
        else:
            rep = TestReport(passed=3, failed=2, total=5, exit_code=1, raw_output="2 failed, 3 passed")
            return False, rep, ["Test suite had 2 failing tests"]


class TestLocalDevWorker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.temp_dir.name) / "repo"
        self.repo_dir.mkdir()
        (self.repo_dir / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_coding_execution(self):
        def fake_llm(instruction, targets):
            return {"calc.py": "def add(a, b): return a + b\ndef sub(a, b): return a - b\n"}

        worker = LocalDevWorker(
            code_generator_fn=fake_llm,
            test_verifier=MockTestVerifier(succeed=True),
        )

        task = CodingTask(
            instruction="Add subtraction function",
            repo_path=str(self.repo_dir),
            target_files=["calc.py"],
        )

        result = worker.execute(task)
        self.assertIsInstance(result, CodingResult)
        self.assertTrue(result.success)
        self.assertTrue(result.test_passed)
        self.assertIn("calc.py", result.modified_files)

    def test_failed_tests_prevent_success_report(self):
        """Rule 1-H1: Coding worker cannot report SUCCESS if test suite fails."""
        worker = LocalDevWorker(
            code_generator_fn=lambda inst, targets: {"calc.py": "broken code"},
            test_verifier=MockTestVerifier(succeed=False),
        )

        task = CodingTask(
            instruction="Fix bug",
            repo_path=str(self.repo_dir),
            target_files=["calc.py"],
        )

        result = worker.execute(task)
        self.assertFalse(result.success)
        self.assertFalse(result.test_passed)
        self.assertIsNotNone(result.error_message)


if __name__ == "__main__":
    unittest.main()
