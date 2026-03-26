"""
Task review screen — checklist of tasks before execution.

IT Support can enable/disable individual tasks before starting.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    BG_SECONDARY,
    BORDER,
    FONT_MONO,
    FONT_SIZE_SM,
    TEXT_MUTED,
    TEXT_SECONDARY,
)


class ReviewScreen(QWidget):
    """Task review with toggleable checklist."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Review Tasks")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.info_label = QLabel("")
        self.info_label.setObjectName("subtitleLabel")
        layout.addWidget(self.info_label)

        # Task list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(6)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, stretch=1)

        # Navigation
        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(lambda: self.mw.navigate_to(self.mw.METADATA))
        nav.addWidget(back_btn)

        nav.addStretch()

        self.start_btn = QPushButton("▶ Start Provisioning")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start)
        nav.addWidget(self.start_btn)

        layout.addLayout(nav)

    def on_enter(self):
        """Populate task list from selected profile."""
        # Clear
        self.checkboxes.clear()
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        profile = self.mw.selected_profile
        device = self.mw.device_metadata
        if not profile:
            return

        self.info_label.setText(
            f"Profile: {profile.name}  |  Hostname: {device.hostname}  |  "
            f"Asset: {device.asset_tag}"
        )

        for task in profile.get_enabled_tasks():
            row = self._build_task_row(task)
            self.list_layout.addWidget(row)

    def _build_task_row(self, task) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background: {BG_SECONDARY}; border-radius: 6px; padding: 8px 12px;"
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)

        cb = QCheckBox()
        cb.setChecked(True)
        self.checkboxes[task.id] = cb
        layout.addWidget(cb)

        name = QLabel(task.name)
        name.setStyleSheet("font-weight: 500;")
        layout.addWidget(name, stretch=1)

        type_badge = QLabel(task.type)
        type_badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px; "
            f"background: {BORDER}; padding: 2px 8px; border-radius: 4px;"
        )
        layout.addWidget(type_badge)

        timeout_label = QLabel(f"{task.timeout}s")
        timeout_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        timeout_label.setFixedWidth(40)
        timeout_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(timeout_label)

        return row

    def _start(self):
        """Collect overrides and proceed to execution."""
        self.mw.task_overrides = {
            task_id: cb.isChecked() for task_id, cb in self.checkboxes.items()
        }
        self.mw.navigate_to(self.mw.EXECUTION)
