"""
MAX OS — Application Adapter: Text & Office Editors (Notepad, Word, TextEdit).
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


class OfficeAdapter(BaseApplicationAdapter):
    def __init__(self, **kwargs):
        super().__init__(
            app_name="Text Editor",
            process_names=["notepad.exe", "winword.exe", "wordpad.exe"],
            **kwargs,
        )

    def discover(self) -> List[WindowState]:
        state = self.state_builder.capture_state()
        return [
            w for w in state.visible_windows
            if any(p in w.process_name.lower() for p in self.process_names)
        ]

    def connect(self, target_window: Optional[WindowState] = None, lease: Optional[OwnershipLease] = None) -> bool:
        instances = self.discover()
        if not instances:
            self.keyboard.hotkey("win", "r", lease=lease)
            time.sleep(0.3)
            self.keyboard.type_text("notepad", human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(1.5)
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
        if act == "type_text":
            text = params.get("text", "")
            self.keyboard.type_text(text, human_cadence=params.get("human_cadence", True), lease=lease)
            return True

        elif act == "save_as":
            filepath = params.get("filepath", "")
            self.keyboard.hotkey("ctrl", "s", lease=lease)
            time.sleep(0.8)
            if filepath:
                self.keyboard.type_text(filepath, human_cadence=False, lease=lease)
                time.sleep(0.2)
                self.keyboard.enter(lease=lease)
                time.sleep(1.0)
            return True

        return False
