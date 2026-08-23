"""
MAX OS — Perception Engine: Browser Accessibility & DOM Snapshot (Priority 2).
Extracts structured in-browser state, active tabs, address bar URLs, and web page elements
from running Chromium/Gecko browsers (Edge, Chrome, Brave, Firefox) via UI Automation document trees.
"""

from __future__ import annotations

import ctypes
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None

import psutil

from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.win32_interactive_session import attach_to_interactive_desktop

SUPPORTED_BROWSER_PROCESSES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "brave.exe": "Brave Browser",
    "firefox.exe": "Mozilla Firefox",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
}


@dataclass
class BrowserTabInfo:
    title: str
    is_active: bool
    bounds: Dict[str, int]
    tab_index: int = 0


@dataclass
class BrowserSnapshot:
    application: str
    hwnd: int
    window_title: str
    active_tab: Optional[BrowserTabInfo]
    tabs: List[BrowserTabInfo]
    url: str
    title: str
    dom_available: bool
    detected_elements: List[ElementDescriptor] = field(default_factory=list)
    timestamp: float = 0.0


class BrowserAccessibilityEngine:
    """
    In-browser DOM and accessibility tree reader.
    Extracts high-fidelity structured web elements, URLs, tabs, and interactive controls
    directly from active browser windows.
    """

    def __init__(self, uia_engine: Optional[UIAccessibilityEngine] = None):
        self.uia = uia_engine or UIAccessibilityEngine()

    def find_active_browser_windows(self) -> List[Tuple[int, str, str]]:
        """
        Returns list of (hwnd, process_name, window_title) for all open browser windows.
        """
        attach_to_interactive_desktop()
        browser_windows: List[Tuple[int, str, str]] = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _enum_cb(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if title:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            proc = psutil.Process(pid)
                            pname = proc.name().lower()
                            if pname in SUPPORTED_BROWSER_PROCESSES:
                                browser_windows.append((hwnd, pname, title))
                        except Exception:
                            pass
            return True

        try:
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        except Exception:
            pass

        return browser_windows

    def capture_browser_state(self, hwnd: Optional[int] = None) -> Optional[BrowserSnapshot]:
        """
        Captures full in-browser snapshot (active URL, tab strip, document tree elements).
        If hwnd is not specified, finds the foremost active browser window.
        """
        target_hwnd = hwnd
        app_name = ""
        win_title = ""

        if not target_hwnd:
            browsers = self.find_active_browser_windows()
            if not browsers:
                return None
            fg_hwnd = win32gui.GetForegroundWindow()
            match = next((b for b in browsers if b[0] == fg_hwnd), None)
            if match:
                target_hwnd, app_name, win_title = match
            else:
                target_hwnd, app_name, win_title = browsers[0]
        else:
            if not win32gui.IsWindow(target_hwnd):
                return None
            win_title = win32gui.GetWindowText(target_hwnd)
            try:
                _, pid = win32process.GetWindowThreadProcessId(target_hwnd)
                app_name = psutil.Process(pid).name().lower()
            except Exception:
                app_name = "browser.exe"

        # Extract UIA tree for browser window
        all_elements = self.uia.get_elements_for_window(target_hwnd, max_depth=6, max_elements=200)

        # 1. Extract Address Bar URL
        extracted_url = self._extract_url_from_elements(all_elements)

        # 2. Extract Tabs
        tabs, active_tab = self._extract_tabs(all_elements, win_title)

        # 3. Extract Document Web Elements (links, buttons, inputs inside document pane)
        web_elements = self._filter_web_elements(all_elements, app_name, win_title)
        dom_available = len(web_elements) > 0 or bool(extracted_url)

        return BrowserSnapshot(
            application=app_name,
            hwnd=target_hwnd,
            window_title=win_title,
            active_tab=active_tab,
            tabs=tabs,
            url=extracted_url,
            title=active_tab.title if active_tab else win_title,
            dom_available=dom_available,
            detected_elements=web_elements,
        )

    def _extract_url_from_elements(self, elements: List[ElementDescriptor]) -> str:
        """Finds address bar / omnibox and extracts valid URL."""
        for elem in elements:
            is_address_candidate = (
                elem.type in {"edit", "text", "custom"}
                and any(
                    k in elem.accessibility_id.lower()
                    for k in ("address", "url", "omnibox", "search", "location")
                )
            ) or (
                elem.type == "edit"
                and (
                    elem.text.startswith("http://")
                    or elem.text.startswith("https://")
                    or elem.text.startswith("www.")
                    or ".com" in elem.text
                    or ".org" in elem.text
                    or ".net" in elem.text
                    or ".io" in elem.text
                    or "/" in elem.text
                )
            )

            if is_address_candidate and elem.text:
                clean_text = elem.text.strip()
                if not clean_text.startswith("http://") and not clean_text.startswith("https://") and "." in clean_text:
                    clean_text = "https://" + clean_text
                return clean_text

        return ""

    def _extract_tabs(
        self, elements: List[ElementDescriptor], window_title: str
    ) -> Tuple[List[BrowserTabInfo], Optional[BrowserTabInfo]]:
        tabs: List[BrowserTabInfo] = []
        active_tab: Optional[BrowserTabInfo] = None

        for idx, elem in enumerate(elements):
            if elem.type in {"tab_item", "tab"}:
                tab_title = elem.text or f"Tab {idx + 1}"
                is_active = elem.focused or (tab_title in window_title)
                t_info = BrowserTabInfo(
                    title=tab_title,
                    is_active=is_active,
                    bounds=elem.bounds,
                    tab_index=idx,
                )
                tabs.append(t_info)
                if is_active and not active_tab:
                    active_tab = t_info

        if not active_tab and tabs:
            active_tab = tabs[0]

        return tabs, active_tab

    def _filter_web_elements(
        self, elements: List[ElementDescriptor], app_name: str, window_title: str
    ) -> List[ElementDescriptor]:
        """Filters down to interactive web page content elements and tags them as browser_dom source."""
        web_elems: List[ElementDescriptor] = []
        for elem in elements:
            if elem.interactable or elem.type in {"button", "link", "edit", "document", "checkbox", "radio_button", "combobox"}:
                elem.source = "browser_dom"
                elem.confidence = 0.96
                elem.application = app_name
                elem.window = window_title
                web_elems.append(elem)
        return web_elems
