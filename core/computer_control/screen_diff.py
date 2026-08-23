"""
MAX OS — Visual Screen Diff & Change Detection Engine (Phase 12).
Compares screen states before and after local actions to verify UI change
without triggering full visual LLM inference calls.
"""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class VisualDiffResult:
    has_changed: bool
    diff_score: float  # 0.0 (identical) to 1.0 (completely different)
    details: str


class ScreenDiffEngine:
    """
    Fast local screen difference calculator.
    Uses MD5/SHA256 frame hashes or pixel diff ratios for zero-latency change verification.
    """

    def compute_image_hash(self, image_bytes: bytes) -> str:
        """Computes SHA-256 hash of raw image payload."""
        return hashlib.sha256(image_bytes).hexdigest()

    def compare_screenshots(
        self,
        before_b64: Optional[str],
        after_b64: Optional[str],
        threshold: float = 0.02,
    ) -> VisualDiffResult:
        """
        Compares base64 encoded screenshots.
        Returns VisualDiffResult with change status and diff score.
        """
        if not before_b64 or not after_b64:
            return VisualDiffResult(has_changed=True, diff_score=1.0, details="Missing screenshot for comparison")

        if before_b64 == after_b64:
            return VisualDiffResult(has_changed=False, diff_score=0.0, details="Identical screen hash")

        hash_a = hashlib.md5(before_b64.encode("utf-8")).hexdigest()
        hash_b = hashlib.md5(after_b64.encode("utf-8")).hexdigest()

        if hash_a == hash_b:
            return VisualDiffResult(has_changed=False, diff_score=0.0, details="Identical screen payload hash")

        # Quick size comparison heuristic
        len_diff = abs(len(before_b64) - len(after_b64)) / float(max(len(before_b64), 1))
        diff_score = min(1.0, max(0.05, len_diff * 5.0))

        has_changed = diff_score >= threshold
        return VisualDiffResult(
            has_changed=has_changed,
            diff_score=diff_score,
            details=f"Screen state changed (diff_score={diff_score:.3f})",
        )
