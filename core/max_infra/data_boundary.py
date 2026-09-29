"""Component #1: Data Boundary & Token Scrubber.

Inspects all outbound prompts and network payloads for sensitive credentials,
API keys, personal identifiable information (PII), and replaces them
with reversible redaction tokens before sending to any cloud model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Pattern, Tuple


@dataclass
class ScrubResult:
    scrubbed_text: str
    token_map: Dict[str, str] = field(default_factory=dict)


class DataBoundary:
    # Compiled patterns for high-risk data leakage
    PATTERNS: list[Tuple[str, Pattern]] = [
        ("API_KEY", re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b")),
        ("API_KEY", re.compile(r"\bAIza[0-9A-Za-z-_]{30,40}\b")),
        ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
        ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9\-_.]{20,}\b")),
    ]

    def scrub(self, text: str) -> ScrubResult:
        if not text:
            return ScrubResult(scrubbed_text="", token_map={})

        token_map: Dict[str, str] = {}
        scrubbed = text
        token_counter = 1

        for label, pattern in self.PATTERNS:
            matches = list(pattern.finditer(scrubbed))
            # Process in reverse order so string indices remain valid
            for match in reversed(matches):
                secret = match.group(0)
                # Check if we already assigned a token for this secret
                existing_token = None
                for t, s in token_map.items():
                    if s == secret:
                        existing_token = t
                        break

                if not existing_token:
                    token = f"[REDACTED_{label}_{token_counter}]"
                    token_counter += 1
                    token_map[token] = secret
                else:
                    token = existing_token

                start, end = match.span()
                scrubbed = scrubbed[:start] + token + scrubbed[end:]

        return ScrubResult(scrubbed_text=scrubbed, token_map=token_map)

    def unscrub(self, scrubbed_text: str, token_map: Dict[str, str]) -> str:
        if not scrubbed_text or not token_map:
            return scrubbed_text

        result = scrubbed_text
        for token, original in token_map.items():
            result = result.replace(token, original)
        return result
