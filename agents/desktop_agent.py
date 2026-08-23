"""
MAX OS — Desktop Agent (Section 8).
Handles Start Menu, taskbar, windows, dialogs, notifications, File Explorer,
Settings, and generic application launching and focusing in real time on the live desktop.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None
import psutil

from core.app_launcher import LiveAppLauncher
from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.state_builder import ComputerStateBuilder, WindowState
from core.verification.engine import VerificationEngine, VerificationOutcome


class DesktopAgent:
    """
    Operating System & Desktop Environment Operator.
    Manages windows, start menu search, dialogs, and application lifecycle in real time.
    """

    def __init__(
        self,
        arbiter: Optional[InputArbiter] = None,
        mouse_controller: Optional[MouseController] = None,
        keyboard_controller: Optional[KeyboardController] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
    ):
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.mouse = mouse_controller or MouseController(arbiter=self.arbiter)
        self.keyboard = keyboard_controller or KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)
        self.state_builder = state_builder or ComputerStateBuilder()
        self.verifier = VerificationEngine()

    def launch_application(
        self,
        app_name_or_cmd: str,
        wait_seconds: float = 1.5,
        lease: Optional[OwnershipLease] = None,
    ) -> bool:
        """
        Launches an actual GUI application on the user's live desktop.
        """
        require_armed(get_kill_switch())
        before = self.state_builder.capture_state()

        # Launch via LiveAppLauncher directly into the user's interactive desktop
        success, hwnd = LiveAppLauncher.launch_live_application(
            app_name_or_path=app_name_or_cmd,
            wait_seconds=wait_seconds,
        )

        after = self.state_builder.capture_state()
        res = self.verifier.verify_window_state(
            expected={"target": app_name_or_cmd},
            before_state=before,
            after_state=after,
        )
        return success or (res.outcome == VerificationOutcome.SUCCESS)

    def open_folder(self, folder_path: str, wait_seconds: float = 1.0) -> bool:
        """Opens a folder in File Explorer on screen."""
        require_armed(get_kill_switch())
        success, _ = LiveAppLauncher.open_live_path(folder_path, wait_seconds=wait_seconds)
        return success

    def focus_window_by_title(
        self, window_title_query: str, lease: Optional[OwnershipLease] = None
    ) -> bool:
        """
        Locates a window matching the title query and brings it to foreground.
        """
        require_armed(get_kill_switch())
        hwnd = LiveAppLauncher.find_and_focus_window(window_title_query)
        return hwnd is not None

    def close_active_window(self, lease: Optional[OwnershipLease] = None) -> bool:
        """Sends Alt+F4 to cleanly close the active foreground window."""
        require_armed(get_kill_switch())
        before = self.state_builder.capture_state()
        if not before.active_window:
            return False

        self.keyboard.hotkey("alt", "f4", lease=lease)
        time.sleep(0.5)

        after = self.state_builder.capture_state()
        res = self.verifier.verify_window_state(
            expected={"target": before.active_window.title, "should_close": True},
            before_state=before,
            after_state=after,
        )
        return res.outcome == VerificationOutcome.SUCCESS

    def dismiss_dialog(self, lease: Optional[OwnershipLease] = None) -> None:
        """Dismisses an active popup/dialog by pressing Escape."""
        self.keyboard.escape(lease=lease)
        time.sleep(0.1)
