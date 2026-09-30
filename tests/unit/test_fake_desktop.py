"""
Unit tests for Task 3.2: Desktop Adapters (FakeDesktopAdapter & UIA Semantic Targeting).

Tests:
1. Fake adapter records all clicks, text inputs, and hotkeys.
2. Semantic UIA element finding and clicking by control name/type.
3. Window listing, active window tracking, and focus switching.
4. WindowsDesktopAdapter fallback and method compliance.
"""

import unittest
from core.adapters.fake_desktop import FakeDesktopAdapter
from core.adapters.windows_desktop import WindowsDesktopAdapter


class TestFakeDesktopAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeDesktopAdapter()

    def test_record_primitives(self):
        self.assertTrue(self.adapter.click(100, 200, clicks=2, button="left"))
        self.assertTrue(self.adapter.type_text("Search query"))
        self.assertTrue(self.adapter.hotkey("win", "r"))

        self.assertEqual(len(self.adapter.calls), 3)
        self.assertEqual(self.adapter.calls[0][0], "click")
        self.assertEqual(self.adapter.calls[1][0], "type_text")
        self.assertEqual(self.adapter.calls[2][0], "hotkey")

    def test_semantic_element_targeting(self):
        self.adapter.add_mock_element("SaveButton", "Button", (300, 400, 380, 430))
        self.adapter.add_mock_element("UsernameInput", "Edit", (300, 450, 500, 480))

        # Find element by name
        elem = self.adapter.find_element(name="SaveButton")
        self.assertIsNotNone(elem)
        self.assertEqual(elem["control_type"], "Button")

        # Find element by control_type
        edit = self.adapter.find_element(control_type="Edit")
        self.assertIsNotNone(edit)
        self.assertEqual(edit["name"], "UsernameInput")

        # Click element directly
        ok = self.adapter.click_element("SaveButton")
        self.assertTrue(ok)
        # Center of (300, 400, 380, 430) is (340, 415)
        click_calls = [c for c in self.adapter.calls if c[0] == "click"]
        self.assertEqual(click_calls[-1][1], (340, 415))

    def test_window_management(self):
        self.adapter.add_mock_window("Calculator", "calc.exe", 1001, 5001)
        self.adapter.add_mock_window("Visual Studio Code", "code.exe", 1002, 5002)

        windows = self.adapter.list_windows()
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0]["title"], "Calculator")

        # Initial active window is the first added
        active = self.adapter.get_active_window()
        self.assertIsNotNone(active)
        self.assertEqual(active["title"], "Calculator")

        # Focus other window by title substring
        ok = self.adapter.focus_window("Code")
        self.assertTrue(ok)
        self.assertEqual(self.adapter.get_active_window()["title"], "Visual Studio Code")


class TestWindowsDesktopAdapterContract(unittest.TestCase):
    def test_interface_compliance(self):
        """Verify WindowsDesktopAdapter implements all DesktopAdapter abstract methods."""
        win_adapter = WindowsDesktopAdapter()
        self.assertTrue(hasattr(win_adapter, "click"))
        self.assertTrue(hasattr(win_adapter, "type_text"))
        self.assertTrue(hasattr(win_adapter, "hotkey"))
        self.assertTrue(hasattr(win_adapter, "find_element"))
        self.assertTrue(hasattr(win_adapter, "click_element"))
        self.assertTrue(hasattr(win_adapter, "list_windows"))
        self.assertTrue(hasattr(win_adapter, "get_active_window"))
        self.assertTrue(hasattr(win_adapter, "focus_window"))


if __name__ == "__main__":
    unittest.main()
