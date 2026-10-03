"""
MAX-AGENT Capability Registry
==============================

Extends the action and agent discovery system into a comprehensive
CapabilityRegistry.

Each capability declares:
  - Canonical name and human-readable description
  - Parameter schema (JSON schema)
  - Declared resources required during execution
  - Idempotency classification (READ_ONLY, IDEMPOTENT, NON_IDEMPOTENT)
  - Postcondition template for verification
  - Base RiskLevel (LOW, MEDIUM, HIGH, CRITICAL)
  - Verification method (process_exit, file_exists, ui_state, read_only, none)

Master Spec references:
  - Section 6 (CapabilityRegistry)
  - Section 7 (Agent Routing)
  - Section 13 (Risk & Policy)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from core.contracts import RiskLevel

logger = logging.getLogger("max.capability_registry")


class IdempotencyClass(str, Enum):
    """Execution idempotency classification."""
    READ_ONLY = "READ_ONLY"
    IDEMPOTENT = "IDEMPOTENT"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"


# Known risk and verification mappings for standard actions
_DEFAULT_ACTION_METADATA: dict[str, dict[str, Any]] = {
    "open_app": {
        "resources": ["display", "os.process"],
        "idempotency": IdempotencyClass.IDEMPOTENT,
        "risk": RiskLevel.LOW,
        "verification": "process_running",
        "postcondition": "process '{app_name}' is running in window manager",
    },
    "web_search": {
        "resources": ["network"],
        "idempotency": IdempotencyClass.READ_ONLY,
        "risk": RiskLevel.LOW,
        "verification": "read_only",
        "postcondition": "search results returned",
    },
    "youtube_video": {
        "resources": ["audio-out", "network"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.LOW,
        "verification": "media_playing",
        "postcondition": "audio track is playing",
    },
    "get_system_status": {
        "resources": ["os.metrics"],
        "idempotency": IdempotencyClass.READ_ONLY,
        "risk": RiskLevel.LOW,
        "verification": "read_only",
        "postcondition": "metrics sampled",
    },
    "screenshot": {
        "resources": ["display"],
        "idempotency": IdempotencyClass.READ_ONLY,
        "risk": RiskLevel.LOW,
        "verification": "read_only",
        "postcondition": "image captured",
    },
    "system_control": {
        "resources": ["os.system"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.MEDIUM,
        "verification": "state_query",
        "postcondition": "system setting modified",
    },
    "set_reminder": {
        "resources": ["scheduler"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.LOW,
        "verification": "scheduler_lookup",
        "postcondition": "reminder scheduled with host",
    },
    "calendaragent": {
        "resources": ["calendar"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.MEDIUM,
        "verification": "calendar_event_exists",
        "postcondition": "calendar event confirmed",
    },
    "emailagent": {
        "resources": ["network", "email_account"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.HIGH,
        "verification": "provider_receipt",
        "postcondition": "email sent or drafted",
    },
    "codingagent": {
        "resources": ["filesystem"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.MEDIUM,
        "verification": "file_exists",
        "postcondition": "code written to allowed workspace",
    },
    "computeruseagent": {
        "resources": ["display", "mouse", "keyboard"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.HIGH,
        "verification": "ui_state",
        "postcondition": "target element interacted with",
    },
    "desktopagent": {
        "resources": ["display", "os.window"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.MEDIUM,
        "verification": "window_state",
        "postcondition": "window manipulated",
    },
    "fileorganizer": {
        "resources": ["filesystem"],
        "idempotency": IdempotencyClass.NON_IDEMPOTENT,
        "risk": RiskLevel.MEDIUM,
        "verification": "file_exists",
        "postcondition": "files moved or organized",
    },
    "securitygate": {
        "resources": ["security_policy"],
        "idempotency": IdempotencyClass.READ_ONLY,
        "risk": RiskLevel.LOW,
        "verification": "read_only",
        "postcondition": "risk evaluation completed",
    },
}


@dataclass
class CapabilityEntry:
    """A fully specified capability registered in MAX."""
    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    declared_resources: list[str] = field(default_factory=list)
    idempotency_class: IdempotencyClass = IdempotencyClass.NON_IDEMPOTENT
    postcondition_template: Optional[str] = None
    base_risk_level: RiskLevel = RiskLevel.MEDIUM
    verification_method: str = "none"
    handler: Optional[Callable] = None
    is_agent: bool = False
    agent_class: Optional[str] = None
    enabled: bool = True

    def to_tool_declaration(self) -> dict[str, Any]:
        """Format as a Gemini function-declaration schema."""
        return {
            "name": self.name.lower(),
            "description": self.description,
            "parameters": self.parameters or {
                "type": "OBJECT",
                "properties": {},
            },
        }

    def validate_schema(self) -> list[str]:
        """Validate parameter schema structure. Returns list of errors."""
        errors: list[str] = []
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$", self.name):
            errors.append(f"Invalid capability name: '{self.name}'")

        if not isinstance(self.parameters, dict):
            errors.append("Parameters must be a dict")
        else:
            p_type = self.parameters.get("type", "").upper()
            if p_type and p_type not in ("OBJECT", "ARRAY", "STRING", "INTEGER", "NUMBER", "BOOLEAN"):
                errors.append(f"Invalid schema type: {p_type}")

        return errors


class CapabilityRegistry:
    """
    Central registry for all executable capabilities (actions, plugins, agents).

    Provides:
      - Capability registration and schema validation
      - Lookup by name, resource, and risk level
      - Scoped tool declaration generation (bounds LLM reasoning space)
      - Bulk ingestion from ActionRegistry and AgentRegistry
    """

    _instance: Optional[CapabilityRegistry] = None

    def __init__(self, seed_defaults: bool = False) -> None:
        self._capabilities: dict[str, CapabilityEntry] = {}
        if seed_defaults:
            for name, meta in _DEFAULT_ACTION_METADATA.items():
                self.register(CapabilityEntry(
                    name=name,
                    description=meta.get("postcondition", name),
                    declared_resources=meta.get("resources", []),
                    idempotency_class=meta.get("idempotency", IdempotencyClass.NON_IDEMPOTENT),
                    base_risk_level=meta.get("risk", RiskLevel.MEDIUM),
                    verification_method=meta.get("verification", "none"),
                    postcondition_template=meta.get("postcondition"),
                ))

    @classmethod
    def get_instance(cls) -> CapabilityRegistry:
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls(seed_defaults=True)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def register(self, entry: CapabilityEntry) -> None:
        """Register a new capability. Canonicalized to lowercase."""
        canonical = entry.name.lower()
        self._capabilities[canonical] = entry
        logger.debug("Registered capability '%s' (risk=%s, agent=%s)", canonical, entry.base_risk_level.name, entry.is_agent)

    def get(self, name: str) -> Optional[CapabilityEntry]:
        """Look up capability by canonical name or alias."""
        return self._capabilities.get(name.lower())

    def has(self, name: str) -> bool:
        """Check if capability is registered."""
        return name.lower() in self._capabilities

    def names(self) -> set[str]:
        """Return all registered capability names."""
        return set(self._capabilities.keys())

    def list_all(self, enabled_only: bool = True) -> list[CapabilityEntry]:
        """Return list of all registered capabilities."""
        if enabled_only:
            return [c for c in self._capabilities.values() if c.enabled]
        return list(self._capabilities.values())

    def find_by_resource(self, resource: str) -> list[CapabilityEntry]:
        """Find capabilities that declare a specific resource."""
        res_lower = resource.lower()
        return [
            c for c in self._capabilities.values()
            if any(res_lower in r.lower() for r in c.declared_resources)
        ]

    def find_by_risk(self, risk_level: RiskLevel) -> list[CapabilityEntry]:
        """Find capabilities matching a specific risk level."""
        return [c for c in self._capabilities.values() if c.base_risk_level == risk_level]

    def get_scoped_tool_declarations(self, names: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """
        Generate bounded tool declarations for LLM exposure.

        If `names` is provided, exposes ONLY those specific capabilities,
        preventing flat-60 tool exposure and hallucination.
        """
        if names is None:
            entries = self.list_all(enabled_only=True)
        else:
            entries = []
            for n in names:
                cap = self.get(n)
                if cap and cap.enabled:
                    entries.append(cap)

        return [c.to_tool_declaration() for c in entries]

    def load_from_action_registry(self, action_registry: Any) -> int:
        """
        Bulk ingest actions from ActionRegistry.

        Returns number of newly registered capabilities.
        """
        count = 0
        actions = getattr(action_registry, "_actions", {})
        for name, rec in actions.items():
            canonical = name.lower()
            if canonical in self._capabilities:
                continue

            meta = _DEFAULT_ACTION_METADATA.get(canonical, {})
            entry = CapabilityEntry(
                name=canonical,
                description=rec.description,
                parameters=rec.parameters if isinstance(rec.parameters, dict) else {},
                declared_resources=meta.get("resources", ["system"]),
                idempotency_class=meta.get("idempotency", IdempotencyClass.NON_IDEMPOTENT),
                postcondition_template=meta.get("postcondition"),
                base_risk_level=meta.get("risk", RiskLevel.MEDIUM),
                verification_method=meta.get("verification", "none"),
                handler=rec.handler,
                is_agent=False,
                enabled=rec.valid,
            )
            self.register(entry)
            count += 1

        return count

    def load_from_agent_registry(self, agent_registry: Any) -> int:
        """
        Bulk ingest agents from AgentRegistry.

        Returns number of newly registered agent capabilities.
        """
        count = 0
        agents = getattr(agent_registry, "_agents", {})
        for name, agent in agents.items():
            canonical = name.lower()
            if canonical in self._capabilities:
                continue

            tool_def = agent.get_tool_definition()
            meta = _DEFAULT_ACTION_METADATA.get(canonical, {})
            entry = CapabilityEntry(
                name=canonical,
                description=tool_def.get("description", agent.description),
                parameters=tool_def.get("parameters", {}),
                declared_resources=meta.get("resources", ["agent"]),
                idempotency_class=meta.get("idempotency", IdempotencyClass.NON_IDEMPOTENT),
                postcondition_template=meta.get("postcondition"),
                base_risk_level=meta.get("risk", RiskLevel.MEDIUM),
                verification_method=meta.get("verification", "none"),
                handler=agent.run,
                is_agent=True,
                agent_class=agent.__class__.__name__,
                enabled=True,
            )
            self.register(entry)
            count += 1

        return count

    def validate_schemas(self) -> dict[str, list[str]]:
        """Validate all registered capability schemas. Returns {name: [errors]}."""
        errors: dict[str, list[str]] = {}
        for name, entry in self._capabilities.items():
            errs = entry.validate_schema()
            if errs:
                errors[name] = errs
        return errors
