"""
Fake Desktop Adapter for Headless / CI Testing
==============================================

Records all interactions in-memory and supports mock window/element fixtures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from core.adapters.base import DesktopAdapter


class FakeDesktopAdapter(DesktopAdapter):
    """In-memory test double for desktop automation."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple, Dict[str, Any]]] = []
        self.mock_windows: List[Dict[str, Any]] = []
        self.mock_elements: List[Dict[str, Any]] = []
        self.active_window: Optional[Dict[str, Any]] = None

    def add_mock_window(
        self,
        title: str,
        process_name: str = "app.exe",
        pid: int = 1234,
        handle: int = 1001,
        class_name: str = "WindowClass",
    ) -> Dict[str, Any]:
        win = {
            "title": title,
            "process_name": process_name,
            "pid": pid,
            "handle": handle,
            "class_name": class_name,
            "is_visible": True,
        }
        self.mock_windows.append(win)
        if self.active_window is None:
            self.active_window = win
        return win

    def add_mock_element(
        self,
        name: str,
        control_type: str = "Button",
        bounding_box: Optional[Tuple[int, int, int, int]] = (100, 100, 200, 150),
    ) -> Dict[str, Any]:
        elem = {
            "name": name,
            "control_type": control_type,
            "bounding_box": bounding_box,
            "is_enabled": True,
            "is_visible": True,
        }
        self.mock_elements.append(elem)
        return elem

    def click(self, x: int, y: int, clicks: int = 1, button: str = "left") -> bool:
        self.calls.append(("click", (x, y), {"clicks": clicks, "button": button}))
        return True

    def type_text(self, text: str, interval: float = 0.0) -> bool:
        self.calls.append(("type_text", (text,), {"interval": interval}))
        return True

    def hotkey(self, *keys: str) -> bool:
        self.calls.append(("hotkey", keys, {}))
        return True

    def find_element(
        self,
        name: str = "",
        control_type: str = "",
        timeout_seconds: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        self.calls.append(("find_element", (), {"name": name, "control_type": control_type}))
        norm_name = name.lower().strip()
        norm_type = control_type.lower().strip()

        for elem in self.mock_elements:
            elem_name = elem.get("name", "").lower().strip()
            elem_type = elem.get("control_type", "").lower().strip()

            if norm_name and norm_name not in elem_name:
                continue
            if norm_type and norm_type != elem_type:
                continue
            return elem
        return None

    def click_element(self, element_or_name: Union[str, Dict[str, Any]]) -> bool:
        if isinstance(element_or_name, str):
            elem = self.find_element(name=element_or_name)
        else:
            elem = element_or_name

        if not elem:
            return False

        bb = elem.get("bounding_box", (0, 0, 10, 10))
        center_x = (bb[0] + bb[2]) // 2
        center_y = (bb[1] + bb[3]) // 2
        self.click(center_x, center_y)
        self.calls.append(("click_element", (elem.get("name"),), {}))
        return True

    def list_windows(self) -> List[Dict[str, Any]]:
        self.calls.append(("list_windows", (), {}))
        return list(self.mock_windows)

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        self.calls.append(("get_active_window", (), {}))
        return self.active_window

    def focus_window(self, title_or_handle: Union[str, int]) -> bool:
        self.calls.append(("focus_window", (title_or_handle,), {}))
        for win in self.mock_windows:
            if isinstance(title_or_handle, int) and win.get("handle") == title_or_handle:
                self.active_window = win
                return True
            if isinstance(title_or_handle, str) and title_or_handle.lower() in win.get("title", "").lower():
                self.active_window = win
                return True
        return False
