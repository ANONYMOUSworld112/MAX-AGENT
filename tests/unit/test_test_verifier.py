"""
Unit tests for Task 4.4: Independent Test Verification & Weakening Detection.
"""

import unittest
from core.coding.test_verifier import TestVerifier, TestReport


class TestTestVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = TestVerifier()

    def test_parse_pytest_all_passed(self):
        sample = """
============================= test session starts =============================
collected 20 items

test_one.py ....................                                         [100%]

============================= 20 passed in 1.45s =============================
"""
        report = self.verifier.parse_pytest_output(sample, exit_code=0)
        self.assertEqual(report.passed, 20)
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.total, 20)
        self.assertEqual(report.exit_code, 0)
        self.assertTrue(report.is_success)

    def test_parse_pytest_failures(self):
        sample = """
============================= test session starts =============================
collected 10 items

test_one.py ...F..F...                                                   [100%]

=========================== short test summary info ===========================
FAILED test_one.py::test_fail_1
FAILED test_one.py::test_fail_2
======================== 2 failed, 8 passed in 0.50s ========================
"""
        report = self.verifier.parse_pytest_output(sample, exit_code=1)
        self.assertEqual(report.passed, 8)
        self.assertEqual(report.failed, 2)
        self.assertEqual(report.total, 10)
        self.assertFalse(report.is_success)

    def test_detect_test_weakening(self):
        baseline = TestReport(passed=20, failed=0, total=20, exit_code=0)
        # Agent deleted 5 tests to make a suite "pass"
        weakened = TestReport(passed=15, failed=0, total=15, exit_code=0)

        # Mock run_and_verify or direct evaluation
        violations = []
        if weakened.passed < baseline.passed:
            violations.append(f"Test weakening detected: passed count decreased from {baseline.passed} to {weakened.passed}")

        self.assertTrue(len(violations) > 0)
        self.assertIn("weakening detected", violations[0])


if __name__ == "__main__":
    unittest.main()
