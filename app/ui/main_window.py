"""
Main window — navigation container using QStackedWidget.

Manages screen transitions and provides access to shared state
(app config, database, kit info, selected profile, device metadata).
"""

from __future__ import annotations

import json
import logging

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.kit_detector import KitDetector, KitInfo
from app.core.profile_loader import ProfileLoader
from app.core.profile_manager_screen import ProfileManagerScreen
from app.core.webhook import WebhookSender
from app.db.database import Database
from app.db.repository import Repository
from app.models.app_config import AppConfig
from app.models.device_metadata import DeviceMetadata
from app.models.profile_definition import ProfileDefinition
from app.ui.screens.execution_screen import ExecutionScreen
from app.ui.screens.home_screen import HomeScreen
from app.ui.screens.metadata_screen import MetadataScreen
from app.ui.screens.package_manager_screen import PackageManagerScreen
from app.ui.screens.profile_screen import ProfileScreen
from app.ui.screens.review_screen import ReviewScreen
from app.ui.screens.summary_screen import SummaryScreen
from app.ui.screens.webhook_settings_screen import WebhookSettingsScreen
from app.ui.theme import (
    ACCENT,
    BG_SECONDARY,
    FONT_MONO,
    FONT_SIZE_SM,
    TEXT_MUTED,
)
from app.utils.paths import (
    get_bundled_packages_dir,
    get_bundled_profiles_dir,
    get_config_path,
    get_data_dir,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application main window."""

    # Screen indices
    HOME = 0
    PROFILE = 1
    METADATA = 2
    REVIEW = 3
    EXECUTION = 4
    SUMMARY = 5
    PROFILE_MANAGER = 6
    PACKAGE_MANAGER = 7
    WEBHOOK_SETTINGS = 8

    def __init__(self):
        super().__init__()

        # ── Load config ──────────────────────────────────────────
        self.config = self._load_config()

        # ── Initialize database ──────────────────────────────────
        db_path = get_data_dir() / self.config.app.db_path
        self.db = Database(db_path)
        self.db.initialize()
        self.repo = Repository(self.db)

        # ── Detect provisioning kit ──────────────────────────────
        self.kit: KitInfo | None = KitDetector(
            marker_filename=self.config.kit.marker_filename,
            manifest_filename=self.config.kit.manifest_filename,
        ).scan()

        # ── Profile loader ───────────────────────────────────────
        self.profile_loader = ProfileLoader(
            bundled_profiles_dir=get_bundled_profiles_dir(),
            bundled_packages_dir=get_bundled_packages_dir(),
            kit=self.kit,
        )

        # ── Webhook sender ───────────────────────────────────────
        self.webhook_sender = WebhookSender(self.config.webhook, self.repo)

        # ── Shared state ─────────────────────────────────────────
        self.selected_profile: ProfileDefinition | None = None
        self.device_metadata: DeviceMetadata = DeviceMetadata()
        self.task_overrides: dict[str, bool] = {}
        self.last_run_id: str | None = None

        # ── Window setup ─────────────────────────────────────────
        self.setWindowTitle(f"WinProv — {self.config.app.version}")
        self.resize(self.config.ui.window_width, self.config.ui.window_height)
        self.setMinimumSize(900, 600)

        # ── Build UI ─────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = self._build_header()
        layout.addWidget(header)

        # Stacked screens
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # Create screens
        self.home_screen = HomeScreen(self)
        self.profile_screen = ProfileScreen(self)
        self.metadata_screen = MetadataScreen(self)
        self.review_screen = ReviewScreen(self)
        self.execution_screen = ExecutionScreen(self)
        self.summary_screen = SummaryScreen(self)
        self.profile_manager_screen = ProfileManagerScreen(self)
        self.package_manager_screen = PackageManagerScreen(self)
        self.webhook_settings_screen = WebhookSettingsScreen(self)

        self.stack.addWidget(self.home_screen)     # 0
        self.stack.addWidget(self.profile_screen)  # 1
        self.stack.addWidget(self.metadata_screen) # 2
        self.stack.addWidget(self.review_screen)   # 3
        self.stack.addWidget(self.execution_screen)# 4
        self.stack.addWidget(self.summary_screen)  # 5
        self.stack.addWidget(self.profile_manager_screen) # 6
        self.stack.addWidget(self.package_manager_screen) # 7
        self.stack.addWidget(self.webhook_settings_screen) # 8

        # Footer
        footer = self._build_footer()
        layout.addWidget(footer)

    def navigate_to(self, screen_index: int):
        """Switch to a screen by index."""
        self.stack.setCurrentIndex(screen_index)

        # Refresh screen data when navigating
        widget = self.stack.currentWidget()
        if hasattr(widget, "on_enter"):
            widget.on_enter()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet(f"background-color: {BG_SECONDARY}; padding: 8px 16px;")
        header.setFixedHeight(48)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("WinProv")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {ACCENT};")
        layout.addWidget(title)

        layout.addStretch()

        kit_label = QLabel()
        if self.kit:
            kit_label.setText(f"Kit: {self.kit.kit_name} ({self.kit.drive_letter}:)")
            kit_label.setStyleSheet(f"color: {ACCENT}; font-size: 12px;")
        else:
            kit_label.setText("No kit detected")
            kit_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(kit_label)

        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(28)
        footer.setStyleSheet(f"background-color: {BG_SECONDARY};")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 0, 16, 0)

        version = QLabel(f"v{self.config.app.version}")
        version.setStyleSheet(f"color: {TEXT_MUTED}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;")
        layout.addWidget(version)

        layout.addStretch()

        db_label = QLabel(f"DB: {self.config.app.db_path}")
        db_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: {FONT_SIZE_SM}px;")
        layout.addWidget(db_label)

        return footer

    def _load_config(self) -> AppConfig:
        config_path = get_config_path()
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                return AppConfig.model_validate(data)
            except Exception as exc:
                logger.error("Failed to load config: %s (using defaults)", exc)
        return AppConfig()

    def save_config(self) -> None:
        """Persist current app config to writable config path."""
        config_path = get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.config.model_dump(mode="json")
        config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Refresh runtime webhook sender with latest config
        self.webhook_sender = WebhookSender(self.config.webhook, self.repo)
        logger.info("Config saved: %s", config_path)

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
