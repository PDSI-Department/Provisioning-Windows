"""
Webhook settings screen.

Provides configuration form + test send payload.
"""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import TEXT_MUTED


class WebhookSettingsScreen(QWidget):
    """Configure webhook endpoint and test payload delivery."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        title = QLabel("Webhook Settings")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        subtitle = QLabel("Konfigurasi endpoint webhook dan test kirim payload.")
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(subtitle)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        root.addWidget(self.status_label)

        form = QFormLayout()
        form.setSpacing(8)

        self.f_enabled = QCheckBox("Enabled")
        form.addRow("Webhook:", self.f_enabled)

        self.f_url = QLineEdit()
        self.f_url.setPlaceholderText("https://hooks.example.com/provisioning")
        form.addRow("URL:", self.f_url)

        self.f_timeout = QSpinBox()
        self.f_timeout.setRange(1, 300)
        self.f_timeout.setSuffix(" sec")
        form.addRow("Timeout:", self.f_timeout)

        self.f_max_retries = QSpinBox()
        self.f_max_retries.setRange(0, 20)
        form.addRow("Max Retries:", self.f_max_retries)

        self.f_retry_interval = QSpinBox()
        self.f_retry_interval.setRange(1, 3600)
        self.f_retry_interval.setSuffix(" sec")
        form.addRow("Retry Interval:", self.f_retry_interval)

        self.f_headers = QTextEdit()
        self.f_headers.setPlaceholderText('{"X-Source":"winprov"}')
        self.f_headers.setMaximumHeight(140)
        form.addRow("Headers JSON:", self.f_headers)

        root.addLayout(form)
        root.addStretch()

        actions = QHBoxLayout()
        back = QPushButton("← Dashboard")
        back.clicked.connect(lambda: self.mw.navigate_to(self.mw.HOME))
        actions.addWidget(back)

        actions.addStretch()

        test_btn = QPushButton("Test Send")
        test_btn.clicked.connect(self._test_send)
        actions.addWidget(test_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_settings)
        actions.addWidget(save_btn)

        root.addLayout(actions)

    def on_enter(self):
        cfg = self.mw.config.webhook
        self.f_enabled.setChecked(cfg.enabled)
        self.f_url.setText(cfg.url)
        self.f_timeout.setValue(cfg.timeout_seconds)
        self.f_max_retries.setValue(cfg.max_retries)
        self.f_retry_interval.setValue(cfg.retry_interval_seconds)
        self.f_headers.setPlainText(json.dumps(cfg.headers, indent=2, ensure_ascii=False))
        self.status_label.setText("")

    def _read_headers(self) -> dict[str, str]:
        raw = self.f_headers.toPlainText().strip()
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Headers JSON invalid: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError("Headers JSON harus object")
        return {str(k): str(v) for k, v in obj.items()}

    def _save_settings(self):
        try:
            headers = self._read_headers()
            cfg = self.mw.config.webhook
            cfg.enabled = self.f_enabled.isChecked()
            cfg.url = self.f_url.text().strip()
            cfg.timeout_seconds = self.f_timeout.value()
            cfg.max_retries = self.f_max_retries.value()
            cfg.retry_interval_seconds = self.f_retry_interval.value()
            cfg.headers = headers
            self.mw.save_config()
            self.status_label.setText("Settings saved.")
            QMessageBox.information(self, "Saved", "Webhook settings tersimpan.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _test_send(self):
        try:
            self._save_settings()
            ok, msg = self.mw.webhook_sender.test_send(
                payload={"event": "winprov_test", "source": "settings_screen"}
            )
            if ok:
                QMessageBox.information(self, "Webhook Test", msg)
            else:
                QMessageBox.warning(self, "Webhook Test", msg)
            self.status_label.setText(msg)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
