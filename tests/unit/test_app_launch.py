"""
Unit tests for Task 3.3: ApplicationRegistry + Guarded Launch + L3 Verification.

Tests:
1. ApplicationRegistry resolves known app names, aliases, and executables.
2. Non-existent apps return NOT_FOUND (None) instead of false success.
3. open_app honestly reports non-existent apps without false claims.
4. L3 verification checks process tables and window handles.
"""

import unittest
from actions.open_app import open_app
from core.adapters import set_desktop_adapter
from core.adapters.fake_desktop import FakeDesktopAdapter
from core.app_registry import ApplicationRegistry, AppSignature


class TestApplicationRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ApplicationRegistry()

    def test_resolve_known_applications(self):
        cases = [
            ("VS Code", "vscode"),
            ("vscode", "vscode"),
            ("visual studio code", "vscode"),
            ("code", "vscode"),
            ("Google Chrome", "chrome"),
            ("chrome", "chrome"),
            ("Calculator", "calculator"),
            ("calc", "calculator"),
            ("Notepad", "notepad"),
            ("terminal", "terminal"),
            ("wt", "terminal"),
        ]
        for query, expected_name in cases:
            with self.subTest(query=query):
                sig = self.registry.resolve(query)
                self.assertIsNotNone(sig, f"Failed to resolve '{query}'")
                self.assertEqual(sig.name, expected_name)

    def test_unknown_application_returns_none(self):
        """Non-existent applications must return None."""
        sig = self.registry.resolve("NonExistentFakeApp99")
        self.assertIsNone(sig)


class TestGuardedOpenApp(unittest.TestCase):
    def setUp(self):
        self.fake_adapter = FakeDesktopAdapter()
        set_desktop_adapter(self.fake_adapter)

    def test_open_non_existent_app_fails_honestly(self):
        """Rule 1-H1: NonExistentFakeApp99 must not return false success."""
        res = open_app({"app_name": "NonExistentFakeApp99"})
        self.assertIn("not found", res.lower())
        self.assertNotIn("opened", res.lower())

    def test_open_empty_name_fails(self):
        res = open_app({"app_name": ""})
        self.assertIn("no application name", res.lower())

    def test_open_already_running_app(self):
        """If window or process is already active, report already running."""
        self.fake_adapter.add_mock_window("Visual Studio Code", "code.exe", 1001, 5001)
        res = open_app({"app_name": "VS Code"})
        self.assertIn("already running", res.lower())

    def test_guarded_launch_delegation(self):
        """Known app triggers launch flow through adapter or process execution."""
        res = open_app({"app_name": "Notepad"})
        # Should either report opened or already running, but definitely not not found
        self.assertTrue("opened" in res.lower() or "already running" in res.lower())


if __name__ == "__main__":
    unittest.main()
