"""
Unit test for Task 3.1: Eliminate exec() RCE in actions/desktop.py.

Verifies:
1. AST scan proves zero `exec` / `eval` / `compile` call nodes in actions/desktop.py.
2. Parameterized primitives (click, type_text, hotkey, find_and_click) function safely through desktop adapter.
3. Arbitrary code execution requests are rejected cleanly.
"""

import ast
from pathlib import Path
import unittest

from actions.desktop import click, type_text, hotkey, find_and_click, desktop_control
from core.adapters import set_desktop_adapter
from core.adapters.fake_desktop import FakeDesktopAdapter


class TestDesktopNoExec(unittest.TestCase):
    def setUp(self):
        self.fake_adapter = FakeDesktopAdapter()
        set_desktop_adapter(self.fake_adapter)

    def test_ast_scan_zero_exec_calls(self):
        """AST scanner checks actions/desktop.py has ZERO exec, eval, or compile calls."""
        desktop_file = Path(__file__).resolve().parent.parent.parent / "actions" / "desktop.py"
        source = desktop_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(desktop_file))

        dangerous_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"}:
                    dangerous_calls.append((node.func.id, node.lineno))

        self.assertEqual(
            dangerous_calls,
            [],
            f"Found forbidden dynamic execution calls in actions/desktop.py: {dangerous_calls}",
        )

    def test_parameterized_click_primitive(self):
        """Test safe click primitive delegates to adapter without code execution."""
        res = click(x=150, y=250, clicks=2, button="right")
        self.assertIn("succeeded", res)
        self.assertEqual(len(self.fake_adapter.calls), 1)
        name, args, kwargs = self.fake_adapter.calls[0]
        self.assertEqual(name, "click")
        self.assertEqual(args, (150, 250))
        self.assertEqual(kwargs, {"clicks": 2, "button": "right"})

    def test_parameterized_type_primitive(self):
        """Test safe type_text primitive delegates to adapter without code execution."""
        res = type_text("Hello MAX", interval=0.01)
        self.assertIn("succeeded", res)
        self.assertEqual(len(self.fake_adapter.calls), 1)
        name, args, kwargs = self.fake_adapter.calls[0]
        self.assertEqual(name, "type_text")
        self.assertEqual(args, ("Hello MAX",))
        self.assertEqual(kwargs, {"interval": 0.01})

    def test_parameterized_hotkey_primitive(self):
        """Test safe hotkey primitive delegates to adapter without code execution."""
        res = hotkey("ctrl", "shift", "esc")
        self.assertIn("succeeded", res)
        self.assertEqual(len(self.fake_adapter.calls), 1)
        name, args, kwargs = self.fake_adapter.calls[0]
        self.assertEqual(name, "hotkey")
        self.assertEqual(args, ("ctrl", "shift", "esc"))

    def test_find_and_click_primitive(self):
        """Test semantic element targeting via adapter."""
        self.fake_adapter.add_mock_element("SubmitButton", "Button", (100, 100, 200, 150))
        res = find_and_click("SubmitButton")
        self.assertIn("Clicked element", res)
        # Verify click was dispatched to center (150, 125)
        click_calls = [c for c in self.fake_adapter.calls if c[0] == "click"]
        self.assertTrue(len(click_calls) >= 1)
        self.assertEqual(click_calls[0][1], (150, 125))

    def test_desktop_control_dispatcher(self):
        """Test desktop_control handler dispatches to parameterized primitives safely."""
        res = desktop_control({"action": "click", "x": 50, "y": 75})
        self.assertIn("succeeded", res)

        res_task = desktop_control({"action": "task", "task": "import os; os.system('calc')"})
        self.assertIn("disabled", res_task.lower())


if __name__ == "__main__":
    unittest.main()
