"""
MAX OS — Intent Classifier
Build Order: #16 (Layer 4A)
═══════════════════════════════════════════════════════

Classifies incoming prompt text into targeting agents or direct conversational chat:
- simple_chat (greetings, general chat — NO subagents triggered!)
- calendar (schedule, reminder, meeting, event, time)
- notes (note, memo, store note, remember, search notes)
- research (search web, find paper, lookup)
- coding (code, refactor, debug, write python, react, fix bug)
- deploy (deploy, push, build release, production)
- terminal (run command, ls, ps, status, zsh, bash)
- system (cpu, ram, health, telemetry, kill, restart)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from src.infra import data_boundary
from src.routing.permissions import get_permission_tier, PermissionTier

logger = logging.getLogger("max.routing.intent_classifier")


@dataclass
class IntentResult:
    agent: str
    intent: str
    confidence: float
    permission_tier: PermissionTier
    clean_text: str
    is_simple_chat: bool = False


# Words/phrases indicating simple conversational input (do not trigger subagents)
_SIMPLE_CHAT_PATTERNS = [
    re.compile(r"^(hi|hello|hey|greetings|hola|sup|yo|good (morning|afternoon|evening))\b", re.I),
    re.compile(r"^(who are you|what is your name|how are you|what can you do|help me|tell me a joke)\b", re.I),
    re.compile(r"^(thanks|thank you|awesome|cool|great|ok|okay|bye|goodbye)\b", re.I),
]

_OPERATIONAL_KEYWORDS = [
    "deploy", "run", "code", "script", "terminal", "zsh", "bash", "schedule",
    "meeting", "calendar", "note", "remember", "install", "git", "python", "react", "build",
    "file", "folder", "organize", "search", "browse", "click", "browser", "document", "presentation"
]


def classify(prompt_text: str) -> IntentResult:
    """Classify user prompt and sanitize text through data boundary."""
    clean_text = data_boundary.sanitize(prompt_text.strip())
    text_lower = clean_text.lower()
    words = text_lower.split()

    # 1. Check if simple conversational chat (no operational keywords)
    has_op_keyword = any(kw in text_lower for kw in _OPERATIONAL_KEYWORDS)
    is_simple = False

    if not has_op_keyword:
        if len(words) <= 6:
            is_simple = True
        else:
            for pattern in _SIMPLE_CHAT_PATTERNS:
                if pattern.search(text_lower):
                    is_simple = True
                    break

    if is_simple:
        return IntentResult(
            agent="conversational",
            intent="simple_chat",
            confidence=0.99,
            permission_tier=PermissionTier.AUTO,
            clean_text=clean_text,
            is_simple_chat=True,
        )

    # 2. Operational Sub-agent classification
    if any(k in text_lower for k in ["calendar", "schedule", "meeting", "reminder", "appointment", "event"]):
        agent = "calendar"
        intent = "schedule_or_event"
        confidence = 0.95
    elif any(k in text_lower for k in ["note", "memo", "remember that", "take a note", "read notes"]):
        agent = "notes"
        intent = "manage_notes"
        confidence = 0.92
    elif any(k in text_lower for k in ["deploy", "ship", "push to github", "release prod", "production"]):
        agent = "deploy"
        intent = "production_deploy"
        confidence = 0.96
    elif any(k in text_lower for k in ["code", "function", "refactor", "debug", "typescript", "python", "react", "fix bug", "script"]):
        agent = "coding"
        intent = "code_task"
        confidence = 0.90
    elif any(k in text_lower for k in ["file", "folder", "directory", "clean temp", "archive", "move file"]):
        agent = "file"
        intent = "filesystem_operation"
        confidence = 0.94
    elif any(k in text_lower for k in ["terminal", "shell", "bash", "command", "psutil", "ls ", "execute"]):
        agent = "terminal"
        intent = "terminal_command"
        confidence = 0.93
    elif any(k in text_lower for k in ["browser", "website", "chrome", "google.com", "open url", "navigate"]):
        agent = "browser"
        intent = "browser_navigation"
        confidence = 0.95
    elif any(k in text_lower for k in ["desktop", "screen", "click", "mouse", "keyboard", "window", "otav"]):
        agent = "desktop"
        intent = "desktop_interaction"
        confidence = 0.92
    elif any(k in text_lower for k in ["document", "presentation", "report", "pdf", "slides", "ppt"]):
        agent = "document"
        intent = "generate_document"
        confidence = 0.93
    elif any(k in text_lower for k in ["search web", "research", "paper", "arxiv", "lookup", "what is"]):
        agent = "research"
        intent = "web_research"
        confidence = 0.91
    elif any(k in text_lower for k in ["status", "metrics", "cpu", "ram", "telemetry", "health", "system"]):
        agent = "system"
        intent = "system_telemetry"
        confidence = 0.94
    else:
        agent = "coding"
        confidence = 0.75

    tier = get_permission_tier(agent, intent)

    logger.info("Classified prompt -> agent='%s', intent='%s', confidence=%.2f, tier='%s', is_simple=%s",
                agent, intent, confidence, tier.value, is_simple)
    return IntentResult(
        agent=agent,
        intent=intent,
        confidence=confidence,
        permission_tier=tier,
        clean_text=clean_text,
        is_simple_chat=False,
    )
