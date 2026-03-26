"""
Profile selection screen — card grid of available profiles.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models.profile_definition import ProfileDefinition
from app.ui.theme import ACCENT, BG_SECONDARY, BORDER, TEXT_MUTED, TEXT_SECONDARY


class ProfileScreen(QWidget):
    """Profile selection with card-based layout."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Header
        title = QLabel("Select Profile")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Choose a provisioning profile for the target device")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        # Grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(16)
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, stretch=1)

        # Back button
        back_btn = QPushButton("← Back to Dashboard")
        back_btn.clicked.connect(lambda: self.mw.navigate_to(self.mw.HOME))
        layout.addWidget(back_btn)

    def on_enter(self):
        """Load profiles and populate grid."""
        # Clear existing cards
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        profiles = self.mw.profile_loader.load_profiles()

        for idx, profile in enumerate(profiles):
            card = self._build_profile_card(profile)
            row, col = divmod(idx, 3)
            self.grid_layout.addWidget(card, row, col)

        if not profiles:
            empty = QLabel("No profiles available. Check bundled profiles or connect SSD kit.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(empty, 0, 0, 1, 3)

    def _build_profile_card(self, profile: ProfileDefinition) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            f"QWidget {{ background: {BG_SECONDARY}; border: 1px solid {BORDER}; "
            f"border-radius: 10px; padding: 20px; }}"
            f"QWidget:hover {{ border-color: {ACCENT}; }}"
        )
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(180)
        card.setMinimumWidth(240)

        layout = QVBoxLayout(card)

        # Icon placeholder (emoji based on icon field)
        icon_map = {
            "briefcase": "💼", "palette": "🎨", "code": "💻",
            "settings": "⚙️", "computer": "🖥️",
        }
        icon = QLabel(icon_map.get(profile.icon, "📦"))
        icon.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon)

        name = QLabel(profile.name)
        name.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(name)

        desc = QLabel(profile.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(desc)

        task_count = QLabel(f"{len(profile.get_enabled_tasks())} tasks")
        task_count.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(task_count)

        layout.addStretch()

        # Click handler — use mousePressEvent on the card
        card.mousePressEvent = lambda event, p=profile: self._select_profile(p)

        return card

    def _select_profile(self, profile: ProfileDefinition):
        self.mw.selected_profile = profile
        self.mw.navigate_to(self.mw.METADATA)
