"""
Path resolution helpers.

Handles the difference between running from source vs running
from a PyInstaller bundle (where sys._MEIPASS is set).
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    Get the application root directory.
    - In PyInstaller bundle: sys._MEIPASS (temp extraction dir)
    - In development: project root (parent of app/)
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    # Running from source
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """
    Get the writable data directory for SQLite, logs, etc.
    - In PyInstaller bundle: next to the .exe
    - In development: project root
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return get_app_root()


def get_config_path() -> Path:
    return get_app_root() / "config" / "app_config.json"


def get_bundled_profiles_dir() -> Path:
    return get_app_root() / "profiles"


def get_bundled_packages_dir() -> Path:
    return get_app_root() / "packages"


def get_scripts_dir() -> Path:
    return get_app_root() / "scripts"
