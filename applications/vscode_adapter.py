"""
MAX OS — Application Adapter: Visual Studio Code (`code.exe`).
Provides optimized interaction for VS Code: Command Palette, Explorer, File Opening, Terminal pane.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import win32gui
except Exception:
    win32gui = None

from applications.base_adapter import BaseApplicationAdapter
from core.input_arbiter import OwnershipLease
from core.perception.accessibility import ElementDescriptor
from core.perception.state_builder import ComputerState, WindowState


class VSCodeAdapter(BaseApplicationAdapter):
    """
    Specialized adapter for Microsoft Visual Studio Code.
    """

    def __init__(self, **kwargs):
        super().__init__(app_name="Visual Studio Code", process_names=["code.exe"], **kwargs)

    def discover(self) -> List[WindowState]:
        state = self.state_builder.capture_state()
        return [
            w for w in state.visible_windows
            if any(p in w.process_name.lower() for p in self.process_names) or "visual studio code" in w.title.lower()
        ]

    def connect(self, target_window: Optional[WindowState] = None, lease: Optional[OwnershipLease] = None) -> bool:
        instances = self.discover()
        if not instances:
            # Launch VS Code
            self.keyboard.hotkey("win", "r", lease=lease)
            time.sleep(0.3)
            self.keyboard.type_text("code", human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(2.5)
            instances = self.discover()

        if instances:
            target = target_window or instances[0]
            try:
                win32gui.SetForegroundWindow(target.hwnd)
                time.sleep(0.2)
                return True
            except Exception:
                pass
        return False

    def observe(self) -> Tuple[ComputerState, List[ElementDescriptor]]:
        state = self.state_builder.capture_state()
        return state, state.detected_elements

    def interact(self, action: str, params: Dict[str, Any], lease: Optional[OwnershipLease] = None) -> bool:
        act = action.lower()
        if act == "open_command_palette":
            self.keyboard.hotkey("ctrl", "shift", "p", lease=lease)
            time.sleep(0.3)
            cmd = params.get("command", "")
            if cmd:
                self.keyboard.type_text(cmd, human_cadence=False, lease=lease)
                time.sleep(0.1)
                if params.get("press_enter", True):
                    self.keyboard.enter(lease=lease)
            return True

        elif act == "quick_open_file":
            self.keyboard.hotkey("ctrl", "p", lease=lease)
            time.sleep(0.3)
            filename = params.get("filename", "")
            if filename:
                self.keyboard.type_text(filename, human_cadence=False, lease=lease)
                time.sleep(0.1)
                self.keyboard.enter(lease=lease)
            return True

        elif act == "toggle_terminal":
            self.keyboard.hotkey("ctrl", "`", lease=lease)
            time.sleep(0.4)
            return True

        elif act == "save_file":
            self.keyboard.hotkey("ctrl", "s", lease=lease)
            time.sleep(0.2)
            return True

        return False
