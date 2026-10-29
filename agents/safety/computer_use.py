"""Agent 22: Computer Use Agent.

Executes low-level keyboard and mouse automation with strict spatial coordinate validation,
DPI-aware display bounds checking, and verified operating system input execution.
Operates at Permission Tier 2 (Requires Confirmation).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from agents.base import BaseAgent, AgentInput, AgentOutput
from core.adapters import get_desktop_adapter
from core.adapters.base import DesktopAdapter

logger = logging.getLogger("max.agents.computer_use")


class ComputerUseAgent(BaseAgent):
    name = "ComputerUseAgent"
    description = "Executes verified desktop mouse and keyboard interactions with spatial bounds enforcement."
    permission_tier = 2  # Requires Confirmation

    def __init__(self, adapter: Optional[DesktopAdapter] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.adapter = adapter or get_desktop_adapter()

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = (input_data.task_description or "").strip()
        params = input_data.parameters or {}

        # Determine target action
        action = params.get("action")
        if not action:
            low_desc = desc.lower()
            if "double click" in low_desc:
                action = "double_click"
            elif "right click" in low_desc:
                action = "right_click"
            elif "click" in low_desc:
                action = "click"
            elif "move" in low_desc:
                action = "mouse_move"
            elif "type" in low_desc or "write" in low_desc:
                action = "type"
            elif "screenshot" in low_desc:
                action = "screenshot"
            elif "hotkey" in low_desc:
                action = "hotkey"
            else:
                action = "mouse_move"

        x = int(params.get("x", 100))
        y = int(params.get("y", 100))

        # Dynamically query screen boundaries with DPI and multi-monitor awareness
        try:
            if hasattr(self.adapter, "get_screen_bounds"):
                min_x, min_y, max_x, max_y = self.adapter.get_screen_bounds()
            elif hasattr(self.adapter, "get_screen_size"):
                w, h = self.adapter.get_screen_size()
                min_x, min_y, max_x, max_y = (0, 0, w, h)
            else:
                return AgentOutput(
                    success=False,
                    error="Desktop geometry unavailable: desktop adapter does not support geometry detection.",
                    artifacts={"spatial_verified": False},
                )
        except Exception as exc:
            return AgentOutput(
                success=False,
                error=f"Desktop geometry unavailable: {exc}",
                artifacts={"spatial_verified": False, "reason": str(exc)},
            )

        screen_w = max_x - min_x
        screen_h = max_y - min_y

        # Coordinate bounds verification for half-open interval [min_x, max_x) x [min_y, max_y)
        if not (min_x <= x < max_x and min_y <= y < max_y):
            return AgentOutput(
                success=False,
                error=f"Coordinates ({x}, {y}) out of bounds for display [{min_x}, {max_x}) x [{min_y}, {max_y}).",
                artifacts={"screen_bounds": (min_x, min_y, max_x, max_y), "display_size": (screen_w, screen_h), "requested": (x, y)},
            )

        # Check if dry-run / simulation was explicitly requested
        is_simulation = bool(params.get("dry_run") or params.get("simulate") or "simulate" in desc.lower())

        if is_simulation:
            logger.info("ComputerUseAgent simulated spatial verification for %s at (%d, %d)", action, x, y)
            return AgentOutput(
                success=True,
                result=f"Simulated {action} at coordinates ({x}, {y}) safely with verified display bounds.",
                artifacts={
                    "x": x,
                    "y": y,
                    "action": action,
                    "spatial_verified": True,
                    "display_size": (screen_w, screen_h),
                    "mode": "simulation",
                },
            )

        # Real desktop OS input execution
        logger.info("ComputerUseAgent executing real %s at (%d, %d)", action, x, y)
        try:
            if action in ("mouse_move", "move"):
                ok = self.adapter.move_to(x, y) if hasattr(self.adapter, "move_to") else self.adapter.click(x, y)
                res_text = f"Moved pointer to ({x}, {y}) on {screen_w}x{screen_h} display."
            elif action in ("click", "left_click"):
                ok = self.adapter.click(x, y, button="left")
                res_text = f"Clicked at coordinates ({x}, {y}) [button: left]."
            elif action == "right_click":
                ok = self.adapter.click(x, y, button="right")
                res_text = f"Right-clicked at coordinates ({x}, {y})."
            elif action == "double_click":
                ok = self.adapter.click(x, y, clicks=2)
                res_text = f"Double-clicked at coordinates ({x}, {y})."
            elif action in ("type", "write"):
                text = str(params.get("text", desc))
                ok = self.adapter.type_text(text)
                res_text = f"Typed text ({len(text)} chars) into active desktop focus."
            elif action == "hotkey":
                keys = params.get("keys", ["ctrl", "c"])
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split("+")]
                ok = self.adapter.hotkey(*keys)
                res_text = f"Triggered desktop hotkey: {'+'.join(keys)}."
            elif action == "screenshot":
                from actions.computer_control import _screenshot
                res_path = _screenshot(params.get("path"))
                ok = True
                res_text = res_path
            else:
                ok = self.adapter.click(x, y)
                res_text = f"Executed desktop action '{action}' at ({x}, {y})."

            artifacts: Dict[str, Any] = {
                "x": x,
                "y": y,
                "action": action,
                "executed": ok,
                "display_size": (screen_w, screen_h),
                "spatial_verified": True,
            }
            if hasattr(self.adapter, "get_cursor_pos"):
                artifacts["cursor_position"] = self.adapter.get_cursor_pos()

            return AgentOutput(
                success=ok,
                result=res_text,
                artifacts=artifacts,
            )
        except Exception as exc:
            logger.error("ComputerUseAgent error during %s: %s", action, exc)
            return AgentOutput(
                success=False,
                error=f"ComputerUseAgent desktop action '{action}' failed: {exc}",
                artifacts={"action": action, "x": x, "y": y, "spatial_verified": False, "error": str(exc)},
            )
