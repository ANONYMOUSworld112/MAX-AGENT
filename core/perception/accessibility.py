"""
MAX OS — Perception Engine: Windows UI Automation & Accessibility Tree (Priority 1).
Native COM bridge to IUIAutomation for structured UI tree reading, exact element bounding boxes,
roles, states, and semantic element resolution.
"""

from __future__ import annotations

import ctypes
import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import comtypes
    import comtypes.client
except Exception:
    comtypes = None

import psutil

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None

from core.win32_interactive_session import attach_to_interactive_desktop

# Mapping UIA ControlType IDs to friendly role names
UIA_CONTROL_TYPE_MAP: Dict[int, str] = {
    50000: "button",
    50001: "calendar",
    50002: "checkbox",
    50003: "combobox",
    50004: "edit",
    50005: "link",
    50006: "image",
    50007: "list_item",
    50008: "list",
    50009: "menu",
    50010: "menu_bar",
    50011: "menu_item",
    50012: "progress_bar",
    50013: "radio_button",
    50014: "scroll_bar",
    50015: "slider",
    50016: "spinner",
    50017: "status_bar",
    50018: "tab",
    50019: "tab_item",
    50020: "text",
    50021: "toolbar",
    50022: "tooltip",
    50023: "tree",
    50024: "tree_item",
    50025: "custom",
    50026: "group",
    50028: "data_item",
    50029: "document",
    50030: "split_button",
    50031: "window",
    50032: "pane",
    50033: "header",
    50034: "header_item",
    50035: "table",
    50036: "title_bar",
    50037: "separator",
    50038: "semantic_zoom",
    50039: "app_bar",
}


