"""
MAX OS — Application Agent & Universal Unknown Application Operator (Section 8 & Section 15).
Coordinates application adapters with the strict lifecycle:
  DISCOVER -> CONNECT -> OBSERVE -> INTERACT -> VERIFY
Provides the autonomous Unknown Application Protocol for interacting with previously unseen apps.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import win32gui
except Exception:
    win32gui = None

from applications.base_adapter import BaseApplicationAdapter
from applications.browser_adapter import BrowserAdapter
from applications.file_explorer_adapter import FileExplorerAdapter
from applications.office_adapter import OfficeAdapter
from applications.terminal_adapter import TerminalAdapter
from applications.vscode_adapter import VSCodeAdapter
from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.memory import MemoryManager
from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.perception.state_builder import ComputerState, ComputerStateBuilder, WindowState
from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationResult


class ApplicationAgent:
    """
    Master Application Operator.
    Dispatches to specialized adapters for common apps or executes the
    autonomous Unknown Application Protocol for new/unseen software.
    """

    def __init__(
        self,
        arbiter: Optional[InputArbiter] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.state_builder = state_builder or ComputerStateBuilder()
        self.memory = memory_manager or MemoryManager()
        self.verifier = VerificationEngine()
        self.mouse = MouseController(arbiter=self.arbiter)
        self.keyboard = KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)
        self.uia = UIAccessibilityEngine()

        # Register specialized adapters
        self.adapters: List[BaseApplicationAdapter] = [
            VSCodeAdapter(arbiter=self.arbiter, mouse=self.mouse, keyboard=self.keyboard, state_builder=self.state_builder),
            BrowserAdapter(arbiter=self.arbiter, mouse=self.mouse, keyboard=self.keyboard, state_builder=self.state_builder),
            FileExplorerAdapter(arbiter=self.arbiter, mouse=self.mouse, keyboard=self.keyboard, state_builder=self.state_builder),
            TerminalAdapter(arbiter=self.arbiter, mouse=self.mouse, keyboard=self.keyboard, state_builder=self.state_builder),
            OfficeAdapter(arbiter=self.arbiter, mouse=self.mouse, keyboard=self.keyboard, state_builder=self.state_builder),
        ]

    def get_adapter_for_window(self, window: WindowState) -> Optional[BaseApplicationAdapter]:
        """Finds matching specialized adapter for a window, if registered."""
        pname = window.process_name.lower()
        for ad in self.adapters:
            if any(p in pname for p in ad.process_names):
                return ad
        return None

    def execute_application_lifecycle(
        self,
        target_app: str,
        action: str,
        params: Dict[str, Any],
        lease: Optional[OwnershipLease] = None,
    ) -> VerificationResult:
        """
        Executes full DISCOVER -> CONNECT -> OBSERVE -> INTERACT -> VERIFY pipeline.
        """
        require_armed(get_kill_switch())

        # 1. DISCOVER
        state = self.state_builder.capture_state()
        matching_win = None
        for w in state.visible_windows:
            if target_app.lower() in w.title.lower() or target_app.lower() in w.process_name.lower():
                matching_win = w
                break

        # Check adapter
        adapter = self.get_adapter_for_window(matching_win) if matching_win else None

        # 2. CONNECT
        if adapter and matching_win:
            connected = adapter.connect(matching_win, lease=lease)
        elif matching_win:
            connected = self._connect_generic_window(matching_win)
        else:
            # Launch app via Win+R
            self.keyboard.hotkey("win", "r", lease=lease)
            time.sleep(0.3)
            self.keyboard.type_text(target_app, human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(2.0)
            connected = True

        # 3. OBSERVE (Pre-action)
        before_state = self.state_builder.capture_state()

        # 4. INTERACT
        if adapter:
            adapter.interact(action, params, lease=lease)
        else:
            # Fallback to Universal Unknown Application Protocol
            self.interact_unknown_application(action, params, before_state, lease=lease)

        time.sleep(0.2)

        # 5. OBSERVE (Post-action) & VERIFY
        after_state = self.state_builder.capture_state()
        expected = params.get("expected", {"target": target_app})
        return self.verifier.verify_action(action, expected, before_state, after_state)

    def interact_unknown_application(
        self,
        action: str,
        params: Dict[str, Any],
        state: ComputerState,
        lease: Optional[OwnershipLease] = None,
    ) -> bool:
        """
        Universal Unknown Application Protocol (Section 15):
          1. Identify application/window
          2. Inspect accessibility tree
          3. Fall back to visual element detection
          4. Determine plausible interaction points
          5. Perform smallest reasonable probing action
          6. Observe and record structure to Task Memory
        """
        win_title = state.active_window.title if state.active_window else "Unknown App"
        app_name = state.active_window.process_name if state.active_window else "unknown.exe"

        # Determine target element
        target_name = params.get("target_element") or params.get("semantic_target") or ""
        target_elem = state.find_element(target_name) if target_name else None

        if target_elem:
            # Probing click or type
            if action.lower() in {"type", "type_text"}:
                self.keyboard.focus_and_type(
                    element=target_elem,
                    text=params.get("text", ""),
                    human_cadence=True,
                    lease=lease,
                )
            else:
                self.mouse.click_element(target_elem, lease=lease)

            # Record discovered structure to Layer 4 Task Memory
            self.memory.set_project_context(
                project_id="app_discovery",
                key=f"{app_name}:{target_name}",
                value=f"role={target_elem.role},bounds={target_elem.bounds}",
                source="observed",
                confidence=0.88,
            )
            return True

        # Fallback click center
        self.mouse.click(lease=lease)
        return True

    def _connect_generic_window(self, win: WindowState) -> bool:
        try:
            win32gui.SetForegroundWindow(win.hwnd)
            time.sleep(0.2)
            return True
        except Exception:
            return False
