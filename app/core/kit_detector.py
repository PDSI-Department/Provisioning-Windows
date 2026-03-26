"""
Provisioning kit detector.

Scans available drive letters to find an external SSD containing
the provisioning kit (profiles, packages, scripts).

Detection method:
- Iterate drive letters (D: through Z:)
- Look for a marker file (default: .winprov-kit) at root
- If found, read the manifest.json alongside it
- Return the kit path and parsed manifest
"""

from __future__ import annotations

import json
import logging
import string
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class KitInfo:
    """Detected provisioning kit information."""

    path: Path
    drive_letter: str
    manifest: dict
    profiles_dir: Path
    packages_dir: Path
    scripts_dir: Path

    @property
    def kit_name(self) -> str:
        return self.manifest.get("kit_name", "Unknown Kit")

    @property
    def kit_version(self) -> str:
        return self.manifest.get("kit_version", "?")


class KitDetector:
    """Auto-detect provisioning kit on removable drives."""

    def __init__(
        self,
        marker_filename: str = ".winprov-kit",
        manifest_filename: str = "manifest.json",
    ):
        self.marker_filename = marker_filename
        self.manifest_filename = manifest_filename

    def scan(self) -> KitInfo | None:
        """
        Scan all non-system drives for a provisioning kit.
        Returns KitInfo if found, None otherwise.
        """
        # Scan D: through Z: (skip A:, B:, C: which are system/floppy)
        for letter in string.ascii_uppercase[3:]:
            drive = Path(f"{letter}:\\")
            if not drive.exists():
                continue

            marker = drive / self.marker_filename
            if not marker.exists():
                continue

            logger.info("Kit marker found on %s:", letter)
            manifest_path = drive / self.manifest_filename

            if not manifest_path.exists():
                logger.warning("Marker found but no manifest at %s", manifest_path)
                continue

            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to read manifest: %s", exc)
                continue

            kit = KitInfo(
                path=drive,
                drive_letter=letter,
                manifest=manifest,
                profiles_dir=drive / manifest.get("profiles_dir", "profiles"),
                packages_dir=drive / manifest.get("packages_dir", "packages"),
                scripts_dir=drive / manifest.get("scripts_dir", "scripts"),
            )
            logger.info("Kit detected: %s v%s at %s:", kit.kit_name, kit.kit_version, drive)
            return kit

        logger.info("No provisioning kit detected on any drive")
        return None

    def scan_path(self, path: str | Path) -> KitInfo | None:
        """Check a specific path for a provisioning kit (useful for testing)."""
        root = Path(path)
        marker = root / self.marker_filename
        manifest_path = root / self.manifest_filename

        if not marker.exists() or not manifest_path.exists():
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        return KitInfo(
            path=root,
            drive_letter=str(root)[:1],
            manifest=manifest,
            profiles_dir=root / manifest.get("profiles_dir", "profiles"),
            packages_dir=root / manifest.get("packages_dir", "packages"),
            scripts_dir=root / manifest.get("scripts_dir", "scripts"),
        )
