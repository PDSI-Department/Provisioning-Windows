"""
Device metadata form — IT Support fills in device information.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from app.models.device_metadata import DeviceMetadata


# Default departments — can be customized via config later
DEPARTMENTS = [
    "", "PDSI", "DAN", "BAHASA", "Layout", "Marketing",
    "Finance", "HRD", "Warehouse", "Management", "Other",
]

LOCATIONS = [
    "", "Kantor Pusat", "Gudang", "Kantor Cabang",
]


class MetadataScreen(QWidget):
    """Form for device metadata input."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        title = QLabel("Device Information")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.profile_label = QLabel("")
        self.profile_label.setObjectName("subtitleLabel")
        layout.addWidget(self.profile_label)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.asset_tag_input = QLineEdit()
        self.asset_tag_input.setPlaceholderText("e.g. DP-PC-0042")
        form.addRow("Asset Tag:", self.asset_tag_input)

        self.user_name_input = QLineEdit()
        self.user_name_input.setPlaceholderText("Nama user yang akan memakai perangkat")
        form.addRow("User Name:", self.user_name_input)

        self.department_input = QComboBox()
        self.department_input.addItems(DEPARTMENTS)
        form.addRow("Department:", self.department_input)

        self.location_input = QComboBox()
        self.location_input.addItems(LOCATIONS)
        self.location_input.setEditable(True)
        form.addRow("Location:", self.location_input)

        self.hostname_input = QLineEdit()
        self.hostname_input.setPlaceholderText("e.g. DP-PC-PDSI-042")
        form.addRow("Hostname:", self.hostname_input)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Catatan tambahan (opsional)")
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)
        layout.addStretch()

        # Navigation buttons
        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(lambda: self.mw.navigate_to(self.mw.PROFILE))
        nav.addWidget(back_btn)

        nav.addStretch()

        next_btn = QPushButton("Review Tasks →")
        next_btn.setObjectName("primaryButton")
        next_btn.clicked.connect(self._proceed)
        nav.addWidget(next_btn)

        layout.addLayout(nav)

    def on_enter(self):
        if self.mw.selected_profile:
            self.profile_label.setText(f"Profile: {self.mw.selected_profile.name}")

    def _proceed(self):
        """Collect form data and move to review screen."""
        self.mw.device_metadata = DeviceMetadata(
            asset_tag=self.asset_tag_input.text().strip(),
            user_name=self.user_name_input.text().strip(),
            department=self.department_input.currentText(),
            location=self.location_input.currentText(),
            hostname=self.hostname_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
        )
        self.mw.navigate_to(self.mw.REVIEW)
