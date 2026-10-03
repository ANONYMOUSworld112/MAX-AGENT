"""
Lifecycle Hooks System (Task 10.2)
==================================

Pluggable lifecycle hook infrastructure enabling non-invasive observability,
telemetry, metrics capture, and policy enforcement across task and tool lifecycles.

Hook points:
  - before_task(task)
  - after_task(task, result)
  - before_tool(action_request)
  - after_tool(action_request, action_result)
  - on_failure(task, error)
  - on_verification(task, report)
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("max.hooks")


class HookPoint(str, enum.Enum):
    BEFORE_TASK = "before_task"
    AFTER_TASK = "after_task"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    ON_FAILURE = "on_failure"
    ON_VERIFICATION = "on_verification"


@dataclass(order=True)
class HookRegistration:
    priority: int
    name: str = field(compare=False)
    callback: Callable[..., Any] = field(compare=False)


class HookRegistry:
    """
    Central registry for lifecycle hooks executed across orchestrator operations.
    """

    _instance: Optional[HookRegistry] = None

    def __init__(self) -> None:
        self._hooks: Dict[HookPoint, List[HookRegistration]] = {hp: [] for hp in HookPoint}

    @classmethod
    def get_instance(cls) -> HookRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        point: Union[HookPoint, str],
        callback: Callable[..., Any],
        priority: int = 100,
        name: str = "",
    ) -> None:
        """
        Registers a hook callback. Lower priority numbers execute earlier.
        """
        hp = HookPoint(point) if isinstance(point, str) else point
        reg = HookRegistration(
            priority=priority,
            name=name or callback.__name__,
            callback=callback,
        )
        self._hooks[hp].append(reg)
        self._hooks[hp].sort()  # Maintain sorted by priority

    def unregister(self, point: Union[HookPoint, str], name: str) -> bool:
        hp = HookPoint(point) if isinstance(point, str) else point
        before_len = len(self._hooks[hp])
        self._hooks[hp] = [h for h in self._hooks[hp] if h.name != name]
        return len(self._hooks[hp]) < before_len

    def trigger(self, point: Union[HookPoint, str], *args: Any, **kwargs: Any) -> None:
        """
        Executes all registered hooks for the hook point in priority order.
        Any exception inside a hook is caught and logged, never crashing execution.
        """
        hp = HookPoint(point) if isinstance(point, str) else point
        for reg in self._hooks[hp]:
            try:
                reg.callback(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    "Error executing hook '%s' at hook point '%s': %s",
                    reg.name,
                    hp.value,
                    exc,
                    exc_info=True,
                )

    def clear(self) -> None:
        """Clears all registered hooks."""
        for hp in HookPoint:
            self._hooks[hp].clear()


# ---------------------------------------------------------------------------
# Built-in Metrics Collection Hook
# ---------------------------------------------------------------------------

class MetricsCollectorHook:
    """Hook implementation collecting task and tool performance metrics."""

    def __init__(self) -> None:
        self.task_starts = 0
        self.task_completions = 0
        self.tool_calls = 0
        self.tool_failures = 0
        self.verification_failures = 0

    def before_task(self, task: Any) -> None:
        self.task_starts += 1

    def after_task(self, task: Any, result: Any = None) -> None:
        self.task_completions += 1

    def before_tool(self, request: Any) -> None:
        self.tool_calls += 1

    def after_tool(self, request: Any, result: Any) -> None:
        if result and getattr(result, "success", True) is False:
            self.tool_failures += 1

    def on_verification(self, task: Any, report: Any) -> None:
        if report and getattr(report, "is_verified", True) is False:
            self.verification_failures += 1

    def register(self, registry: Optional[HookRegistry] = None) -> None:
        reg = registry or HookRegistry.get_instance()
        reg.register(HookPoint.BEFORE_TASK, self.before_task, name="metrics.before_task")
        reg.register(HookPoint.AFTER_TASK, self.after_task, name="metrics.after_task")
        reg.register(HookPoint.BEFORE_TOOL, self.before_tool, name="metrics.before_tool")
        reg.register(HookPoint.AFTER_TOOL, self.after_tool, name="metrics.after_tool")
        reg.register(HookPoint.ON_VERIFICATION, self.on_verification, name="metrics.on_verification")

    def get_metrics(self) -> dict[str, int]:
        return {
            "task_starts": self.task_starts,
            "task_completions": self.task_completions,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
            "verification_failures": self.verification_failures,
        }


LifecycleHookRegistry = HookRegistry
