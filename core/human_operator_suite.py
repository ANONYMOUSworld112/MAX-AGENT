"""
MAX OS — 6 Human-Operating Capabilities Suite (Master Build Addendum).
Implements the 6 essential human computer-operating capabilities:
  1. Opportunistic Peripheral Awareness (Rogue modals, popups, cookie banner dismissal)
  2. Final Glance Before Committing (Pre-submission form diffing against intent)
  3. Confidence That Changes Behavior (High -> proceed, Med -> re-observe, Low -> halt & ask)
  4. Settle-Time by Re-Observation (Visual snapshot & hash convergence over fixed sleep)
  5. Task-Scoped Working Memory & Referential Resolution (Pronoun 'it' & entity tracking)
  6. Narrated Spoken Course-Correction (Real-time voice recovery narration)
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.command_model import ActionObject
from core.kill_switch import get_kill_switch, require_armed
from core.single_tts_queue import speak


@dataclass
class PeripheralInterference:
    found: bool
    kind: str  # "cookie_consent", "dialog_modal", "update_popup", "ad_overlay"
    dismiss_target: Optional[str] = None
    dismiss_action: Optional[ActionObject] = None
    details: str = ""


@dataclass
class FormDiffResult:
    is_consistent: bool
    discrepancies: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class SettleTimeResult:
    stabilized: bool
    iterations_waited: int
    elapsed_seconds: float
    final_hash: str


class OpportunisticPeripheralAwareness:
    """
    1. Opportunistic Peripheral Awareness.
    Inspects UI hierarchy on every observation cycle to detect and dismiss unprompted popups,
    cookie consent banners, permission prompts, and overlay dialogs without losing task context.
    """

    POPUP_DISMISS_PATTERNS = [
        r"(?:accept|agree|allow|ok|got it|continue|close|dismiss|reject all|accept all)",
        r"(?:cookies|cookie policy|privacy terms|newsletter|sign in to continue)",
    ]

    def scan_and_remedy(self, uia_elements: List[Dict[str, Any]]) -> PeripheralInterference:
        """Checks for interrupting overlays and returns remediation action if found."""
        for el in uia_elements:
            name = str(el.get("name") or el.get("text") or "").lower()
            role = str(el.get("role") or el.get("control_type") or "").lower()

            # Check for cookie consent / promo overlay
            if any(term in name for term in ("cookie", "accept all", "agree to all", "got it", "i agree", "dismiss")):
                if role in ("button", "hyperlink", "pane", ""):
                    dismiss_act = ActionObject(
                        action_id="dismiss_popup",
                        type="click",
                        target=el.get("name") or "Accept",
                        semantic_target=el.get("name") or "Accept",
                    )
                    return PeripheralInterference(
                        found=True,
                        kind="cookie_consent",
                        dismiss_target=el.get("name"),
                        dismiss_action=dismiss_act,
                        details=f"Detected interrupting overlay button: '{name}'",
                    )

            # Check for rogue modal close button
            if name in ("close", "x", "no thanks", "maybe later", "not now", "cancel"):
                if role in ("button", "image"):
                    dismiss_act = ActionObject(
                        action_id="dismiss_modal",
                        type="click",
                        target=el.get("name") or "Close",
                        semantic_target="Close Modal",
                    )
                    return PeripheralInterference(
                        found=True,
                        kind="dialog_modal",
                        dismiss_target="Close",
                        dismiss_action=dismiss_act,
                        details=f"Detected modal close target: '{name}'",
                    )

        return PeripheralInterference(found=False, kind="")


class FinalGlanceFormGuard:
    """
    2. Final Glance Before Committing.
    Diffs pre-filled form fields, recipient emails, dollar amounts, or query texts against
    original user goal before executing irreversible Tier 1/2 submissions.
    """

    def verify_commitment_intent(
        self,
        goal: str,
        action: ActionObject,
        current_field_values: Dict[str, Any],
    ) -> FormDiffResult:
        """Compares current field state with user intent."""
        goal_lower = goal.lower()
        discrepancies: List[str] = []

        # Check monetary figures (e.g. $150, 150 dollars)
        price_matches = re.findall(r"\$?(\d+(?:\.\d{2})?)", goal)
        for expected_num in price_matches:
            # If form has an amount field, verify consistency
            for k, val in current_field_values.items():
                if "amount" in k.lower() or "price" in k.lower() or "total" in k.lower():
                    if str(expected_num) not in str(val):
                        discrepancies.append(
                            f"Field '{k}' has value '{val}', which diverges from requested amount '{expected_num}'."
                        )

        # Check recipient / email
        email_matches = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", goal)
        if email_matches:
            expected_email = email_matches[0].lower()
            for k, val in current_field_values.items():
                if "to" in k.lower() or "recipient" in k.lower() or "email" in k.lower():
                    if expected_email not in str(val).lower():
                        discrepancies.append(
                            f"Recipient field '{k}' is '{val}', expected '{expected_email}'."
                        )

        is_ok = (len(discrepancies) == 0)
        return FormDiffResult(is_consistent=is_ok, discrepancies=discrepancies, confidence=1.0 if is_ok else 0.4)


class AdaptiveConfidenceBrancher:
    """
    3. Confidence That Changes Behavior.
    Translates visual element recognition and LLM confidence scores into real execution branches:
      - confidence >= 0.85: Fast proceed.
      - 0.60 <= confidence < 0.85: Settle-time re-observation and single confirmation check.
      - confidence < 0.60: Halt, narrate ambiguity, prompt user.
    """

    HIGH_THRESHOLD = 0.85
    MEDIUM_THRESHOLD = 0.60

    def evaluate_branch(self, confidence: float, action: ActionObject) -> str:
        """Returns action directive: 'EXECUTE', 'RE_OBSERVE', or 'HALT_AND_ASK'."""
        if confidence >= self.HIGH_THRESHOLD:
            return "EXECUTE"
        elif confidence >= self.MEDIUM_THRESHOLD:
            return "RE_OBSERVE"
        else:
            return "HALT_AND_ASK"


class SettleTimeReObserver:
    """
    4. Settle-Time by Re-Observation.
    Replaces brittle static time.sleep() calls by polling visual snapshot hashes and element counts
    until convergence (snapshot hash unchanged for 2 consecutive polls or timeout).
    """

    def wait_for_settlement(
        self,
        snapshot_getter: Callable[[], str | bytes | List[Dict[str, Any]]],
        max_wait_seconds: float = 3.0,
        poll_interval_seconds: float = 0.25,
    ) -> SettleTimeResult:
        """Polls until snapshot state converges."""
        start_time = time.time()
        prev_hash = ""
        stable_count = 0
        iterations = 0

        while (time.time() - start_time) < max_wait_seconds:
            iterations += 1
            raw_state = snapshot_getter()
            if isinstance(raw_state, list):
                raw_bytes = str(sorted([str(x) for x in raw_state])).encode("utf-8")
            elif isinstance(raw_state, str):
                raw_bytes = raw_state.encode("utf-8")
            else:
                raw_bytes = bytes(raw_state)

            curr_hash = hashlib.sha256(raw_bytes).hexdigest()

            if curr_hash == prev_hash:
                stable_count += 1
                if stable_count >= 2:
                    return SettleTimeResult(
                        stabilized=True,
                        iterations_waited=iterations,
                        elapsed_seconds=time.time() - start_time,
                        final_hash=curr_hash,
                    )
            else:
                stable_count = 0
                prev_hash = curr_hash

            time.sleep(poll_interval_seconds)

        return SettleTimeResult(
            stabilized=False,
            iterations_waited=iterations,
            elapsed_seconds=time.time() - start_time,
            final_hash=prev_hash,
        )


class TaskScopedReferentialMemory:
    """
    5. Task-Scoped Working Memory & Referential Resolution.
    Maintains a rolling entity state dictionary and resolves conversational referents
    like 'it', 'that', 'the price', 'the first result', or 'the total' to concrete values.
    """

    def __init__(self):
        self._entities: Dict[str, Any] = {}
        self._recent_items: List[Dict[str, Any]] = []

    def record_entity(self, key: str, value: Any) -> None:
        """Records or updates an entity in working memory."""
        self._entities[key.lower().strip()] = value

    def record_list_items(self, items: List[Dict[str, Any]]) -> None:
        """Records ordered list items (e.g. search results)."""
        self._recent_items = list(items)

    def get_entity(self, key: str, default: Any = None) -> Any:
        """Retrieves a tracked entity."""
        return self._entities.get(key.lower().strip(), default)

    def resolve_reference(self, expression: str) -> Optional[str]:
        """Resolves pronouns and ordinal references."""
        expr = expression.lower().strip()

        # Ordinal matches
        if "first" in expr or "1st" in expr:
            if self._recent_items:
                return str(self._recent_items[0].get("title") or self._recent_items[0].get("name") or self._recent_items[0])
        elif "second" in expr or "2nd" in expr:
            if len(self._recent_items) > 1:
                return str(self._recent_items[1].get("title") or self._recent_items[1].get("name") or self._recent_items[1])
        elif "last" in expr:
            if self._recent_items:
                return str(self._recent_items[-1].get("title") or self._recent_items[-1].get("name") or self._recent_items[-1])

        # Entity lookup for 'it', 'that', 'the price', 'result'
        if expr in ("it", "that", "this", "the item"):
            return str(self._entities.get("last_selected_item") or self._entities.get("target_app") or self._entities.get("result", ""))
        elif "price" in expr or "cost" in expr:
            return str(self._entities.get("price") or self._entities.get("total", ""))
        elif "result" in expr or "total" in expr:
            return str(self._entities.get("result") or self._entities.get("calculator_result", ""))

        return None

    def export_state(self) -> Dict[str, Any]:
        """Exports memory state dictionary."""
        return {
            "entities": dict(self._entities),
            "item_count": len(self._recent_items),
        }


class NarratedCourseCorrector:
    """
    6. Narrated Course-Correction.
    Speaks updates aloud through the Single TTS Queue when adapting, retrying,
    or course-correcting during autonomous computer-use operations.
    """

    def narrate_correction(self, message: str) -> None:
        """Speaks course correction message aloud."""
        speak(message)


class HumanOperatorSuite:
    """
    Integrated 6 Human-Operating Capabilities Suite.
    Composes all 6 human traits into a unified evaluation framework for UniversalExecutionLoop.
    """

    def __init__(self):
        self.peripheral = OpportunisticPeripheralAwareness()
        self.form_guard = FinalGlanceFormGuard()
        self.brancher = AdaptiveConfidenceBrancher()
        self.settle = SettleTimeReObserver()
        self.memory = TaskScopedReferentialMemory()
        self.narrator = NarratedCourseCorrector()
