"""
Home screen — dashboard with kit status, recent runs, and start button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    ACCENT,
    BG_SECONDARY,
    BORDER,
    ERROR,
    FONT_MONO,
    FONT_SIZE_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


class HomeScreen(QWidget):
    """Dashboard — entry point for the provisioning workflow."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # Title
        title = QLabel("Dashboard")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Kit status card
        kit_card = self._build_kit_card()
        layout.addWidget(kit_card)

        # Start button
        start_btn = QPushButton("Start New Provisioning")
        start_btn.setObjectName("primaryButton")
        start_btn.setFixedHeight(48)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.clicked.connect(self._start_new_provisioning)
        layout.addWidget(start_btn)

        # Tools section
        tools = QWidget()
        tools_layout = QGridLayout(tools)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(10)

        profile_mgr = QPushButton("Manage Profiles")
        profile_mgr.clicked.connect(lambda: self.mw.navigate_to(self.mw.PROFILE_MANAGER))
        tools_layout.addWidget(profile_mgr, 0, 0)

        package_mgr = QPushButton("Package Sources")
        package_mgr.clicked.connect(lambda: self.mw.navigate_to(self.mw.PACKAGE_MANAGER))
        tools_layout.addWidget(package_mgr, 0, 1)

        webhook_cfg = QPushButton("Webhook Settings")
        webhook_cfg.clicked.connect(lambda: self.mw.navigate_to(self.mw.WEBHOOK_SETTINGS))
        tools_layout.addWidget(webhook_cfg, 0, 2)

        layout.addWidget(tools)

        # Recent runs section
        section = QLabel("Recent Runs")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

        # Scroll area for run history
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.runs_container = QWidget()
        self.runs_layout = QVBoxLayout(self.runs_container)
        self.runs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.runs_layout.setSpacing(8)
        scroll.setWidget(self.runs_container)
        layout.addWidget(scroll, stretch=1)

    def on_enter(self):
        """Called when screen becomes visible — refresh data."""
        self._refresh_runs()

    def _build_kit_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QWidget#card {{ background: {BG_SECONDARY}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; padding: 16px; }}"
        )

        layout = QVBoxLayout(card)
        kit = self.mw.kit

        if kit:
            name_label = QLabel(f"Provisioning Kit: {kit.kit_name}")
            name_label.setStyleSheet(f"color: {ACCENT}; font-weight: 600; font-size: 15px;")
            layout.addWidget(name_label)

            details = QLabel(
                f"Drive {kit.drive_letter}:  ·  Version {kit.kit_version}  ·  "
                f"{len(kit.manifest.get('packages', []))} packages"
            )
            details.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(details)
        else:
            label = QLabel("No provisioning kit detected — using bundled profiles only")
            label.setStyleSheet(f"color: {WARNING};")
            layout.addWidget(label)

            hint = QLabel("Connect your SSD provisioning kit and restart to load external packages")
            hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(hint)

        return card

    def _refresh_runs(self):
        """Load and display recent runs from DB."""
        # Clear existing
        while self.runs_layout.count():
            child = self.runs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        runs = self.mw.repo.get_recent_runs(limit=10)

        if not runs:
            empty = QLabel("No provisioning runs yet")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; padding: 20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.runs_layout.addWidget(empty)
            return

        for run in runs:
            row = self._build_run_row(run)
            self.runs_layout.addWidget(row)

    def _start_new_provisioning(self):
        """Start flow; if no profile exists, send user to profile manager first."""
        profiles = self.mw.profile_loader.load_profiles()
        if profiles:
            self.mw.navigate_to(self.mw.PROFILE)
            return
        QMessageBox.information(
            self,
            "Profile Belum Ada",
            "Belum ada profile provisioning. Silakan buat profile dulu.",
        )
        self.mw.navigate_to(self.mw.PROFILE_MANAGER)

    def _build_run_row(self, run: dict) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background: {BG_SECONDARY}; border-radius: 6px; padding: 10px 14px;"
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)

        # Status dot
        status = run.get("status", "?")
        color_map = {
            "completed": ACCENT, "partial": WARNING,
            "failed": ERROR, "running": "#4dabf7", "cancelled": TEXT_MUTED,
        }
        dot_color = color_map.get(status, TEXT_MUTED)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
        dot.setFixedWidth(20)
        layout.addWidget(dot)

        # Info
        info = QLabel(
            f"{run.get('profile_name', '?')}  —  {run.get('hostname', '?')}  "
            f"({run.get('asset_tag', '')})"
        )
        info.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(info, stretch=1)

        # Stats
        stats = QLabel(
            f"{run.get('succeeded_tasks', 0)}✓  {run.get('failed_tasks', 0)}✗  "
            f"{run.get('skipped_tasks', 0)}⊘"
        )
        stats.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;")
        layout.addWidget(stats)

        # Timestamp
        ts = QLabel(run.get("started_at", "")[:16].replace("T", " "))
        ts.setStyleSheet(f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SM}px;")
        layout.addWidget(ts)

        return row
