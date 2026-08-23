"""
MAX OS — Application Adapter: Windows File Explorer (`explorer.exe`).
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


class FileExplorerAdapter(BaseApplicationAdapter):
    def __init__(self, **kwargs):
        super().__init__(app_name="File Explorer", process_names=["explorer.exe"], **kwargs)

    def discover(self) -> List[WindowState]:
        state = self.state_builder.capture_state()
        return [
            w for w in state.visible_windows
            if "explorer" in w.process_name.lower() and w.title and w.title != "Program Manager"
        ]

    def connect(self, target_window: Optional[WindowState] = None, lease: Optional[OwnershipLease] = None) -> bool:
        instances = self.discover()
        if not instances:
            self.keyboard.hotkey("win", "e", lease=lease)
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
        if act == "navigate_path":
            path = params.get("path", "C:\\")
            self.keyboard.hotkey("ctrl", "l", lease=lease)
            time.sleep(0.2)
            self.keyboard.type_text(path, human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(1.0)
            return True

        elif act == "search_files":
            query = params.get("query", "")
            self.keyboard.hotkey("ctrl", "e", lease=lease)
            time.sleep(0.3)
            self.keyboard.type_text(query, human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(1.5)
            return True

        return False
