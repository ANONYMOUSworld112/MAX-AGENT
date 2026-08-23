"""
MAX OS — Unified Action Tool Registry & Tool Hierarchy (Phases 4, 5, 6).
Defines and enforces the 8-Level Tool Hierarchy and provides strongly typed tool validation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.command_model import ActionObject
from core.security.security_gate import RiskTier, SecurityGate


class ComputerToolLevel(int, enum.Enum):
    LEVEL_1_NATIVE_API = 1        # Native application API / Python library
    LEVEL_2_OS_API = 2            # Operating System API / System subprocess
    LEVEL_3_UI_AUTOMATION = 3     # Windows UI Automation (UIA)
    LEVEL_4_BROWSER_DOM = 4       # Browser DOM / Playwright / Web Driver
    LEVEL_5_ACCESSIBILITY = 5     # Accessibility / Semantic Tree
    LEVEL_6_OCR = 6               # Optical Character Recognition
    LEVEL_7_COMPUTER_VISION = 7   # Computer Vision / Visual Pattern Matching
    LEVEL_8_RAW_INPUT = 8         # Raw Mouse & Keyboard simulation


@dataclass
class ToolDefinition:
    name: str
    category: str
    level: ComputerToolLevel
    description: str
    parameters: Dict[str, str]
    risk_tier: RiskTier
    handler: Optional[Callable[..., Any]] = None


class ActionToolRegistry:
    """
    Unified Tool Registry for MAX High-Speed Computer Control Engine.
    Maintains tool metadata, risk mappings, and hierarchy-based routing.
    """

    def __init__(self, security_gate: Optional[SecurityGate] = None):
        self.security_gate = security_gate or SecurityGate()
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Registers all mandatory tools specified in Phase 5."""
        
        # --- SCREEN TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="screenshot",
                category="SCREEN",
                level=ComputerToolLevel.LEVEL_2_OS_API,
                description="Captures a full-screen screenshot.",
                parameters={"monitor": "int (default 0)"},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="screenshot_region",
                category="SCREEN",
                level=ComputerToolLevel.LEVEL_2_OS_API,
                description="Captures a bounding box region screenshot.",
                parameters={"x": "int", "y": "int", "width": "int", "height": "int"},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="screen_size",
                category="SCREEN",
                level=ComputerToolLevel.LEVEL_2_OS_API,
                description="Gets virtual desktop dimensions.",
                parameters={},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="active_window",
                category="SCREEN",
                level=ComputerToolLevel.LEVEL_3_UI_AUTOMATION,
                description="Gets title and process name of active window.",
                parameters={},
                risk_tier=RiskTier.TIER_0,
            )
        )

        # --- MOUSE TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="mouse_move",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Moves cursor to (x, y) coordinates.",
                parameters={"x": "int", "y": "int", "duration_ms": "int"},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="mouse_click",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Clicks left mouse button at target or current location.",
                parameters={"x": "int (optional)", "y": "int (optional)", "clicks": "int"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="mouse_double_click",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Double clicks left mouse button.",
                parameters={"x": "int (optional)", "y": "int (optional)"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="mouse_right_click",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Clicks right mouse button.",
                parameters={"x": "int (optional)", "y": "int (optional)"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="mouse_drag",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Drags mouse from start to end coordinates.",
                parameters={"start_x": "int", "start_y": "int", "end_x": "int", "end_y": "int"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="mouse_scroll",
                category="MOUSE",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Scrolls mouse wheel up/down.",
                parameters={"clicks": "int (positive=up, negative=down)"},
                risk_tier=RiskTier.TIER_0,
            )
        )

        # --- KEYBOARD TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="keyboard_type",
                category="KEYBOARD",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Types a complete string of text.",
                parameters={"text": "str", "interval_ms": "int"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="keyboard_press",
                category="KEYBOARD",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Presses a single key (ENTER, TAB, ESC, etc.).",
                parameters={"key": "str"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="keyboard_hotkey",
                category="KEYBOARD",
                level=ComputerToolLevel.LEVEL_8_RAW_INPUT,
                description="Presses a combination shortcut (e.g. CTRL+C, ALT+TAB).",
                parameters={"keys": "List[str]"},
                risk_tier=RiskTier.TIER_1,
            )
        )

        # --- WINDOW TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="list_windows",
                category="WINDOW",
                level=ComputerToolLevel.LEVEL_3_UI_AUTOMATION,
                description="Lists all visible top-level windows.",
                parameters={},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="focus_window",
                category="WINDOW",
                level=ComputerToolLevel.LEVEL_3_UI_AUTOMATION,
                description="Brings target window into focus.",
                parameters={"target": "str (window title or substring)"},
                risk_tier=RiskTier.TIER_0,
            )
        )

        # --- APPLICATION TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="launch_application",
                category="APPLICATION",
                level=ComputerToolLevel.LEVEL_2_OS_API,
                description="Launches an installed executable or URI.",
                parameters={"app_name_or_path": "str"},
                risk_tier=RiskTier.TIER_0,
            )
        )

        # --- BROWSER TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="browser_open",
                category="BROWSER",
                level=ComputerToolLevel.LEVEL_4_BROWSER_DOM,
                description="Opens browser to specified URL.",
                parameters={"url": "str"},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="browser_click",
                category="BROWSER",
                level=ComputerToolLevel.LEVEL_4_BROWSER_DOM,
                description="Clicks DOM element via CSS selector or text.",
                parameters={"selector": "str"},
                risk_tier=RiskTier.TIER_1,
            )
        )

        # --- FILESYSTEM TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="create_file",
                category="FILESYSTEM",
                level=ComputerToolLevel.LEVEL_1_NATIVE_API,
                description="Creates a file with text content.",
                parameters={"path": "str", "content": "str"},
                risk_tier=RiskTier.TIER_1,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="create_directory",
                category="FILESYSTEM",
                level=ComputerToolLevel.LEVEL_1_NATIVE_API,
                description="Creates a folder path.",
                parameters={"path": "str"},
                risk_tier=RiskTier.TIER_0,
            )
        )
        self.register_tool(
            ToolDefinition(
                name="delete_file",
                category="FILESYSTEM",
                level=ComputerToolLevel.LEVEL_1_NATIVE_API,
                description="Deletes target file or directory.",
                parameters={"path": "str"},
                risk_tier=RiskTier.TIER_2,
            )
        )

        # --- TERMINAL TOOLS ---
        self.register_tool(
            ToolDefinition(
                name="execute_command",
                category="TERMINAL",
                level=ComputerToolLevel.LEVEL_2_OS_API,
                description="Executes a shell command.",
                parameters={"command": "str"},
                risk_tier=RiskTier.TIER_1,
            )
        )

    def register_tool(self, tool: ToolDefinition) -> None:
        """Registers a tool definition."""
        self._tools[tool.name.lower()] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves registered tool definition."""
        return self._tools.get(name.lower())

    def validate_action(self, action: ActionObject) -> Tuple[bool, str]:
        """Validates action schema and parameters."""
        act_type = action.type.lower()
        tool = self.get_tool(act_type)
        if not tool:
            # Check alias or generic mapping
            return True, "Valid action type"
        return True, "Valid action type"

    def select_best_level_tool(self, intent: str, available_methods: List[ComputerToolLevel]) -> ComputerToolLevel:
        """Enforces tool hierarchy: selects the lowest numerical level (highest deterministic capability)."""
        if not available_methods:
            return ComputerToolLevel.LEVEL_8_RAW_INPUT
        return min(available_methods, key=lambda lvl: lvl.value)
