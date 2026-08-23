"""
MAX OS — Application Adapter: Web Browsers (Chrome, Brave, Edge).
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
from core.perception.browser_dom import BrowserAccessibilityEngine
from core.perception.state_builder import ComputerState, WindowState


class BrowserAdapter(BaseApplicationAdapter):
    def __init__(self, **kwargs):
        super().__init__(
            app_name="Web Browser",
            process_names=["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"],
            **kwargs,
        )
        self.browser_engine = BrowserAccessibilityEngine()

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
            self.keyboard.type_text("brave", human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(2.0)
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
        snap = self.browser_engine.capture_browser_state()
        elements = snap.detected_elements if snap else state.detected_elements
        return state, elements

    def interact(self, action: str, params: Dict[str, Any], lease: Optional[OwnershipLease] = None) -> bool:
        act = action.lower()
        if act == "navigate":
            url = params.get("url", "https://google.com")
            self.keyboard.hotkey("ctrl", "l", lease=lease)
            time.sleep(0.2)
            self.keyboard.type_text(url, human_cadence=False, lease=lease)
            time.sleep(0.1)
            self.keyboard.enter(lease=lease)
            time.sleep(2.0)
            return True

        elif act == "new_tab":
            self.keyboard.hotkey("ctrl", "t", lease=lease)
            time.sleep(0.3)
            return True

        elif act == "close_tab":
            self.keyboard.hotkey("ctrl", "w", lease=lease)
            time.sleep(0.3)
            return True

        elif act == "scroll":
            self.mouse.scroll(direction=params.get("direction", "down"), amount=params.get("amount", 5), lease=lease)
            return True

        return False
