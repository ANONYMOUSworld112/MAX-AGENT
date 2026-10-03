"""
Real-Time Task Progress Widget for MAX HUD (Phase 11: Task 11.1)
================================================================

Displays real-time multi-step task execution progress:
- Task ID and title/description
- Current step index and total steps (Step N of M)
- Progress bar indicator (0% - 100%)
- Worker status badge (PENDING, RUNNING, COMPLETED, FAILED)
- Verification outcome badge (PENDING, VERIFIED, FAILED, UNKNOWN)

Subscribes to EventBus for 'task.progress', 'task.created', 'task.completed',
'task.failed', and 'verification.completed' events.
Thread-safe and resilient to rapid event bursts.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Enable headless PyQt6 if running in test/CI environment without a display
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.contracts import EventEnvelope
from core.events import EventBus

logger = logging.getLogger("max.ui.task_progress")


def _get_or_create_qapp() -> QApplication:
    """Ensure a QApplication instance exists before creating any QWidget."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if sys.argv else ["max-hud"])
    return app


class TaskProgressItemWidget(QFrame):
    """Visual row for a single task's multi-step execution."""

    def __init__(
        self,
        task_id: str,
        description: str,
        step_index: int = 1,
        total_steps: int = 1,
        step_name: str = "Initializing",
        worker_status: str = "RUNNING",
        verification_status: str = "PENDING",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.description = description
        self.step_index = step_index
        self.total_steps = max(1, total_steps)
        self.step_name = step_name
        self.worker_status = worker_status
        self.verification_status = verification_status
        self.start_time = time.time()

        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName(f"task_item_{self.task_id}")
        self.setStyleSheet(
            "QFrame {"
            "  background-color: #1E293B;"
            "  border: 1px solid #334155;"
            "  border-radius: 8px;"
            "  padding: 6px;"
            "  margin-bottom: 4px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Top row: Task Title + Worker Badge + Verification Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_title = QLabel(f"[{self.task_id[:8]}] {self.description[:36]}")
        self.lbl_title.setStyleSheet("color: #F8FAFC; font-weight: 700; font-family: monospace; font-size: 12px;")
        top_row.addWidget(self.lbl_title, 3)

        self.lbl_worker = QLabel(self.worker_status.upper())
        self._apply_worker_badge(self.worker_status)
        top_row.addWidget(self.lbl_worker, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.lbl_verification = QLabel(self.verification_status.upper())
        self._apply_verification_badge(self.verification_status)
        top_row.addWidget(self.lbl_verification, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_row)

        # Middle row: Progress Bar + Step Count
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  background-color: #0F172A;"
            "  border: 1px solid #334155;"
            "  border-radius: 6px;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06B6D4, stop:1 #38BDF8);"
            "  border-radius: 5px;"
            "}"
        )
        mid_row.addWidget(self.progress_bar, 4)

        self.lbl_step_counter = QLabel(f"Step {self.step_index}/{self.total_steps}")
        self.lbl_step_counter.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 11px;")
        mid_row.addWidget(self.lbl_step_counter, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(mid_row)

        # Bottom row: Current Step Description
        self.lbl_step_desc = QLabel(f"Executing: {self.step_name}")
        self.lbl_step_desc.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        layout.addWidget(self.lbl_step_desc)

        self._update_progress_bar()

    def _apply_worker_badge(self, status: str) -> None:
        colors = {
            "pending": ("#F59E0B", "#78350F"),
            "running": ("#38BDF8", "#0C4A6E"),
            "completed": ("#34D399", "#064E3B"),
            "done": ("#34D399", "#064E3B"),
            "failed": ("#F87171", "#7F1D1D"),
            "cancelled": ("#94A3B8", "#1E293B"),
        }
        fg, bg = colors.get(status.lower(), ("#94A3B8", "#1E293B"))
        self.lbl_worker.setText(status.upper())
        self.lbl_worker.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border: 1px solid {fg}; "
            f"border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )

    def _apply_verification_badge(self, outcome: str) -> None:
        colors = {
            "verified": ("#10B981", "#064E3B"),
            "failed": ("#EF4444", "#7F1D1D"),
            "unknown": ("#F59E0B", "#78350F"),
            "pending": ("#64748B", "#0F172A"),
            "not_applicable": ("#94A3B8", "#1E293B"),
        }
        fg, bg = colors.get(outcome.lower(), ("#94A3B8", "#1E293B"))
        self.lbl_verification.setText(outcome.upper())
        self.lbl_verification.setStyleSheet(
            f"color: {fg}; background-color: {bg}; border: 1px solid {fg}; "
            f"border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )

    def _update_progress_bar(self) -> None:
        pct = int((self.step_index / max(1, self.total_steps)) * 100)
        pct = max(0, min(100, pct))
        self.progress_bar.setValue(pct)
        self.lbl_step_counter.setText(f"Step {self.step_index}/{self.total_steps} ({pct}%)")

    def update_state(
        self,
        step_index: int,
        total_steps: int,
        step_name: Optional[str] = None,
        worker_status: Optional[str] = None,
        verification_status: Optional[str] = None,
    ) -> None:
        """Update progress metrics and re-render visual components."""
        self.step_index = step_index
        self.total_steps = max(1, total_steps)
        if step_name is not None:
            self.step_name = step_name
            self.lbl_step_desc.setText(f"Executing: {self.step_name}")
        if worker_status is not None:
            self.worker_status = worker_status
            self._apply_worker_badge(worker_status)
        if verification_status is not None:
            self.verification_status = verification_status
            self._apply_verification_badge(verification_status)

        self._update_progress_bar()

    def to_dict(self) -> dict[str, Any]:
        pct = int((self.step_index / max(1, self.total_steps)) * 100)
        return {
            "task_id": self.task_id,
            "description": self.description,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "step_name": self.step_name,
            "worker_status": self.worker_status,
            "verification_status": self.verification_status,
            "progress_pct": max(0, min(100, pct)),
        }


class _ProgressSignalBridge(QObject):
    """Internal bridge to emit signals safely to the Qt event thread."""
    progress_event = pyqtSignal(dict)


class TaskProgressWidget(QWidget):
    """
    Main HUD component for real-time task progress monitoring.

    Can be embedded in the CyberBlack HUD window and receives events
    from the EventBus or direct API invocations.
    """

    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QWidget] = None) -> None:
        _get_or_create_qapp()
        super().__init__(parent)

        self._task_items: dict[str, TaskProgressItemWidget] = {}
        self._lock = threading.Lock()
        self._bridge = _ProgressSignalBridge()
        self._bridge.progress_event.connect(self._handle_dispatched_event)

        self._init_ui()

        if event_bus is not None:
            self.subscribe_to_event_bus(event_bus)

    def _init_ui(self) -> None:
        self.setStyleSheet("background-color: #07090F; border: none;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel("TASK EXECUTION PROGRESS")
        self.title_label.setStyleSheet(
            "color: #06B6D4; font-size: 13px; font-weight: 800; letter-spacing: 1.5px;"
        )
        header_layout.addWidget(self.title_label)

        self.count_badge = QLabel("0 active")
        self.count_badge.setStyleSheet(
            "color: #94A3B8; background-color: #0F172A; border: 1px solid #334155; "
            "border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
        )
        header_layout.addWidget(self.count_badge, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(header_layout)

        # Scrollable Task Items Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")

        self.items_container = QWidget()
        self.items_container.setStyleSheet("background-color: transparent;")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(6)
        self.items_layout.addStretch()

        self.scroll_area.setWidget(self.items_container)
        main_layout.addWidget(self.scroll_area)

    def subscribe_to_event_bus(self, event_bus: EventBus) -> None:
        """Register handlers for all relevant lifecycle events on the bus."""
        event_bus.subscribe("task.progress", self.on_event)
        event_bus.subscribe("task.created", self.on_event)
        event_bus.subscribe("task.completed", self.on_event)
        event_bus.subscribe("task.failed", self.on_event)
        event_bus.subscribe("verification.completed", self.on_event)
        event_bus.subscribe("action.executed", self.on_event)

    def on_event(self, envelope: EventEnvelope) -> None:
        """Entrypoint for EventBus subscriber; marshals payload to Qt signal."""
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        data = {
            "event_type": envelope.event_type,
            "correlation_id": envelope.correlation_id or payload.get("task_id", ""),
            "actor": envelope.actor,
            "payload": payload,
        }
        self._bridge.progress_event.emit(data)

    def _handle_dispatched_event(self, data: dict[str, Any]) -> None:
        """Safely handled on Qt thread via signal bridge."""
        event_type = data.get("event_type", "")
        task_id = data.get("correlation_id", "")
        payload = data.get("payload", {})

        if not task_id:
            task_id = payload.get("task_id", "")
        if not task_id:
            return

        if event_type == "task.progress":
            step_idx = payload.get("step_index", 1)
            total = payload.get("total_steps", 1)
            step_name = payload.get("step_name") or payload.get("description", "")
            worker = payload.get("worker_status") or payload.get("status", "RUNNING")
            verif = payload.get("verification_status", "PENDING")
            desc = payload.get("task_description", f"Task {task_id[:8]}")

            self.update_task_progress(
                task_id=task_id,
                step_index=step_idx,
                total_steps=total,
                step_name=step_name,
                worker_status=worker,
                verification_status=verif,
                description=desc,
            )

        elif event_type == "task.created":
            desc = payload.get("description") or payload.get("intent", {}).get("action", f"Task {task_id[:8]}")
            self.update_task_progress(
                task_id=task_id,
                step_index=0,
                total_steps=payload.get("total_steps", 1),
                step_name="Created",
                worker_status="PENDING",
                verification_status="PENDING",
                description=str(desc),
            )

        elif event_type in ("task.completed", "task.failed"):
            status = "COMPLETED" if event_type == "task.completed" else "FAILED"
            verif = payload.get("verification_status", "VERIFIED" if status == "COMPLETED" else "FAILED")
            with self._lock:
                item = self._task_items.get(task_id)
                if item:
                    item.update_state(
                        step_index=item.total_steps,
                        total_steps=item.total_steps,
                        step_name="Done" if status == "COMPLETED" else "Execution Failed",
                        worker_status=status,
                        verification_status=verif,
                    )
            self._refresh_count()

        elif event_type == "verification.completed":
            verif_outcome = payload.get("outcome") or payload.get("status", "VERIFIED")
            with self._lock:
                item = self._task_items.get(task_id)
                if item:
                    item.update_state(
                        step_index=item.step_index,
                        total_steps=item.total_steps,
                        verification_status=verif_outcome,
                    )

    def update_task_progress(
        self,
        task_id: str,
        step_index: int,
        total_steps: int,
        step_name: str = "",
        worker_status: str = "RUNNING",
        verification_status: str = "PENDING",
        description: str = "",
    ) -> TaskProgressItemWidget:
        """Add or update a task item widget directly."""
        with self._lock:
            if task_id in self._task_items:
                item = self._task_items[task_id]
                item.update_state(
                    step_index=step_index,
                    total_steps=total_steps,
                    step_name=step_name,
                    worker_status=worker_status,
                    verification_status=verification_status,
                )
            else:
                desc = description or f"Task {task_id[:8]}"
                item = TaskProgressItemWidget(
                    task_id=task_id,
                    description=desc,
                    step_index=step_index,
                    total_steps=total_steps,
                    step_name=step_name,
                    worker_status=worker_status,
                    verification_status=verification_status,
                    parent=self.items_container,
                )
                # Insert before the stretch
                self.items_layout.insertWidget(self.items_layout.count() - 1, item)
                self._task_items[task_id] = item

        self._refresh_count()
        return item

    def get_task_progress(self, task_id: str) -> Optional[dict[str, Any]]:
        """Return the dictionary representation of task progress for testing/inspection."""
        with self._lock:
            item = self._task_items.get(task_id)
            return item.to_dict() if item else None

    def get_active_tasks(self) -> list[str]:
        """Return task IDs of currently active (running or pending) tasks."""
        with self._lock:
            return [
                tid
                for tid, item in self._task_items.items()
                if item.worker_status.upper() in ("PENDING", "RUNNING")
            ]

    def clear_finished(self) -> int:
        """Remove completed or failed tasks from the widget."""
        cleared = 0
        with self._lock:
            finished = [
                tid
                for tid, item in self._task_items.items()
                if item.worker_status.upper() in ("COMPLETED", "DONE", "FAILED", "CANCELLED")
            ]
            for tid in finished:
                item = self._task_items.pop(tid)
                self.items_layout.removeWidget(item)
                item.deleteLater()
                cleared += 1

        self._refresh_count()
        return cleared

    def count(self) -> int:
        """Return total number of tracked task items."""
        with self._lock:
            return len(self._task_items)

    def _refresh_count(self) -> None:
        active_count = len(self.get_active_tasks())
        self.count_badge.setText(f"{active_count} active")
