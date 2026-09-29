"""5-Layer Memory Context Heap for MAX OS.

Hierarchical state management partitioned into 5 discrete tiers:
- Layer 1: System Identity & Safety Invariants (Fixed, highest priority)
- Layer 2: User Preferences & Style
- Layer 3: Learned Behavioral Patterns & Anti-Patterns
- Layer 4: Active Project State & Architectural Context
- Layer 5: Conversational Scratchpad & Working Memory

Zero unbudgeted prompt overflow.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from core.memory.token_budget import TokenBudgetCompressor

logger = logging.getLogger("max.memory.context_heap")


class MemoryContextHeap:
    def __init__(self, db=None) -> None:
        self._lock = threading.RLock()
        self.db = db
        self._l1_identity: str = "You are MAX / MAX. Absolute loyalty to user. Zero safety compromises."
        self._l2_preferences: Dict[str, str] = {}
        self._l3_behavioral: Dict[str, str] = {}
        self._l4_project: Dict[str, str] = {}
        self._l5_conversation: List[Dict[str, str]] = []

    def set_identity(self, identity: str) -> None:
        with self._lock:
            self._l1_identity = identity

    def set_preference(self, key: str, value: str) -> None:
        with self._lock:
            self._l2_preferences[key] = value

    def set_behavioral_pattern(self, key: str, pattern: str) -> None:
        with self._lock:
            self._l3_behavioral[key] = pattern

    def set_project_state(self, key: str, value: str) -> None:
        with self._lock:
            self._l4_project[key] = value

    def add_conversation_turn(self, role: str, content: str) -> None:
        with self._lock:
            self._l5_conversation.append({"role": role, "content": content})
            # Keep only last 10 turns in active L5 memory
            if len(self._l5_conversation) > 10:
                self._l5_conversation.pop(0)

    def get_composite_context(self, max_tokens: int = 2048) -> str:
        with self._lock:
            sections = []

            # Layer 1: Identity
            sections.append(f"### [L1: SYSTEM IDENTITY]\n{self._l1_identity}\n")

            # Layer 2: Preferences
            if self._l2_preferences:
                prefs = "\n".join(f"- {k}: {v}" for k, v in self._l2_preferences.items())
                sections.append(f"### [L2: USER PREFERENCES]\n{prefs}\n")

            # Layer 3: Behavioral Patterns
            if self._l3_behavioral:
                behav = "\n".join(f"- {k}: {v}" for k, v in self._l3_behavioral.items())
                sections.append(f"### [L3: BEHAVIORAL PATTERNS & ANTI-PATTERNS]\n{behav}\n")

            # Layer 4: Project State
            if self._l4_project:
                proj = "\n".join(f"- {k}: {v}" for k, v in self._l4_project.items())
                sections.append(f"### [L4: ACTIVE PROJECT STATE]\n{proj}\n")

            # Layer 5: Conversation
            if self._l5_conversation:
                conv = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in self._l5_conversation)
                sections.append(f"### [L5: RECENT CONVERSATION]\n{conv}\n")

            full_text = "\n".join(sections)
            compressor = TokenBudgetCompressor(max_budget=max_tokens)
            return compressor.compress(full_text)

