"""
MAX OS — Controllers: High-Precision Mouse Controller (Section 7.1).
Resolves semantic element descriptors to physical pixel coordinates and executes
human-like curved trajectories, clicks, double-clicks, right-clicks, dragging, and scrolling
under InputArbiter lease protection.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple, Union

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.accessibility import ElementDescriptor
from core.win32_interactive_session import (
    attach_to_interactive_desktop,
    click_physical_mouse,
    get_physical_cursor_pos,
    set_physical_cursor_pos,
    smooth_glide_cursor,
)


class MouseController:
    """
    Physical & Semantic Mouse Controller.
    Always operates on dynamically resolved element bounding boxes, never static fixed coordinates.
    """

    def __init__(self, arbiter: Optional[InputArbiter] = None):
        self.arbiter = arbiter or InputArbiter.get_instance()
        attach_to_interactive_desktop()

    def get_position(self) -> Tuple[int, int]:
        """Returns current physical cursor coordinates (X, Y)."""
        attach_to_interactive_desktop()
        return get_physical_cursor_pos()

    def move_to_coordinates(
        self,
        x: int,
        y: int,
        duration: float = 0.4,
        lease: Optional[OwnershipLease] = None,
    ) -> Tuple[int, int]:
        """
        Moves the physical mouse cursor smoothly to target coordinates (x, y).
        """
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        smooth_glide_cursor(target_x=x, target_y=y, duration=duration)
        return (x, y)

    def move_to_element(
        self,
        element: Union[ElementDescriptor, Dict[str, Any]],
        duration: float = 0.4,
        lease: Optional[OwnershipLease] = None,
    ) -> Tuple[int, int]:
        """
        Moves the physical mouse to the computed center of a detected UI element.
        """
        center_x, center_y = self._resolve_element_center(element)
        return self.move_to_coordinates(center_x, center_y, duration=duration, lease=lease)

    def click(
        self,
        button: str = "left",
        delay: float = 0.08,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """Sends a physical mouse click at the current cursor position."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        click_physical_mouse(button=button, delay=delay)

    def click_element(
        self,
        element: Union[ElementDescriptor, Dict[str, Any]],
        button: str = "left",
        duration: float = 0.35,
        lease: Optional[OwnershipLease] = None,
    ) -> Tuple[int, int]:
        """
        Moves smoothly to the element center and executes physical click.
        """
        pos = self.move_to_element(element, duration=duration, lease=lease)
        time.sleep(0.04)
        self.click(button=button, lease=lease)
        return pos

    def double_click(
        self,
        element: Optional[Union[ElementDescriptor, Dict[str, Any]]] = None,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """Executes a physical double click."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        if element:
            self.move_to_element(element, duration=0.35, lease=lease)

        attach_to_interactive_desktop()
        click_physical_mouse(button="left", delay=0.05)
        time.sleep(0.06)
        click_physical_mouse(button="left", delay=0.05)

    def right_click(
        self,
        element: Optional[Union[ElementDescriptor, Dict[str, Any]]] = None,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """Executes a physical right click (context menu)."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        if element:
            self.move_to_element(element, duration=0.35, lease=lease)

        attach_to_interactive_desktop()
        click_physical_mouse(button="right", delay=0.08)

    def drag(
        self,
        start: Union[Tuple[int, int], ElementDescriptor],
        end: Union[Tuple[int, int], ElementDescriptor],
        duration: float = 0.6,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """Executes a click-and-drag gesture from start to end."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        start_x, start_y = self._resolve_coords(start)
        end_x, end_y = self._resolve_coords(end)

        self.move_to_coordinates(start_x, start_y, duration=0.3, lease=lease)
        time.sleep(0.05)

        # Mouse Down
        self.mouse_down(button="left", lease=lease)
        time.sleep(0.05)

        # Drag trajectory
        self.move_to_coordinates(end_x, end_y, duration=duration, lease=lease)
        time.sleep(0.05)

        # Mouse Up
        self.mouse_up(button="left", lease=lease)

    def scroll(
        self,
        direction: str = "down",
        amount: int = 5,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """Scrolls the mouse wheel up or down."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        clicks = -amount if direction.lower() == "down" else amount
        pyautogui.scroll(clicks)

    def mouse_down(self, button: str = "left", lease: Optional[OwnershipLease] = None) -> None:
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)
        attach_to_interactive_desktop()
        btn = button.lower()
        if btn == "left":
            pyautogui.mouseDown(button="left")
        elif btn == "right":
            pyautogui.mouseDown(button="right")

    def mouse_up(self, button: str = "left", lease: Optional[OwnershipLease] = None) -> None:
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)
        attach_to_interactive_desktop()
        btn = button.lower()
        if btn == "left":
            pyautogui.mouseUp(button="left")
        elif btn == "right":
            pyautogui.mouseUp(button="right")

    def _resolve_element_center(self, element: Union[ElementDescriptor, Dict[str, Any]]) -> Tuple[int, int]:
        if isinstance(element, ElementDescriptor):
            return element.center
        elif isinstance(element, dict):
            bounds = element.get("bounds", element)
            x = bounds.get("x", 0) + (bounds.get("width", 0) // 2)
            y = bounds.get("y", 0) + (bounds.get("height", 0) // 2)
            return (x, y)
        return (0, 0)

    def _resolve_coords(self, target: Union[Tuple[int, int], ElementDescriptor, Dict[str, Any]]) -> Tuple[int, int]:
        if isinstance(target, (tuple, list)) and len(target) == 2:
            return (int(target[0]), int(target[1]))
        return self._resolve_element_center(target)
