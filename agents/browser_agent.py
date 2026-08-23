"""
MAX OS — Browser Agent (Section 8).
Operates web browsers (Brave, Chrome, Edge), tabs, address bar navigation,
web searches, and page-state observation live on the user's interactive desktop.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from core.app_launcher import LiveAppLauncher
from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.browser_dom import BrowserAccessibilityEngine, BrowserSnapshot
from core.perception.state_builder import ComputerStateBuilder
from core.verification.engine import VerificationEngine, VerificationOutcome
from tasks.task_system import Task
from tools.backends.browser_tool import BrowserAutomationTool
from tools.interfaces import BrowserTool


class BrowserAgent:
    """
    Browser Operator.
    Drives browser windows, tabs, URL navigation, and in-browser semantic interaction in real time.
    Uses BrowserAutomationTool via BrowserTool interface seam.
    """

    def __init__(
        self,
        arbiter: Optional[InputArbiter] = None,
        mouse_controller: Optional[MouseController] = None,
        keyboard_controller: Optional[KeyboardController] = None,
        browser_engine: Optional[BrowserAccessibilityEngine] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
        browser_tool: Optional[BrowserTool] = None,
    ):
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.mouse = mouse_controller or MouseController(arbiter=self.arbiter)
        self.keyboard = keyboard_controller or KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)
        self.browser_engine = browser_engine or BrowserAccessibilityEngine()
        self.state_builder = state_builder or ComputerStateBuilder()
        self.verifier = VerificationEngine()
        self.browser_tool = browser_tool or BrowserAutomationTool()

    def launch_browser(
        self,
        browser_preference: str = "msedge",
        initial_url: str = "https://google.com",
        lease: Optional[OwnershipLease] = None,
    ) -> bool:
        """Launches the browser with the requested URL visually on screen."""
        require_armed(get_kill_switch())
        self.browser_tool.navigate(initial_url)
        success, hwnd = LiveAppLauncher.open_live_url(
            url=initial_url,
            browser=browser_preference,
            wait_seconds=2.0,
        )
        return success

    def navigate_to(
        self, url: str, wait_seconds: float = 2.0, lease: Optional[OwnershipLease] = None
    ) -> bool:
        """
        Navigates to URL in the active live browser or opens it directly on screen.
        """
        require_armed(get_kill_switch())
        self.browser_tool.navigate(url)
        before = self.state_builder.capture_state()

        if before.active_window and any(b in before.active_window.process_name.lower() for b in ("edge", "chrome", "brave", "firefox")):
            self.keyboard.hotkey("ctrl", "l", lease=lease)
            time.sleep(0.2)
            self.keyboard.type_text(url, human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(wait_seconds)
        else:
            LiveAppLauncher.open_live_url(url=url, wait_seconds=wait_seconds)

        after = self.state_builder.capture_state()
        res = self.verifier.verify_browser_navigation(
            expected={"url": url},
            before_state=before,
            after_state=after,
        )
        return res.outcome == VerificationOutcome.SUCCESS or bool(after.browser.url)

    def search(
        self, query: str, engine: str = "google", lease: Optional[OwnershipLease] = None
    ) -> bool:
        """Executes a search query in the live browser."""
        self.browser_tool.search(query)
        encoded = urllib.parse.quote_plus(query)
        if engine.lower() == "youtube":
            url = f"https://www.youtube.com/results?search_query={encoded}"
        else:
            url = f"https://www.google.com/search?q={encoded}"

        return self.navigate_to(url, wait_seconds=2.5, lease=lease)

    def new_tab(self, lease: Optional[OwnershipLease] = None) -> None:
        """Opens a new browser tab via Ctrl+T."""
        self.keyboard.hotkey("ctrl", "t", lease=lease)
        time.sleep(0.5)

    def close_tab(self, lease: Optional[OwnershipLease] = None) -> None:
        """Closes the current browser tab via Ctrl+W."""
        self.keyboard.hotkey("ctrl", "w", lease=lease)
        time.sleep(0.4)

    def scroll_page(self, direction: str = "down", amount: int = 5, lease: Optional[OwnershipLease] = None) -> None:
        """Scrolls the active webpage on screen."""
        self.mouse.scroll(direction=direction, amount=amount, lease=lease)


def browser_agent_executor(task: Task) -> Any:
    """
    Standard agent_executor interface signature: def agent_executor(task: Task) -> Any
    """
    agent = BrowserAgent()
    success = agent.search(task.description)
    return {"search": task.description, "success": success}
