"""
MAX-AGENT Platform Adapters Layer
==================================

Allowlisted boundary for OS-specific primitives and platform APIs.
Provides abstract interfaces and test doubles (fake adapters) for CI/headless testing.
"""

from __future__ import annotations

import os
import platform
from typing import Optional

from core.adapters.base import DesktopAdapter
from core.adapters.fake_desktop import FakeDesktopAdapter


_DESKTOP_ADAPTER: Optional[DesktopAdapter] = None


def get_desktop_adapter() -> DesktopAdapter:
    """Retrieve or create the singleton desktop adapter for the current environment."""
    global _DESKTOP_ADAPTER
    if _DESKTOP_ADAPTER is None:
        if os.environ.get("MAX_USE_FAKE_ADAPTERS") == "1" or platform.system() != "Windows":
            _DESKTOP_ADAPTER = FakeDesktopAdapter()
        else:
            try:
                from core.adapters.windows_desktop import WindowsDesktopAdapter
                _DESKTOP_ADAPTER = WindowsDesktopAdapter()
            except Exception:
                _DESKTOP_ADAPTER = FakeDesktopAdapter()
    return _DESKTOP_ADAPTER


def set_desktop_adapter(adapter: DesktopAdapter) -> None:
    """Override the active desktop adapter (for testing)."""
    global _DESKTOP_ADAPTER
    _DESKTOP_ADAPTER = adapter
