"""
Profile and package loader.

Loads provisioning profiles and package metadata from:
1. Bundled directories (shipped with the app)
2. External SSD kit (detected at runtime)

Kit paths take precedence over bundled — this allows the SSD to
carry updated profiles/packages without rebuilding the app.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.kit_detector import KitInfo
from app.models.package_definition import PackageDefinition
from app.models.profile_definition import ProfileDefinition

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Loads profiles and packages from bundled dirs and external kit."""

    def __init__(
        self,
        bundled_profiles_dir: Path,
        bundled_packages_dir: Path,
        kit: KitInfo | None = None,
    ):
        self.bundled_profiles_dir = bundled_profiles_dir
        self.bundled_packages_dir = bundled_packages_dir
        self.kit = kit

    def load_profiles(self) -> list[ProfileDefinition]:
        """Load all available profiles. Kit profiles override bundled ones by ID."""
        profiles: dict[str, ProfileDefinition] = {}

        # Load bundled first
        for p in self._load_profiles_from(self.bundled_profiles_dir):
            profiles[p.profile_id] = p

        # Kit overrides bundled
        if self.kit and self.kit.profiles_dir.exists():
            for p in self._load_profiles_from(self.kit.profiles_dir):
                profiles[p.profile_id] = p
                logger.info("Kit profile loaded (override): %s", p.profile_id)

        result = sorted(profiles.values(), key=lambda p: p.name)
        logger.info("Loaded %d profiles total", len(result))
        return result

    def load_package(self, package_id: str) -> PackageDefinition | None:
        """Load package metadata by ID. Kit packages take precedence."""
        # Try kit first
        if self.kit:
            pkg = self._load_package_from(self.kit.packages_dir, package_id)
            if pkg:
                return pkg

        # Fallback to bundled
        return self._load_package_from(self.bundled_packages_dir, package_id)

    def resolve_installer_path(self, package_id: str) -> Path | None:
        """
        Find the actual installer file for a package.
        Checks kit packages dir first, then bundled.
        """
        pkg = self.load_package(package_id)
        if not pkg or not pkg.installer:
            return None

        # Check kit
        if self.kit:
            kit_path = self.kit.packages_dir / package_id / pkg.installer.filename
            if kit_path.exists():
                return kit_path

        # Check bundled
        bundled_path = self.bundled_packages_dir / package_id / pkg.installer.filename
        if bundled_path.exists():
            return bundled_path

        logger.warning("Installer file not found for %s: %s", package_id, pkg.installer.filename)
        return None

    def resolve_script_path(self, relative_path: str) -> Path | None:
        """
        Resolve a script path. Tries kit scripts dir first, then bundled.
        The relative_path is as specified in the profile JSON (e.g., 'scripts/rename_hostname.ps1').
        """
        if self.kit:
            kit_script = self.kit.path / relative_path
            if kit_script.exists():
                return kit_script

        # Bundled: resolve relative to app root
        bundled = Path(__file__).resolve().parent.parent.parent / relative_path
        if bundled.exists():
            return bundled

        logger.warning("Script not found: %s", relative_path)
        return None

    # ── Private ───────────────────────────────────────────────────

    def _load_profiles_from(self, directory: Path) -> list[ProfileDefinition]:
        profiles = []
        if not directory.exists():
            return profiles

        for f in directory.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                profile = ProfileDefinition.model_validate(data)
                profiles.append(profile)
            except Exception as exc:
                logger.error("Failed to load profile %s: %s", f.name, exc)

        return profiles

    def _load_package_from(self, packages_dir: Path, package_id: str) -> PackageDefinition | None:
        meta_path = packages_dir / package_id / "meta.json"
        if not meta_path.exists():
            return None

        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return PackageDefinition.model_validate(data)
        except Exception as exc:
            logger.error("Failed to load package %s: %s", package_id, exc)
            return None
