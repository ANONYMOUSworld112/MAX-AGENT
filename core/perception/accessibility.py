"""Accessibility and IUIAutomation inspection engine (Levels 1 & 2)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from core.max_infra.kill_switch import KillSwitch

logger = logging.getLogger("max.perception.accessibility")


@dataclass
class UIElement:
    name: str
    control_type: str
    bounding_rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_enabled: bool = True
    is_focused: bool = False
    automation_id: str = ""
    class_name: str = ""
    handle: int = 0

    @property
    def center_point(self) -> Tuple[int, int]:
        l, t, r, b = self.bounding_rect
        return ((l + r) // 2, (t + b) // 2)


class AccessibilityEngine:
    def __init__(self) -> None:
        self.kill_switch = KillSwitch.get_instance()

    def get_focused_element(self) -> Optional[UIElement]:
        """Returns the currently focused UI element via accessibility."""
        self.kill_switch.guard()
        try:
            import pywinauto
            from pywinauto.findwindows import find_window
            focused_handle = pywinauto.win32functions.GetFocus()
            if focused_handle:
                rect = pywinauto.win32functions.GetWindowRect(focused_handle)
                text = pywinauto.win32functions.GetWindowText(focused_handle)
                return UIElement(
                    name=text or "FocusedWindow",
                    control_type="Window",
                    bounding_rect=(rect.left, rect.top, rect.right, rect.bottom),
                    is_enabled=True,
                    is_focused=True,
                    handle=focused_handle,
                )
        except Exception as exc:
            logger.debug("Accessibility focus detection fallback: %s", exc)

        return None

    def find_elements(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        max_elements: int = 50,
    ) -> List[UIElement]:
        """Scans for active UI elements matching query criteria."""
        self.kill_switch.guard()
        results: List[UIElement] = []

        try:
            import pywinauto
            desktop = pywinauto.Desktop(backend="uia")
            windows = desktop.windows()[:15]
            for win in windows:
                try:
                    w_name = win.window_text()
                    rect = win.rectangle()
                    b_rect = (rect.left, rect.top, rect.right, rect.bottom)
                    if name and name.lower() not in w_name.lower():
                        continue
                    results.append(UIElement(
                        name=w_name or "UntitledWindow",
                        control_type="Window",
                        bounding_rect=b_rect,
                        is_enabled=win.is_enabled(),
                        class_name=win.class_name(),
                        handle=win.handle,
                    ))
                    if len(results) >= max_elements:
                        break
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("pywinauto uia scan fallback: %s", exc)

        return results