@dataclass
class ElementDescriptor:
    id: str
    type: str  # button, edit, text, link, window, pane, etc.
    text: str
    role: str
    bounds: Dict[str, int]  # {"x": int, "y": int, "width": int, "height": int}
    confidence: float = 1.0
    enabled: bool = True
    focused: bool = False
    interactable: bool = True
    source: str = "accessibility_tree"
    accessibility_id: str = ""
    application: str = ""
    window: str = ""
    parent_id: Optional[str] = None
    children_count: int = 0
    raw_control_type: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def center(self) -> Tuple[int, int]:
        x = self.bounds.get("x", 0) + (self.bounds.get("width", 0) // 2)
        y = self.bounds.get("y", 0) + (self.bounds.get("height", 0) // 2)
        return (x, y)


class UIAccessibilityEngine:
    """
    Native Windows UI Automation accessibility reader.
    Interfaces directly with UIAutomationCore.dll COM server to produce
    ground-truth structural element descriptions and exact pixel bounding boxes.
    """

    def __init__(self):
        self._uia = None
        self._init_uia()

    def _init_uia(self) -> None:
        try:
            attach_to_interactive_desktop()
            try:
                comtypes.CoInitialize()
            except Exception:
                pass
            UIAutomationClient = comtypes.client.GetModule("UIAutomationCore.dll")
            self._uia = comtypes.client.CreateObject(
                "{ff48dba4-60ef-4201-aa87-54103eef594e}",
                interface=UIAutomationClient.IUIAutomation,
            )
        except Exception:
            try:
                self._uia = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}")
            except Exception:
                self._uia = None

    @property
    def is_available(self) -> bool:
        return self._uia is not None

    def get_focused_element(self) -> Optional[ElementDescriptor]:
        """Retrieves the currently keyboard-focused UI element."""
        if not self._uia:
            return None
        try:
            elem = self._uia.GetFocusedElement()
            if elem:
                return self._parse_uia_element(elem, window_title="Focused", app_name="")
        except Exception:
            pass
        return None

    def get_root_element(self):
        """Retrieves desktop root UIA element."""
        if not self._uia:
            return None
        try:
            return self._uia.GetRootElement()
        except Exception:
            return None

    def get_element_from_hwnd(self, hwnd: int):
        """Retrieves UIA element directly from a Win32 window handle."""
        if not self._uia or not hwnd:
            return None
        try:
            return self._uia.ElementFromHandle(hwnd)
        except Exception:
            return None

    def get_elements_for_window(
        self, hwnd: int, max_depth: int = 4, max_elements: int = 150
    ) -> List[ElementDescriptor]:
        """
        Traverses and extracts all interactable and semantic elements within a target window.
        """
        if not self._uia or not win32gui.IsWindow(hwnd):
            return []

        title = win32gui.GetWindowText(hwnd)
        app_name = self._get_process_name_for_hwnd(hwnd)

        try:
            root_elem = self._uia.ElementFromHandle(hwnd)
            if not root_elem:
                return []

            walker = self._uia.ControlViewWalker
            if not walker:
                return []

            elements: List[ElementDescriptor] = []
            visited_ids: Set[str] = set()

            self._traverse_tree(
                elem=root_elem,
                walker=walker,
                window_title=title,
                app_name=app_name,
                depth=0,
                max_depth=max_depth,
                max_elements=max_elements,
                output_list=elements,
                visited_ids=visited_ids,
            )
            return elements
        except Exception:
            return []

    def get_active_window_elements(
        self, max_depth: int = 4, max_elements: int = 150
    ) -> Tuple[Optional[str], List[ElementDescriptor]]:
        """
        Extracts all structured UI elements from the currently active foreground window.
        """
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, []

        title = win32gui.GetWindowText(hwnd)
        elems = self.get_elements_for_window(hwnd, max_depth=max_depth, max_elements=max_elements)
        return title, elems

    def find_elements_by_query(
        self,
        elements: List[ElementDescriptor],
        query: str,
        role: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[ElementDescriptor]:
        """
        Filters and ranks detected elements matching a semantic natural-language query.
        """
        q_lower = query.lower().strip()
        matches: List[Tuple[float, ElementDescriptor]] = []

        for elem in elements:
            elem_text = elem.text.lower().strip()
            elem_id = elem.accessibility_id.lower().strip()
            elem_role = elem.role.lower().strip()

            if role and elem_role != role.lower():
                continue

            score = 0.0

            # 1. Exact match on text or accessibility ID
            if q_lower == elem_text or q_lower == elem_id:
                score = 1.0
            # 2. Substring match
            elif q_lower in elem_text or q_lower in elem_id:
                score = 0.85
            # 3. Partial word overlap
            else:
                q_words = set(q_lower.split())
                text_words = set(elem_text.split() + elem_id.split())
                overlap = q_words.intersection(text_words)
                if overlap:
                    score = 0.5 + (0.3 * (len(overlap) / max(1, len(q_words))))

            # Role bonus if matches target role
            if role and elem_role == role.lower():
                score = min(1.0, score + 0.1)

            # Interactability multiplier
            final_conf = score * (elem.confidence if elem.interactable else elem.confidence * 0.7)

            if final_conf >= min_confidence:
                matches.append((final_conf, elem))

        # Sort by confidence score descending
        matches.sort(key=lambda item: item[0], reverse=True)
        return [elem for _, elem in matches]

    def _traverse_tree(
        self,
        elem,
        walker,
        window_title: str,
        app_name: str,
        depth: int,
        max_depth: int,
        max_elements: int,
        output_list: List[ElementDescriptor],
        visited_ids: Set[str],
        parent_id: Optional[str] = None,
    ) -> None:
        if len(output_list) >= max_elements or depth > max_depth:
            return

        desc = self._parse_uia_element(elem, window_title=window_title, app_name=app_name, parent_id=parent_id)
        if desc and desc.id not in visited_ids:
            # Include elements with meaningful bounds and interactable/semantic roles
            if desc.bounds["width"] > 0 and desc.bounds["height"] > 0:
                visited_ids.add(desc.id)
                output_list.append(desc)
                current_id = desc.id
            else:
                current_id = parent_id
        else:
            current_id = parent_id

        # Walk children
        try:
            child = walker.GetFirstChildElement(elem)
            while child and len(output_list) < max_elements:
                self._traverse_tree(
                    elem=child,
                    walker=walker,
                    window_title=window_title,
                    app_name=app_name,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_elements=max_elements,
                    output_list=output_list,
                    visited_ids=visited_ids,
                    parent_id=current_id,
                )
                child = walker.GetNextSiblingElement(child)
        except Exception:
            pass

    def _parse_uia_element(
        self, elem, window_title: str, app_name: str, parent_id: Optional[str] = None
    ) -> Optional[ElementDescriptor]:
        try:
            raw_type = elem.CurrentControlType
            role = UIA_CONTROL_TYPE_MAP.get(raw_type, "custom")
            name = elem.CurrentName or ""
            auto_id = elem.CurrentAutomationId or ""
            is_enabled = bool(elem.CurrentIsEnabled)
            is_focused = bool(elem.CurrentHasKeyboardFocus)
            is_focusable = bool(elem.CurrentIsKeyboardFocusable)

            # Bounding rectangle: (left, top, width, height)
            rect = elem.CurrentBoundingRectangle
            left = int(rect[0]) if isinstance(rect, (list, tuple)) else int(getattr(rect, "left", 0))
            top = int(rect[1]) if isinstance(rect, (list, tuple)) else int(getattr(rect, "top", 0))
            width = int(rect[2]) if isinstance(rect, (list, tuple)) else int(getattr(rect, "right", 0) - left)
            height = int(rect[3]) if isinstance(rect, (list, tuple)) else int(getattr(rect, "bottom", 0) - top)

            bounds = {"x": left, "y": top, "width": width, "height": height}

            # Generate stable deterministic element ID
            id_seed = f"{app_name}:{window_title}:{role}:{auto_id}:{name}:{left},{top},{width},{height}"
            elem_id = f"elem_{hashlib.md5(id_seed.encode('utf-8')).hexdigest()[:8]}"

            # Determine interactability
            interactable = is_enabled and (
                role in {"button", "edit", "link", "checkbox", "radio_button", "combobox", "tab_item", "menu_item", "list_item", "split_button", "slider"}
                or is_focusable
            )

            return ElementDescriptor(
                id=elem_id,
                type=role,
                text=name,
                role=role,
                bounds=bounds,
                confidence=0.98 if is_enabled else 0.85,
                enabled=is_enabled,
                focused=is_focused,
                interactable=interactable,
                source="accessibility_tree",
                accessibility_id=auto_id,
                application=app_name,
                window=window_title,
                parent_id=parent_id,
                raw_control_type=raw_type,
            )
        except Exception:
            return None

    def _get_process_name_for_hwnd(self, hwnd: int) -> str:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return proc.name()
        except Exception:
            return ""
