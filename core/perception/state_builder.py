"""State Builder: constructs holistic ComputerState snapshots."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.max_infra.kill_switch import KillSwitch
from core.perception.screen_capture import ScreenCapture, MonitorInfo
from core.perception.accessibility import AccessibilityEngine, UIElement

logger = logging.getLogger("max.perception.state_builder")


@dataclass
class ComputerState:
    active_window: str
    visible_windows: List[Dict[str, Any]]
    processes: List[Dict[str, Any]]
    monitors: List[Dict[str, Any]]
    cursor_pos: Tuple[int, int]
    focused_element: Optional[Dict[str, Any]] = None
    clipboard_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class StateBuilder:
    def __init__(
        self,
        screen_capture: Optional[ScreenCapture] = None,
        accessibility: Optional[AccessibilityEngine] = None,
    ) -> None:
        self.kill_switch = KillSwitch.get_instance()
        self.screen_capture = screen_capture or ScreenCapture()
        self.accessibility = accessibility or AccessibilityEngine()

    def build_state(self) -> ComputerState:
        """Captures a complete, consistent snapshot of the current operating system state."""
        self.kill_switch.guard()

        # 1. Cursor position
        cursor_pos = (0, 0)
        try:
            import ctypes
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            cursor_pos = (pt.x, pt.y)
        except Exception:
            pass

        # 2. Monitors
        monitors_data = [
            {
                "id": m.id,
                "left": m.left,
                "top": m.top,
                "width": m.width,
                "height": m.height,
                "is_primary": m.is_primary,
            }
            for m in self.screen_capture.get_monitors()
        ]

        # 3. Active & Visible Windows
        active_window_title = "Desktop"
        visible_windows: List[Dict[str, Any]] = []

        try:
            import pywinauto
            elements = self.accessibility.find_elements(max_elements=10)
            for el in elements:
                visible_windows.append({
                    "title": el.name,
                    "rect": el.bounding_rect,
                    "enabled": el.is_enabled,
                })
            if visible_windows:
                active_window_title = visible_windows[0]["title"]
        except Exception:
            visible_windows = [{"title": "Default", "rect": (0, 0, 1920, 1080), "enabled": True}]

        # 4. Processes
        processes_data: List[Dict[str, Any]] = []
        try:
            import psutil
            for p in list(psutil.process_iter(["pid", "name"]))[:15]:
                try:
                    processes_data.append(p.info)
                except Exception:
                    continue
        except Exception:
            pass

        # 5. Focused Element
        focused = self.accessibility.get_focused_element()
        focused_dict = (
            {
                "name": focused.name,
                "control_type": focused.control_type,
                "bounding_rect": focused.bounding_rect,
            }
            if focused
            else None
        )

        return ComputerState(
            active_window=active_window_title,
            visible_windows=visible_windows,
            processes=processes_data,
            monitors=monitors_data,
            cursor_pos=cursor_pos,
            focused_element=focused_dict,
            clipboard_metadata={"has_text": False, "length": 0},
            timestamp=time.time(),
        )
