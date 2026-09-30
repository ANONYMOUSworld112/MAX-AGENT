"""
Abstract Desktop Adapter Interface
===================================

Defines safe, strongly-typed desktop automation primitives:
- Pointer actions (click, move, scroll)
- Keyboard actions (type_text, hotkey, press)
- Semantic UI Automation targeting (find_element, click_element)
- Window management (list_windows, get_active_window, focus_window)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class DesktopAdapter(ABC):
    """Abstract interface for desktop automation."""

    @abstractmethod
    def click(self, x: int, y: int, clicks: int = 1, button: str = "left") -> bool:
        """Click at specific screen coordinates."""
        raise NotImplementedError

    @abstractmethod
    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text into active focused element."""
        raise NotImplementedError

    @abstractmethod
    def hotkey(self, *keys: str) -> bool:
        """Press a combination of keys simultaneously."""
        raise NotImplementedError

    @abstractmethod
    def find_element(
        self,
        name: str = "",
        control_type: str = "",
        timeout_seconds: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """Search the UI Automation accessibility tree for a named control."""
        raise NotImplementedError

    @abstractmethod
    def click_element(self, element_or_name: Union[str, Dict[str, Any]]) -> bool:
        """Click an element identified by UIA name or dictionary."""
        raise NotImplementedError

    @abstractmethod
    def list_windows(self) -> List[Dict[str, Any]]:
        """Enumerate top-level desktop windows."""
        raise NotImplementedError

    @abstractmethod
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Return the currently focused foreground window."""
        raise NotImplementedError

    @abstractmethod
    def focus_window(self, title_or_handle: Union[str, int]) -> bool:
        """Bring window to foreground."""
        raise NotImplementedError
