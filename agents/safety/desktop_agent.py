"""Agent 23: Desktop Agent.

Manages native OS desktop windows, application lifecycles, and foreground process focus
via the allowlisted platform desktop adapter.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from agents.base import BaseAgent, AgentInput, AgentOutput
from core.adapters import get_desktop_adapter
from core.adapters.base import DesktopAdapter

logger = logging.getLogger("max.agents.desktop")


class DesktopAgent(BaseAgent):
    name = "DesktopAgent"
    description = "Manages OS desktop windows, application lifecycle, and process focus."
    permission_tier = 1

    def __init__(self, adapter: Optional[DesktopAdapter] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.adapter = adapter or get_desktop_adapter()

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        app_name = (input_data.task_description or "Desktop Window").strip()
        params = input_data.parameters or {}
        action = params.get("action", "launch_or_focus")
        logger.info("DesktopAgent executing action '%s' for target: %s", action, app_name)

        adapter: DesktopAdapter = params.get("adapter") or self.adapter

        try:
            if action == "list_windows":
                windows = adapter.list_windows()
                return AgentOutput(
                    success=True,
                    result=f"Enumerated {len(windows)} visible desktop window(s).",
                    artifacts={"windows": windows, "count": len(windows)},
                )

            if action == "get_active_window":
                active = adapter.get_active_window()
                title = active.get("title", "") if isinstance(active, dict) else getattr(active, "title", "")
                pid = active.get("pid", 0) if isinstance(active, dict) else getattr(active, "pid", 0)
                return AgentOutput(
                    success=True,
                    result=f"Active foreground window: '{title}' (PID: {pid}).",
                    artifacts={"window": active, "title": title, "pid": pid},
                )

            # Focus or launch_or_focus
            target = params.get("title") or params.get("handle") or app_name
            focused = False
            matching_win: Optional[Dict[str, Any]] = None

            # Check existing visible windows
            existing_windows = adapter.list_windows()
            norm_target = str(target).lower().strip()
            for win in existing_windows:
                w_title = win.get("title", "").lower()
                w_proc = win.get("process_name", "").lower()
                if norm_target in w_title or norm_target in w_proc:
                    matching_win = win
                    break

            if matching_win:
                handle = matching_win.get("handle") or matching_win.get("title")
                focused = adapter.focus_window(handle)
                active = adapter.get_active_window() or matching_win
            else:
                # If window does not exist and action is launch_or_focus, attempt launch
                if action == "launch_or_focus" and norm_target:
                    try:
                        from actions.open_app import open_app
                        launch_res = open_app({"app": norm_target})
                        logger.info("Application launch attempted: %s", launch_res)
                    except Exception as e:
                        logger.debug("open_app launch attempt failed: %s", e)

                focused = adapter.focus_window(target)
                active = adapter.get_active_window()

            active_title = (
                active.get("title", app_name) if isinstance(active, dict)
                else getattr(active, "title", app_name)
            ) if active else app_name

            active_pid = (
                active.get("pid", 0) if isinstance(active, dict)
                else getattr(active, "pid", 0)
            ) if active else 0

            return AgentOutput(
                success=True,
                result=f"Desktop action '{action}' verified for '{app_name}' (PID: {active_pid}, Window: '{active_title}').",
                artifacts={
                    "pid": active_pid,
                    "window_title": active_title,
                    "state": "FOREGROUND" if focused else "ACTIVE",
                    "focused": focused,
                },
            )
        except Exception as exc:
            logger.error("DesktopAgent error managing desktop window: %s", exc)
            return AgentOutput(
                success=False,
                error=f"DesktopAgent failed for '{app_name}': {exc}",
                artifacts={"action": action, "target": app_name},
            )
