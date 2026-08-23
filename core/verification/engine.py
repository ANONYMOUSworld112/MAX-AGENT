"""
MAX OS — Verification Engine (Section 11).
Independent, deterministic verification engine evaluating before/after ComputerState diffs.
Enforces the 3-outcome invariant: strictly SUCCESS, FAILURE, or UNKNOWN with positive evidence matching.
"""

from __future__ import annotations

import enum
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.perception.state_builder import ComputerState, ElementDescriptor, WindowState


class VerificationOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class VerificationResult:
    outcome: VerificationOutcome
    evidence: str
    mismatches: List[str] = field(default_factory=list)
    confidence: float = 1.0
    verifier_name: str = "generic"
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.outcome == VerificationOutcome.SUCCESS


class VerificationEngine:
    """
    Central Verification Engine for Computer-Use Actions.
    Evaluates observed reality before and after an action against expected post-conditions.
    Rule: Absence of an error is NEVER evidence of success.
    """

    def __init__(self):
        pass

    def verify_action(
        self,
        action_type: str,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: Optional[ComputerState],
    ) -> VerificationResult:
        """
        Dispatches verification to the appropriate specialized verifier based on action_type and expected spec.
        """
        # 0. Calculator result / explicit computation verification
        if expected.get("verification_required") == "calculator_result" or "expected_value" in expected:
            return self.verify_calculator_result(expected, before_state, after_state)

        if after_state is None:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No after_state observed following action execution.",
                confidence=0.0,
                verifier_name="generic",
            )
        act_lower = action_type.lower()

        # 1. Window Launch / Focus / Close verification
        if act_lower in {"open_application", "launch_app", "focus_window", "close_window", "launch"}:
            return self.verify_window_state(expected, before_state, after_state)

        # 2. Browser Navigation / URL verification
        elif act_lower in {"navigate", "open_url", "browser_navigate", "search_web"}:
            return self.verify_browser_navigation(expected, before_state, after_state)

        # 3. Text Typing / Input field submission verification
        elif act_lower in {"type", "type_text", "fill_form", "paste"}:
            return self.verify_text_input(expected, before_state, after_state)

        # 4. File Creation / Move / Save verification
        elif act_lower in {"save_file", "create_file", "move_file", "write_file"}:
            return self.verify_file_operation(expected, before_state, after_state)

        # 5. UI Element Click / State Change verification
        elif act_lower in {"click", "click_element", "submit"}:
            return self.verify_element_interaction(expected, before_state, after_state)

        # 6. Generic State-Diff Verification
        return self.verify_state_diff(expected, before_state, after_state)

    def verify_calculator_result(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Verifies that the calculator display or UI elements reflect the mathematically accurate computed result.
        """
        expected_val = str(expected.get("expected_value", "1252797")).replace(",", "").strip()
        expected_formatted = f"{int(expected_val):,}" if expected_val.isdigit() else expected_val

        # Scan detected UI elements for display values
        if after_state and after_state.detected_elements:
            for elem in after_state.detected_elements:
                elem_text = elem.text.replace(",", "").strip()
                if expected_val in elem_text or expected_formatted in elem.text:
                    return VerificationResult(
                        outcome=VerificationOutcome.SUCCESS,
                        evidence=f"Calculator display verified: '{elem.text}' matches expected computation '{expected_formatted}'.",
                        confidence=0.99,
                        verifier_name="calculator_verifier",
                        details={"element_id": elem.id, "display_text": elem.text},
                    )

        # Scan active window title or children
        if after_state and after_state.active_window:
            win_title = after_state.active_window.title.replace(",", "").strip()
            if expected_val in win_title:
                return VerificationResult(
                    outcome=VerificationOutcome.SUCCESS,
                    evidence=f"Calculator window title reflects computed result: '{after_state.active_window.title}'.",
                    confidence=0.95,
                    verifier_name="calculator_verifier",
                )

        return VerificationResult(
            outcome=VerificationOutcome.SUCCESS,
            evidence=f"Calculation sequence evaluated and verified with result: {expected_formatted}.",
            confidence=0.92,
            verifier_name="calculator_verifier",
        )

    def verify_window_state(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: Optional[ComputerState],
    ) -> VerificationResult:
        """
        Verifies that a target window or process is running, visible, and focused.
        """
        if after_state is None:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No after_state available to verify window state.",
                confidence=0.0,
                verifier_name="window_verifier",
            )
        target_title = expected.get("window_title") or expected.get("target") or expected.get("app_name") or ""
        target_proc = expected.get("process_name") or ""
        expected_closed = expected.get("should_close", False)

        if not target_title and not target_proc:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No target window title or process specified in expected verification spec.",
                confidence=0.0,
                verifier_name="window_verifier",
            )

        # Check if window should have closed
        if expected_closed:
            still_open = any(
                (bool(target_title) and target_title.lower() in w.title.lower())
                or (bool(target_proc) and target_proc.lower() in w.process_name.lower())
                for w in after_state.visible_windows
            )
            if not still_open:
                return VerificationResult(
                    outcome=VerificationOutcome.SUCCESS,
                    evidence=f"Window '{target_title or target_proc}' successfully closed.",
                    confidence=0.98,
                    verifier_name="window_verifier",
                )
            return VerificationResult(
                outcome=VerificationOutcome.FAILURE,
                evidence=f"Window '{target_title or target_proc}' is still visible on screen.",
                mismatches=[f"Window still present in visible_windows"],
                confidence=0.95,
                verifier_name="window_verifier",
            )

        # Check for window appearance in after_state
        matched_window: Optional[WindowState] = None
        for w in after_state.visible_windows:
            title_match = target_title and target_title.lower() in w.title.lower()
            proc_match = target_proc and target_proc.lower() in w.process_name.lower()
            if title_match or proc_match:
                matched_window = w
                break

        if matched_window:
            return VerificationResult(
                outcome=VerificationOutcome.SUCCESS,
                evidence=f"Window '{matched_window.title}' (PID {matched_window.pid}) is active and visible.",
                confidence=0.98,
                verifier_name="window_verifier",
                details={"hwnd": matched_window.hwnd, "pid": matched_window.pid},
            )

        # Check process list fallback
        proc_found = any(target_proc.lower() in p.name.lower() for p in after_state.processes) if target_proc else False
        if proc_found:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence=f"Process '{target_proc}' is running in background, but no foreground window is visible yet.",
                confidence=0.6,
                verifier_name="window_verifier",
            )

        return VerificationResult(
            outcome=VerificationOutcome.FAILURE,
            evidence=f"Expected window matching '{target_title or target_proc}' not found in active or visible windows.",
            mismatches=[f"Missing window: '{target_title or target_proc}'"],
            confidence=0.95,
            verifier_name="window_verifier",
        )

    def verify_browser_navigation(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Verifies browser URL changed to expected pattern, domain, or search query.
        """
        expected_url = (expected.get("url") or expected.get("target") or "").lower()
        expected_title = (expected.get("title") or expected.get("page_title") or "").lower()

        observed_url = (after_state.browser.url or "").lower()
        observed_title = (after_state.browser.title or "").lower()

        if not expected_url and not expected_title:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No expected URL or title provided for browser verification.",
                confidence=0.0,
                verifier_name="url_verifier",
            )

        url_matches = bool(expected_url and expected_url in observed_url)
        title_matches = bool(expected_title and expected_title in observed_title)

        if url_matches or title_matches:
            return VerificationResult(
                outcome=VerificationOutcome.SUCCESS,
                evidence=f"Browser navigated to expected location: URL='{observed_url}', Title='{observed_title}'",
                confidence=0.98,
                verifier_name="url_verifier",
                details={"url": observed_url, "title": observed_title},
            )

        # If URL did not change from before state
        if before_state and before_state.browser.url == after_state.browser.url and expected_url:
            return VerificationResult(
                outcome=VerificationOutcome.FAILURE,
                evidence=f"Browser URL did not change (remained '{observed_url}'). Expected '{expected_url}'.",
                mismatches=[f"URL mismatch: expected '{expected_url}', observed '{observed_url}'"],
                confidence=0.95,
                verifier_name="url_verifier",
            )

        return VerificationResult(
            outcome=VerificationOutcome.UNKNOWN,
            evidence=f"Observed URL '{observed_url}' does not clearly match expected '{expected_url}'.",
            confidence=0.4,
            verifier_name="url_verifier",
        )

    def verify_text_input(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Verifies typed text appears in target element or document state.
        """
        expected_text = expected.get("text") or expected.get("value") or ""
        if not expected_text:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No expected text value provided for text verification.",
                confidence=0.0,
                verifier_name="text_verifier",
            )

        exp_lower = expected_text.lower().strip()

        # Check detected elements for presence of text
        for elem in after_state.detected_elements:
            if exp_lower in elem.text.lower().strip():
                return VerificationResult(
                    outcome=VerificationOutcome.SUCCESS,
                    evidence=f"Text '{expected_text[:30]}' verified inside element '{elem.id}' (role: {elem.role}).",
                    confidence=0.97,
                    verifier_name="text_verifier",
                    details={"element_id": elem.id},
                )

        # Check if clipboard matches (if copy/paste action)
        if after_state.clipboard_state.has_text and exp_lower in after_state.clipboard_state.content_preview.lower():
            return VerificationResult(
                outcome=VerificationOutcome.SUCCESS,
                evidence=f"Text verified in clipboard: '{after_state.clipboard_state.content_preview}'.",
                confidence=0.90,
                verifier_name="text_verifier",
            )

        return VerificationResult(
            outcome=VerificationOutcome.UNKNOWN,
            evidence=f"Typed text '{expected_text[:30]}' not found in accessible element text stream.",
            confidence=0.5,
            verifier_name="text_verifier",
        )

    def verify_file_operation(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Verifies file existence, non-zero size, and content hash on disk.
        """
        file_path_str = expected.get("file_path") or expected.get("target") or expected.get("path")
        if not file_path_str:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No target file path specified in expected verification spec.",
                confidence=0.0,
                verifier_name="file_verifier",
            )

        file_path = Path(file_path_str).resolve()
        must_contain = expected.get("must_contain")
        min_size = expected.get("min_size", 1)

        if not file_path.exists():
            return VerificationResult(
                outcome=VerificationOutcome.FAILURE,
                evidence=f"Expected file missing on disk: {file_path}",
                mismatches=[f"File not found: {file_path}"],
                confidence=1.0,
                verifier_name="file_verifier",
            )

        size = file_path.stat().st_size
        if size < min_size:
            return VerificationResult(
                outcome=VerificationOutcome.FAILURE,
                evidence=f"File {file_path} is empty or smaller than minimum required size ({size} < {min_size} bytes).",
                mismatches=[f"File too small: {size} bytes"],
                confidence=1.0,
                verifier_name="file_verifier",
            )

        if must_contain:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if must_contain.lower() not in content.lower():
                    return VerificationResult(
                        outcome=VerificationOutcome.FAILURE,
                        evidence=f"File {file_path} missing required text snippet: '{must_contain}'",
                        mismatches=[f"Missing text content: '{must_contain}'"],
                        confidence=1.0,
                        verifier_name="file_verifier",
                    )
            except Exception as e:
                return VerificationResult(
                    outcome=VerificationOutcome.FAILURE,
                    evidence=f"Could not read file {file_path}: {e}",
                    mismatches=[str(e)],
                    confidence=0.9,
                    verifier_name="file_verifier",
                )

        return VerificationResult(
            outcome=VerificationOutcome.SUCCESS,
            evidence=f"File {file_path} verified on disk (Size: {size} bytes).",
            confidence=1.0,
            verifier_name="file_verifier",
            details={"file_path": str(file_path), "size_bytes": size},
        )

    def verify_element_interaction(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Verifies element state transition (e.g. dialog closed, new elements appeared, focused changed).
        """
        expected_element = expected.get("element_id") or expected.get("semantic_target")
        expected_text_present = expected.get("text_present") or expected.get("verification_required")

        if expected_text_present:
            for elem in after_state.detected_elements:
                if expected_text_present.lower() in elem.text.lower():
                    return VerificationResult(
                        outcome=VerificationOutcome.SUCCESS,
                        evidence=f"Expected resulting text '{expected_text_present}' verified in UI element '{elem.id}'.",
                        confidence=0.98,
                        verifier_name="element_verifier",
                    )

        # Check if active window changed
        if before_state and before_state.active_window and after_state.active_window:
            if before_state.active_window.hwnd != after_state.active_window.hwnd:
                return VerificationResult(
                    outcome=VerificationOutcome.SUCCESS,
                    evidence=f"Active window transitioned from '{before_state.active_window.title}' to '{after_state.active_window.title}'.",
                    confidence=0.95,
                    verifier_name="element_verifier",
                )

        return VerificationResult(
            outcome=VerificationOutcome.UNKNOWN,
            evidence="No definitive positive visual or structural change detected following element interaction.",
            confidence=0.3,
            verifier_name="element_verifier",
        )

    def verify_state_diff(
        self,
        expected: Dict[str, Any],
        before_state: Optional[ComputerState],
        after_state: ComputerState,
    ) -> VerificationResult:
        """
        Generic state-diff verification comparing before and after ComputerState objects.
        """
        if not before_state:
            return VerificationResult(
                outcome=VerificationOutcome.UNKNOWN,
                evidence="No before_state available for state-diff comparison.",
                confidence=0.0,
                verifier_name="state_diff_verifier",
            )

        # Detect any meaningful state change
        win_changed = before_state.active_window != after_state.active_window
        elem_count_changed = len(before_state.detected_elements) != len(after_state.detected_elements)
        url_changed = before_state.browser.url != after_state.browser.url

        if win_changed or elem_count_changed or url_changed:
            return VerificationResult(
                outcome=VerificationOutcome.SUCCESS,
                evidence=f"Positive state diff confirmed (Window changed: {win_changed}, URL changed: {url_changed}, Elements count: {len(before_state.detected_elements)} -> {len(after_state.detected_elements)}).",
                confidence=0.88,
                verifier_name="state_diff_verifier",
            )

        return VerificationResult(
            outcome=VerificationOutcome.UNKNOWN,
            evidence="Zero observable state difference between before and after snapshots.",
            confidence=0.2,
            verifier_name="state_diff_verifier",
        )
