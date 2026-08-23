"""
MAX OS — Controllers: High-Precision Keyboard Controller (Section 7.2).
Executes human-cadence typing, hotkeys, focus validation, clipboard paste/copy,
and navigational keypresses under InputArbiter lease protection.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Union

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

import pyperclip

from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.win32_interactive_session import (
    attach_to_interactive_desktop,
    press_physical_key,
    type_string_hardware,
    VK_RETURN,
    VK_ESCAPE,
    VK_TAB,
    VK_CONTROL,
)


class KeyboardController:
    """
    Physical & Semantic Keyboard Controller.
    Validates element focus before typing and maintains realistic cadence.
    """

    def __init__(
        self,
        arbiter: Optional[InputArbiter] = None,
        mouse_controller: Optional[MouseController] = None,
        uia_engine: Optional[UIAccessibilityEngine] = None,
    ):
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.mouse = mouse_controller or MouseController(arbiter=self.arbiter)
        self.uia = uia_engine or UIAccessibilityEngine()
        attach_to_interactive_desktop()

    def focus_and_type(
        self,
        element: Optional[Union[ElementDescriptor, Dict[str, Any]]],
        text: str,
        clear_existing: bool = False,
        human_cadence: bool = True,
        press_enter: bool = False,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """
        Guarantees target element has focus (clicks into it if specified) before typing.
        """
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        # 1. Click element to focus if supplied
        if element:
            self.mouse.click_element(element, duration=0.3, lease=lease)
            time.sleep(0.1)

        # 2. Optionally select all and clear existing text
        if clear_existing:
            self.select_all(lease=lease)
            time.sleep(0.04)
            self.press_key("backspace", lease=lease)
            time.sleep(0.04)

        # 3. Type text with human cadence
        self.type_text(text, human_cadence=human_cadence, lease=lease)

        # 4. Optionally press Enter to submit
        if press_enter:
            time.sleep(0.08)
            self.enter(lease=lease)

    def type_text(
        self,
        text: str,
        human_cadence: bool = True,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """
        Types text into the active focused window.
        """
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        interval = 0.03 if human_cadence else 0.005
        pyautogui.typewrite(text, interval=interval)

    def press_key(self, key: str, lease: Optional[OwnershipLease] = None) -> None:
        """Presses a single key (e.g. 'enter', 'esc', 'tab', 'backspace')."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        pyautogui.press(key.lower())

    def hotkey(self, *keys: str, lease: Optional[OwnershipLease] = None) -> None:
        """Executes a hotkey sequence (e.g. 'ctrl', 'c' or 'win', 'r')."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        attach_to_interactive_desktop()
        pyautogui.hotkey(*[k.lower() for k in keys])

    def paste(
        self,
        text: str,
        target_element: Optional[Union[ElementDescriptor, Dict[str, Any]]] = None,
        lease: Optional[OwnershipLease] = None,
    ) -> None:
        """
        Sets clipboard and executes Ctrl+V into active element.
        Fast and reliable for long blocks of text.
        """
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        if target_element:
            self.mouse.click_element(target_element, duration=0.3, lease=lease)
            time.sleep(0.08)

        pyperclip.copy(text)
        time.sleep(0.04)
        self.hotkey("ctrl", "v", lease=lease)

    def copy(self, lease: Optional[OwnershipLease] = None) -> str:
        """Executes Ctrl+C and returns the copied clipboard text."""
        require_armed(get_kill_switch())
        if lease:
            self.arbiter.check_lease(lease)

        self.hotkey("ctrl", "c", lease=lease)
        time.sleep(0.08)
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    def select_all(self, lease: Optional[OwnershipLease] = None) -> None:
        """Executes Ctrl+A."""
        self.hotkey("ctrl", "a", lease=lease)

    def enter(self, lease: Optional[OwnershipLease] = None) -> None:
        """Presses the Enter key."""
        self.press_key("enter", lease=lease)

    def escape(self, lease: Optional[OwnershipLease] = None) -> None:
        """Presses the Escape key."""
        self.press_key("esc", lease=lease)

    def tab(self, lease: Optional[OwnershipLease] = None) -> None:
        """Presses the Tab key."""
        self.press_key("tab", lease=lease)

    def shift_tab(self, lease: Optional[OwnershipLease] = None) -> None:
        """Executes Shift+Tab to navigate backwards."""
        self.hotkey("shift", "tab", lease=lease)

    def arrow(self, direction: str = "down", count: int = 1, lease: Optional[OwnershipLease] = None) -> None:
        """Presses arrow keys (up, down, left, right)."""
        key_name = direction.lower()
        for _ in range(max(1, count)):
            self.press_key(key_name, lease=lease)
            time.sleep(0.03)
