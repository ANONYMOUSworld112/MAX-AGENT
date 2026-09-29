"""PyQt6 Task Queue widget for the CyberBlack AI-agent MAX HUD.

Displays real-time TaskQueue execution status:
- Task ID / Description
- Assigned Agent
- Lifecycle Status (QUEUED / RUNNING / DONE / FAILED)
- Elapsed Execution Time
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFrame,
)


class TaskItemWidget(QFrame):
    def __init__(
        self,
        task_id: str,
        description: str,
        agent: str,
        status: str,
        elapsed: float = 0.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.start_time = time.time() - elapsed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Task Name & ID
        self.lbl_task = QLabel(f"[{task_id[:8]}] {description[:28]}")
        self.lbl_task.setStyleSheet("color: #E2E8F0; font-weight: bold; font-family: monospace;")
        layout.addWidget(self.lbl_task, 3)

        # Agent Badge
        self.lbl_agent = QLabel(agent)
        self.lbl_agent.setStyleSheet(
            "color: #38BDF8; background-color: #0F172A; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
        )
        layout.addWidget(self.lbl_agent, 1)

        # Status Badge
        self.lbl_status = QLabel(status.upper())
        self._update_status_style(status)
        layout.addWidget(self.lbl_status, 1)

        # Elapsed Timer
        self.lbl_elapsed = QLabel(f"{elapsed:.1f}s")
        self.lbl_elapsed.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self.lbl_elapsed, 1)

        self.setStyleSheet(
            "background-color: #1E293B; border: 1px solid #334155; border-radius: 6px; margin-bottom: 2px;"
        )

    def _update_status_style(self, status: str) -> None:
        color_map = {
            "queued": "#F59E0B",
            "running": "#3B82F6",
            "done": "#10B981",
            "failed": "#EF4444",
            "cancelled": "#6B7280",
        }
        color = color_map.get(status.lower(), "#94A3B8")
        self.lbl_status.setText(status.upper())
        self.lbl_status.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 11px; padding: 2px 4px;"
        )

    def update_state(self, status: str, elapsed: Optional[float] = None) -> None:
        self._update_status_style(status)
        if elapsed is not None:
            self.lbl_elapsed.setText(f"{elapsed:.1f}s")
        else:
            cur_elapsed = time.time() - self.start_time
            self.lbl_elapsed.setText(f"{cur_elapsed:.1f}s")


class TaskListWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._task_widgets: Dict[str, tuple[QListWidgetItem, TaskItemWidget]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header Title
        title_box = QHBoxLayout()
        self.title_lbl = QLabel("SWARM TASK QUEUE")
        self.title_lbl.setStyleSheet(
            "color: #06B6D4; font-size: 13px; font-weight: 800; letter-spacing: 1px;"
        )
        title_box.addWidget(self.title_lbl)

        self.count_lbl = QLabel("0 active")
        self.count_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        title_box.addWidget(self.count_lbl, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_box)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: transparent; border: none; } "
            "QListWidget::item { margin: 2px 0px; }"
        )
        layout.addWidget(self.list_widget)

        # Ticker for elapsed time updates
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def add_or_update_task(
        self,
        task_id: str,
        description: str,
        agent: str,
        status: str,
        elapsed: float = 0.0,
    ) -> None:
        if task_id in self._task_widgets:
            _, item_widget = self._task_widgets[task_id]
            item_widget.update_state(status, elapsed)
        else:
            item = QListWidgetItem(self.list_widget)
            item_widget = TaskItemWidget(task_id, description, agent, status, elapsed)
            item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
            self._task_widgets[task_id] = (item, item_widget)

        self._refresh_count()

    def remove_task(self, task_id: str) -> None:
        if task_id in self._task_widgets:
            item, _ = self._task_widgets.pop(task_id)
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            self._refresh_count()

    def clear_finished(self) -> None:
        finished_ids = [
            tid
            for tid, (_, widget) in self._task_widgets.items()
            if widget.lbl_status.text() in ("DONE", "FAILED", "CANCELLED")
        ]
        for tid in finished_ids:
            self.remove_task(tid)

    def _refresh_count(self) -> None:
        active = sum(
            1 for _, w in self._task_widgets.values() if w.lbl_status.text() in ("QUEUED", "RUNNING")
        )
        self.count_lbl.setText(f"{active} active")

    def _tick(self) -> None:
        for _, widget in self._task_widgets.values():
            if widget.lbl_status.text() in ("QUEUED", "RUNNING"):
                widget.update_state(widget.lbl_status.text().lower())
