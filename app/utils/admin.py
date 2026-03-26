"""Admin privilege utilities for Windows."""

from __future__ import annotations

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Check if the current process has admin (elevated) privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        # Not on Windows or ctypes issue
        return False


def request_elevation() -> None:
    """
    Re-launch the current script with admin privileges via UAC prompt.
    Only works on Windows. Exits the current process after requesting elevation.
    """
    if is_admin():
        return

    try:
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(sys.argv),
            None,
            1,  # SW_SHOWNORMAL
        )
        sys.exit(0)
    except Exception as exc:
        logger.error("Failed to request elevation: %s", exc)
