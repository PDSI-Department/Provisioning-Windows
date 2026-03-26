"""
WinProv — Windows Provisioning Tool
Entry point.

Bootstraps logging, checks admin privileges, and launches the UI.
"""

from __future__ import annotations

import sys

from app.utils.logger import setup_logging
from app.utils.paths import get_data_dir


def main():
    # ── Logging ──────────────────────────────────────────────
    log_dir = get_data_dir() / "logs"
    setup_logging(log_dir=str(log_dir), level="INFO")

    import logging
    logger = logging.getLogger(__name__)
    logger.info("WinProv starting")

    # ── Admin check (Windows only) ───────────────────────────
    try:
        from app.utils.admin import is_admin
        if not is_admin():
            logger.warning("Not running as admin — some tasks may fail")
            # Optionally auto-elevate:
            # from app.utils.admin import request_elevation
            # request_elevation()
    except Exception:
        pass  # Not on Windows

    # ── Qt Application ───────────────────────────────────────
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)

    # Set default font
    font = QFont("Segoe UI", 13)
    app.setFont(font)

    # Apply global stylesheet
    from app.ui.theme import STYLESHEET
    app.setStyleSheet(STYLESHEET)

    # ── Main Window ──────────────────────────────────────────
    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    window.navigate_to(MainWindow.HOME)

    logger.info("UI launched")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
