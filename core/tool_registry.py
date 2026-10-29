"""
core/tool_registry.py — Plugin Tool Registry for FRIDAY.

Discovers, validates, and dispatches plugin tools stored as:
    tools/<name>/manifest.json
    tools/<name>/handler.py

Enforces:
  - JSON Schema validation for manifests
  - Permission tiers (T0: auto, T1: auto+logged, T2: confirm, T3: forbidden)
  - Timeouts per tool
  - Dynamic hot-reloading on file change
  - Hash-chained audit logging and event emission
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import jsonschema

from core.contracts import EventEnvelope
from core.events import (
    AuditWriter,
    EventBus,
    create_tool_call_event,
    create_tool_result_event,
)

logger = logging.getLogger("friday.tools")

MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["name", "description", "permission_tier", "parameters"],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]+$"
        },
        "description": {"type": "string", "minLength": 5},
        "permission_tier": {
            "type": "string",
            "enum": ["T0", "T1", "T2", "T3"]
        },
        "timeout_seconds": {"type": "number", "minimum": 0.5, "maximum": 300.0},
        "parameters": {"type": "object"}
    }
}


class InvalidManifestError(Exception):
    """Raised when a tool manifest fails JSON Schema validation."""
    pass


class ForbiddenActionError(PermissionError):
    """Raised when a T3 action is attempted."""
    pass


class ActionConfirmationDeniedError(PermissionError):
    """Raised when user denies confirmation for a T2 tool."""
    pass


@dataclass
class ToolRecord:
    name: str
    description: str
    permission_tier: str
    timeout_seconds: float
    parameters: dict[str, Any]
    directory: Path
    manifest_path: Path
    handler_path: Path
    handler_func: Optional[Callable[..., Any]] = None
    manifest_mtime: float = 0.0
    handler_mtime: float = 0.0


ConfirmationCallback = Callable[[str, dict[str, Any]], Awaitable[bool] | bool]


class ToolRegistry:
    """Manages discoverable, hot-reloadable tools with permission tier governance."""

    def __init__(
        self,
        tools_dir: Path | str,
        event_bus: Optional[EventBus] = None,
        audit_writer: Optional[AuditWriter] = None,
    ) -> None:
        self.tools_dir = Path(tools_dir)
        self.event_bus = event_bus
        self.audit_writer = audit_writer
        self._tools: dict[str, ToolRecord] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.tools_dir.is_dir():
            self.tools_dir.mkdir(parents=True, exist_ok=True)
            return

        for manifest_file in self.tools_dir.glob("*/manifest.json"):
            try:
                self._load_tool(manifest_file)
            except Exception as e:
                logger.error("Failed to load tool at %s: %s", manifest_file, e)

    def _load_tool(self, manifest_file: Path) -> ToolRecord:
        raw_text = manifest_file.read_text(encoding="utf-8")
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise InvalidManifestError(f"Malformed JSON in {manifest_file}: {e}") from e

        # Validate against schema
        try:
            jsonschema.validate(instance=data, schema=MANIFEST_SCHEMA)
        except jsonschema.ValidationError as e:
            raise InvalidManifestError(f"Manifest schema validation failed for {manifest_file}: {e.message}") from e

        name = data["name"]
        tier = data["permission_tier"].upper()
        timeout = float(data.get("timeout_seconds", 15.0))
        params = data["parameters"]
        description = data["description"]

        handler_file = manifest_file.parent / "handler.py"
        if not handler_file.is_file():
            raise InvalidManifestError(f"Missing handler.py for tool {name} at {handler_file}")

        # Load handler module dynamically
        handler_func = self._import_handler(name, handler_file)

        record = ToolRecord(
            name=name,
            description=description,
            permission_tier=tier,
            timeout_seconds=timeout,
            parameters=params,
            directory=manifest_file.parent,
            manifest_path=manifest_file,
            handler_path=handler_file,
            handler_func=handler_func,
            manifest_mtime=manifest_file.stat().st_mtime,
            handler_mtime=handler_file.stat().st_mtime,
        )
        self._tools[name] = record
        logger.info("Registered tool '%s' [Tier: %s]", name, tier)
        return record

    def _import_handler(self, name: str, handler_path: Path) -> Callable[..., Any]:
        module_name = f"friday_tool_{name}"
        spec = importlib.util.spec_from_file_location(module_name, handler_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {handler_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "handle"):
            return getattr(module, "handle")
        elif hasattr(module, "run"):
            return getattr(module, "run")
        elif hasattr(module, "execute"):
            return getattr(module, "execute")
        else:
            raise AttributeError(f"Tool handler {handler_path} must define 'handle(params)' or 'run(params)'")

    def check_hot_reload(self) -> None:
        """Scan directory and reload any modified or newly added tools."""
        if not self.tools_dir.is_dir():
            return

        for manifest_file in self.tools_dir.glob("*/manifest.json"):
            name = manifest_file.parent.name
            record = self._tools.get(name)
            if record is None:
                try:
                    self._load_tool(manifest_file)
                except Exception as e:
                    logger.warning("Hot reload: failed to add %s: %s", name, e)
            else:
                mtime_m = manifest_file.stat().st_mtime
                h_file = record.handler_path
                mtime_h = h_file.stat().st_mtime if h_file.exists() else 0.0
                if mtime_m > record.manifest_mtime or mtime_h > record.handler_mtime:
                    try:
                        self._load_tool(manifest_file)
                        logger.info("Hot-reloaded tool '%s'", name)
                    except Exception as e:
                        logger.warning("Hot reload failed for %s: %s", name, e)

    def get_tool(self, name: str) -> Optional[ToolRecord]:
        self.check_hot_reload()
        return self._tools.get(name)

    def list_tools(self) -> list[ToolRecord]:
        self.check_hot_reload()
        return list(self._tools.values())

    def get_tool_declarations(self) -> list[dict[str, Any]]:
        """Return tool declarations in Gemini / Claude function-calling format."""
        self.check_hot_reload()
        decls = []
        for rec in self._tools.values():
            if rec.permission_tier == "T3":
                continue  # Never expose forbidden tools
            decls.append({
                "name": rec.name,
                "description": f"[{rec.permission_tier}] {rec.description}",
                "parameters": rec.parameters,
                "permission_tier": rec.permission_tier,
            })
        return decls

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        confirm_callback: Optional[ConfirmationCallback] = None,
        correlation_id: str = "",
    ) -> dict[str, Any]:
        """
        Execute a tool with tier checks, confirmation gates, timeouts, and audit logging.
        """
        from core.kill_switch import is_armed
        if not is_armed():
            msg = f"Emergency Halt: System is DISARMED by Kill Switch. Tool '{name}' cannot run."
            if self.event_bus:
                self.event_bus.publish(create_tool_result_event(name, msg, status="disarmed", correlation_id=correlation_id))
            raise PermissionError(msg)

        self.check_hot_reload()
        record = self._tools.get(name)
        if not record:
            return {
                "success": False,
                "error": f"Tool '{name}' is not registered.",
                "output": None
            }

        tier = record.permission_tier

        # T3: Forbidden actions
        if tier == "T3":
            msg = f"Security Violation: Action '{name}' is classified as T3 (Forbidden) and cannot be executed."
            if self.event_bus:
                self.event_bus.publish(create_tool_result_event(name, msg, status="forbidden", correlation_id=correlation_id))
            raise ForbiddenActionError(msg)

        # T2: Sensitive actions requiring confirmation
        if tier == "T2":
            confirmed = False
            if confirm_callback:
                res = confirm_callback(name, arguments)
                if asyncio.iscoroutine(res):
                    confirmed = await res
                else:
                    confirmed = bool(res)

            if not confirmed:
                msg = f"Action '{name}' cancelled: User confirmation was denied for Tier 2 operation."
                if self.event_bus:
                    self.event_bus.publish(create_tool_result_event(name, msg, status="denied", correlation_id=correlation_id))
                raise ActionConfirmationDeniedError(msg)

        # Emit tool_call event
        if self.event_bus:
            self.event_bus.publish(create_tool_call_event(name, arguments, correlation_id=correlation_id))

        start_time = time.monotonic()
        try:
            handler = record.handler_func
            if handler is None:
                raise RuntimeError(f"Tool '{name}' handler is not loaded")

            # Call handler with timeout
            if asyncio.iscoroutinefunction(handler):
                coro = handler(arguments)
                result = await asyncio.wait_for(coro, timeout=record.timeout_seconds)
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, handler, arguments),
                    timeout=record.timeout_seconds,
                )

            duration_ms = (time.monotonic() - start_time) * 1000.0

            # Emit tool_result event
            if self.event_bus:
                self.event_bus.publish(create_tool_result_event(name, result, status="success", correlation_id=correlation_id))

            # Record in audit log
            if self.audit_writer:
                self.audit_writer.record(
                    event_type="tool_execution",
                    actor=f"tool:{name}",
                    correlation_id=correlation_id,
                    payload={
                        "tool": name,
                        "tier": tier,
                        "arguments": arguments,
                        "duration_ms": duration_ms,
                        "status": "success",
                        "output": str(result)[:500],
                    }
                )

            return {
                "success": True,
                "output": result,
                "duration_ms": duration_ms,
                "tier": tier
            }

        except asyncio.TimeoutError:
            err = f"Tool '{name}' timed out after {record.timeout_seconds}s."
            if self.event_bus:
                self.event_bus.publish(create_tool_result_event(name, err, status="timeout", correlation_id=correlation_id))
            return {"success": False, "error": err, "output": None}

        except Exception as e:
            err = f"Tool '{name}' error: {e}"
            logger.exception("Tool execution error in %s", name)
            if self.event_bus:
                self.event_bus.publish(create_tool_result_event(name, err, status="error", correlation_id=correlation_id))
            return {"success": False, "error": err, "output": None}
