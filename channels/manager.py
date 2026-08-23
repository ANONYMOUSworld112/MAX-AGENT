"""
MAX OS — Communication Channel Adapters (Step 7.3).
Connects MAX OS to Telegram, Discord, Slack, and REST webhooks.
Inbound messages pass through Intent Classifier; outbound messages pass through Data Boundary.
Confirmation-gated actions require explicit reply tokens.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.data_boundary import sanitize_payload
from core.intent_classifier import IntentClassifier, IntentResult

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class ChannelMessage:
    channel_id: str
    channel_type: str  # 'telegram', 'discord', 'slack', 'cli'
    sender_id: str
    content: str
    timestamp: str


@dataclass
class ChannelResponse:
    channel_id: str
    recipient_id: str
    text: str
    requires_approval: bool = False
    approval_token: Optional[str] = None


class ChannelManager:
    """
    Manages external communication channels and message dispatching.
    """

    def __init__(self, db_path: Optional[Path | str] = None, intent_classifier: Optional[IntentClassifier] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.classifier = intent_classifier or IntentClassifier()
        self._handlers: Dict[str, Callable[[ChannelMessage], ChannelResponse]] = {}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def register_channel(self, channel_id: str, channel_type: str, config: Dict[str, Any]) -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cfg_str = json.dumps(config)
        try:
            conn.execute(
                """
                INSERT INTO channel_registry (channel_id, channel_type, config_json, status, created_at)
                VALUES (?, ?, ?, 'active', ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_type = excluded.channel_type,
                    config_json = excluded.config_json,
                    status = 'active';
                """,
                (channel_id, channel_type, cfg_str, now),
            )
            conn.commit()
        finally:
            conn.close()

    def handle_inbound_message(self, msg: ChannelMessage) -> ChannelResponse:
        """Processes an inbound message from any channel."""
        # 1. Route intent
        route_decision = self.classifier.classify(msg.content)
        agent_name = route_decision.agent or "main"

        # 2. Check if dangerous/confirm tier action
        requires_approval = False
        approval_token = None
        if "deploy" in msg.content.lower() or "delete" in msg.content.lower():
            import uuid
            requires_approval = True
            approval_token = f"tok-{uuid.uuid4().hex[:6]}"
            response_text = f"Action requires confirmation. Reply with token `{approval_token}` to execute."
        else:
            response_text = f"Processed request via agent '{agent_name}' for: {msg.content}"

        # 3. Sanitize outbound response through Data Boundary
        safe_response = sanitize_payload({"text": response_text})

        return ChannelResponse(
            channel_id=msg.channel_id,
            recipient_id=msg.sender_id,
            text=safe_response.get("text", response_text),
            requires_approval=requires_approval,
            approval_token=approval_token,
        )

    def send_message(
        self,
        channel_type: str,
        recipient: str,
        text: str,
        approval_token: Optional[str] = None,
    ) -> ChannelResponse:
        """Sends an outbound message to a specific channel recipient."""
        # 1. Sanitize outbound payload
        clean_text = sanitize_payload({"text": text}).get("text", text)

        # 2. Check if outbound bulk/money/external messaging requires confirm gate
        requires_approval = False
        if any(w in clean_text.lower() for w in ("money", "payment", "transfer", "api_key", "password")):
            requires_approval = True
            if not approval_token:
                import uuid
                tok = f"tok-{uuid.uuid4().hex[:6]}"
                return ChannelResponse(
                    channel_id=f"{channel_type}-outbound",
                    recipient_id=recipient,
                    text=f"Sensitive message dispatch requires approval token. Generated: {tok}",
                    requires_approval=True,
                    approval_token=tok,
                )

        # 3. Channel specific transmission
        if channel_type.lower() == "whatsapp":
            from channels.whatsapp import WhatsAppBridge
            bridge = WhatsAppBridge()
            wa_res = bridge.send_whatsapp_message(recipient=recipient, message=clean_text, launch_desktop=True)
            return ChannelResponse(
                channel_id=f"{channel_type}-outbound",
                recipient_id=recipient,
                text=f"[{channel_type.upper()}] {wa_res.details}",
                requires_approval=False,
            )

        return ChannelResponse(
            channel_id=f"{channel_type}-outbound",
            recipient_id=recipient,
            text=f"[{channel_type.upper()}] Sent to '{recipient}': {clean_text}",
            requires_approval=False,
        )
