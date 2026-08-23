"""
MAX OS — Agent-to-Agent (A2A) Protocol (Step 7.5).
Structured inter-agent message passing protocol with cycle prevention and trace logging.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed


class A2ACycleDetectedError(Exception):
    """Raised when an A2A call chain contains a recursive cycle."""
    pass


@dataclass
class A2AMessage:
    message_id: str
    sender_agent: str
    target_agent: str
    method: str
    params: Dict[str, Any]
    call_chain: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class A2AResponse:
    message_id: str
    sender_agent: str
    target_agent: str
    success: bool
    result: Any
    error: Optional[str] = None


class A2ARouter:
    """
    Inter-agent communication router.
    Prevents cycles and routes messages between registered agent handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[[A2AMessage], Any]] = {}

    def register_agent(self, agent_name: str, handler_fn: Callable[[A2AMessage], Any]) -> None:
        self._handlers[agent_name] = handler_fn

    def send_message(
        self,
        sender_agent: str,
        target_agent: str,
        method: str,
        params: Dict[str, Any],
        call_chain: Optional[List[str]] = None,
    ) -> A2AResponse:
        require_armed(get_kill_switch())

        chain = list(call_chain or [sender_agent])

        # Cycle detection: target cannot already be in the chain
        if target_agent in chain:
            raise A2ACycleDetectedError(
                f"A2A cycle detected: call chain {' -> '.join(chain)} -> {target_agent} contains a loop."
            )

        chain.append(target_agent)
        msg_id = f"a2a-{uuid.uuid4().hex[:8]}"

        msg = A2AMessage(
            message_id=msg_id,
            sender_agent=sender_agent,
            target_agent=target_agent,
            method=method,
            params=params,
            call_chain=chain,
        )

        handler = self._handlers.get(target_agent)
        if not handler:
            return A2AResponse(
                message_id=msg_id,
                sender_agent=sender_agent,
                target_agent=target_agent,
                success=False,
                result=None,
                error=f"Target agent '{target_agent}' is not registered in A2A router.",
            )

        try:
            res = handler(msg)
            return A2AResponse(
                message_id=msg_id,
                sender_agent=sender_agent,
                target_agent=target_agent,
                success=True,
                result=res,
            )
        except Exception as e:
            return A2AResponse(
                message_id=msg_id,
                sender_agent=sender_agent,
                target_agent=target_agent,
                success=False,
                result=None,
                error=str(e),
            )
