"""
Execution screen — realtime task progress and log viewer.

Shows:
- Overall progress bar
- Per-task status list (icon + name + status + duration)
- Live log panel (auto-scroll)
- Cancel button
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.orchestrator import Orchestrator
from app.ui.theme import (
    ACCENT,
    BG_SECONDARY,
    ERROR,
    FONT_MONO,
    FONT_SIZE_SM,
    INFO,
    STATUS_COLORS,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARNING,
)


class ExecutionScreen(QWidget):
    """Provisioning execution view with live progress."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.orchestrator: Orchestrator | None = None
        self.task_labels: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Provisioning")
        title.setObjectName("titleLabel")
        header.addWidget(title)

        header.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(f"background: {ERROR}; color: white; font-weight: 600;")
        self.cancel_btn.clicked.connect(self._cancel)
        header.addWidget(self.cancel_btn)

        layout.addLayout(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Preparing...")
        self.progress_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        layout.addWidget(self.progress_label)

        # Splitter: task list (top) + log (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Task status list
        task_scroll = QScrollArea()
        task_scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setSpacing(4)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        task_scroll.setWidget(self.task_container)
        splitter.addWidget(task_scroll)

        # Log viewer
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logViewer")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        splitter.addWidget(self.log_view)

        splitter.setSizes([300, 200])
        layout.addWidget(splitter, stretch=1)

    def on_enter(self):
        """Start the provisioning orchestrator."""
        self.log_view.clear()
        self.task_labels.clear()
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)

        # Clear task list
        while self.task_layout.count():
            child = self.task_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        profile = self.mw.selected_profile
        if not profile:
            return

        # Pre-populate task rows
        for task in profile.get_enabled_tasks():
            if not self.mw.task_overrides.get(task.id, True):
                continue
            row = self._build_task_status_row(task.id, task.name)
            self.task_layout.addWidget(row)

        # Total for progress bar
        active_count = sum(1 for t in profile.get_enabled_tasks()
                          if self.mw.task_overrides.get(t.id, True))
        self.progress_bar.setMaximum(active_count)

        # Create and start orchestrator
        self.orchestrator = Orchestrator(
            profile=profile,
            device=self.mw.device_metadata,
            task_overrides=self.mw.task_overrides,
            repo=self.mw.repo,
            profile_loader=self.mw.profile_loader,
            webhook_sender=self.mw.webhook_sender,
        )

        # Connect signals
        self.orchestrator.task_started.connect(self._on_task_started)
        self.orchestrator.task_finished.connect(self._on_task_finished)
        self.orchestrator.log_line.connect(self._on_log)
        self.orchestrator.progress_updated.connect(self._on_progress)
        self.orchestrator.run_finished.connect(self._on_finished)

        self.orchestrator.start()

    def _build_task_status_row(self, task_id: str, task_name: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet(f"background: {BG_SECONDARY}; border-radius: 4px; padding: 6px 10px;")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 10, 6)

        status_dot = QLabel("○")
        status_dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        status_dot.setFixedWidth(20)
        layout.addWidget(status_dot)

        name = QLabel(task_name)
        name.setStyleSheet("font-size: 13px;")
        layout.addWidget(name, stretch=1)

        status_label = QLabel("pending")
        status_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;"
        )
        layout.addWidget(status_label)

        duration = QLabel("")
        duration.setStyleSheet(f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SM}px;")
        duration.setFixedWidth(60)
        duration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(duration)

        # Store references for updates
        self.task_labels[task_id] = {
            "dot": status_dot,
            "status": status_label,
            "duration": duration,
            "row": row,
        }

        return row

    def _on_task_started(self, task_id: str, task_name: str):
        refs = self.task_labels.get(task_id)
        if refs:
            refs["dot"].setText("◉")
            refs["dot"].setStyleSheet(f"color: {INFO}; font-size: 12px;")
            refs["status"].setText("running")
            refs["status"].setStyleSheet(
                f"color: {INFO}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;"
            )

    def _on_task_finished(self, task_id: str, status: str, duration_ms: int, error: str):
        refs = self.task_labels.get(task_id)
        if not refs:
            return

        icon_map = {"success": "✓", "failed": "✗", "skipped": "⊘", "cancelled": "—"}
        color = STATUS_COLORS.get(status, TEXT_MUTED)

        refs["dot"].setText(icon_map.get(status, "?"))
        refs["dot"].setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
        refs["status"].setText(status)
        refs["status"].setStyleSheet(
            f"color: {color}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;"
        )

        if duration_ms > 0:
            secs = duration_ms / 1000
            refs["duration"].setText(f"{secs:.1f}s")

    def _on_log(self, message: str):
        self.log_view.appendPlainText(message)

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Task {current}/{total}")

    def _on_finished(self, run_id: str, status: str):
        self.cancel_btn.setEnabled(False)
        self.mw.last_run_id = run_id

        color = STATUS_COLORS.get(status, TEXT_MUTED)
        self.progress_label.setText(f"Finished: {status}")
        self.progress_label.setStyleSheet(f"color: {color}; font-size: {FONT_SIZE_SM}px; font-weight: 600;")

        # Auto-navigate to summary after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.mw.navigate_to(self.mw.SUMMARY))

    def _cancel(self):
        if self.orchestrator:
            self.orchestrator.cancel()
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("Cancelling...")
