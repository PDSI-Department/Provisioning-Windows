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
import re
import shutil
from pathlib import Path

from app.core.kit_detector import KitInfo
from app.models.package_definition import PackageDefinition
from app.models.profile_definition import ProfileDefinition
from app.utils.paths import get_data_dir

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Loads profiles and packages from bundled dirs and external kit."""

    def __init__(
        self,
        bundled_profiles_dir: Path,
        bundled_packages_dir: Path,
        kit: KitInfo | None = None,
        user_profiles_dir: Path | None = None,
        user_packages_dir: Path | None = None,
    ):
        self.bundled_profiles_dir = bundled_profiles_dir
        self.bundled_packages_dir = bundled_packages_dir
        self.kit = kit
        data_dir = get_data_dir()
        self.user_profiles_dir = user_profiles_dir or (data_dir / "profiles")
        self.user_packages_dir = user_packages_dir or (data_dir / "packages")

    def load_profiles(self) -> list[ProfileDefinition]:
        """Load all available profiles. User/kit profiles override bundled ones by ID."""
        profiles: dict[str, ProfileDefinition] = {}

        # Load bundled first
        for p in self._load_profiles_from(self.bundled_profiles_dir):
            profiles[p.profile_id] = p

        # Kit overrides bundled
        if self.kit and self.kit.profiles_dir.exists():
            for p in self._load_profiles_from(self.kit.profiles_dir):
                profiles[p.profile_id] = p
                logger.info("Kit profile loaded (override): %s", p.profile_id)

        # User-local overrides/new profiles
        if self.user_profiles_dir.exists():
            for p in self._load_profiles_from(self.user_profiles_dir):
                profiles[p.profile_id] = p
                logger.info("Local profile loaded (override): %s", p.profile_id)

        result = sorted(profiles.values(), key=lambda p: p.name)
        logger.info("Loaded %d profiles total", len(result))
        return result

    def load_package(self, package_id: str) -> PackageDefinition | None:
        """Load package metadata by ID. User/kit packages take precedence."""
        # Try user-local first
        pkg = self._load_package_from(self.user_packages_dir, package_id)
        if pkg:
            return pkg

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
        Checks local packages dir, then kit, then bundled.
        """
        pkg = self.load_package(package_id)
        if not pkg or not pkg.installer:
            return None

        # Check user-local
        user_path = self.user_packages_dir / package_id / pkg.installer.filename
        if user_path.exists():
            return user_path

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

    def save_profile(self, profile: ProfileDefinition) -> Path:
        """Save or update a profile JSON in writable local profiles directory."""
        self._ensure_profile_id(profile.profile_id)
        self.user_profiles_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_profiles_dir / f"{profile.profile_id}.json"
        payload = profile.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Profile saved: %s", path)
        return path

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a local profile by ID. Returns True if deleted."""
        self._ensure_profile_id(profile_id)
        path = self.user_profiles_dir / f"{profile_id}.json"
        if path.exists():
            path.unlink()
            logger.info("Profile deleted: %s", path)
            return True
        return False

    def list_packages(self) -> list[PackageDefinition]:
        """List all available packages from bundled, kit, and local sources."""
        ids: set[str] = set()
        ids.update(self._iter_package_ids(self.bundled_packages_dir))
        ids.update(self._iter_package_ids(self.user_packages_dir))
        if self.kit:
            ids.update(self._iter_package_ids(self.kit.packages_dir))

        items: list[PackageDefinition] = []
        for pkg_id in sorted(ids):
            pkg = self.load_package(pkg_id)
            if pkg:
                items.append(pkg)
        return sorted(items, key=lambda p: (p.name.lower(), p.package_id.lower()))

    def import_package_source(
        self,
        package_id: str,
        name: str,
        source_path: str | Path | None,
        install_type: str = "exe_installer",
        installer_arguments: str = "",
        winget_id: str = "",
        description: str = "",
        publisher: str = "",
        installer_relative_path: str = "",
        detect_path: str = "",
    ) -> PackageDefinition:
        """
        Import/update a package source into local packages dir and write meta.json.

        For EXE/MSI installer package types, source_path can be file or folder.
        For winget_install, source_path is optional.
        """
        self._ensure_profile_id(package_id)
        if not name.strip():
            raise ValueError("Package name is required")

        install_type = install_type.strip() or "exe_installer"
        is_winget = install_type == "winget_install"
        if is_winget and not winget_id.strip():
            raise ValueError("winget_id is required for winget_install")

        package_dir = self.user_packages_dir / package_id
        package_dir.mkdir(parents=True, exist_ok=True)

        detected_installer = installer_relative_path.strip()
        source = Path(source_path) if source_path else None

        if not is_winget:
            if not source:
                raise ValueError("Source path is required for installer-based packages")
            if not source.exists():
                raise FileNotFoundError(f"Source not found: {source}")

            # Clear old imported files before replacing package source.
            if package_dir.exists():
                for child in package_dir.iterdir():
                    if child.name == "meta.json":
                        continue
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()

            if source.is_file():
                target = package_dir / source.name
                shutil.copy2(source, target)
                if not detected_installer:
                    detected_installer = source.name
            else:
                for child in source.iterdir():
                    dst = package_dir / child.name
                    if child.is_dir():
                        shutil.copytree(child, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(child, dst)
                if not detected_installer:
                    detected_installer = self._auto_detect_installer_rel(package_dir)

            if not detected_installer:
                raise ValueError(
                    "Installer tidak terdeteksi. Isi 'installer_relative_path' secara manual."
                )

            rel = Path(detected_installer)
            resolved = package_dir / rel
            if not resolved.exists():
                raise FileNotFoundError(f"Installer file not found in package dir: {detected_installer}")
            detected_installer = rel.as_posix()

        package_dict: dict = {
            "package_id": package_id,
            "name": name.strip(),
            "version": "latest",
            "description": description.strip(),
            "publisher": publisher.strip(),
            "install_type": install_type,
            "winget_id": winget_id.strip() or None,
            "tags": [],
        }

        if not is_winget:
            package_dict["installer"] = {
                "filename": detected_installer,
                "arguments": installer_arguments.strip(),
                "exit_codes": {"success": [0]},
            }

        if detect_path.strip():
            package_dict["detect_rule"] = {
                "type": "path_exists",
                "value": detect_path.strip(),
            }

        pkg = PackageDefinition.model_validate(package_dict)

        package_dir.mkdir(parents=True, exist_ok=True)
        meta_path = package_dir / "meta.json"
        meta_path.write_text(
            json.dumps(pkg.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Package imported: %s", meta_path)
        return pkg

    def delete_package(self, package_id: str) -> bool:
        """Delete local package directory by package ID."""
        self._ensure_profile_id(package_id)
        package_dir = self.user_packages_dir / package_id
        if not package_dir.exists():
            return False
        shutil.rmtree(package_dir)
        logger.info("Package deleted: %s", package_dir)
        return True

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

    @staticmethod
    def _ensure_profile_id(value: str) -> None:
        if not value or not re.match(r"^[a-zA-Z0-9._-]+$", value):
            raise ValueError("ID hanya boleh berisi huruf, angka, titik, underscore, atau dash")

    @staticmethod
    def _iter_package_ids(packages_dir: Path) -> set[str]:
        if not packages_dir.exists():
            return set()
        result = set()
        for d in packages_dir.iterdir():
            if d.is_dir() and (d / "meta.json").exists():
                result.add(d.name)
        return result

    @staticmethod
    def _auto_detect_installer_rel(package_dir: Path) -> str:
        preferred = {"setup.exe", "install.exe", "installer.exe"}
        candidates = []
        for f in package_dir.rglob("*"):
            if not f.is_file():
                continue
            suffix = f.suffix.lower()
            if suffix not in {".exe", ".msi", ".msix", ".msixbundle"}:
                continue
            candidates.append(f)

        if not candidates:
            return ""

        # 1) Preferred installer names
        for f in candidates:
            if f.name.lower() in preferred:
                return f.relative_to(package_dir).as_posix()

        # 2) MSI first
        for f in candidates:
            if f.suffix.lower() == ".msi":
                return f.relative_to(package_dir).as_posix()

        # 3) fallback first candidate
        return candidates[0].relative_to(package_dir).as_posix()
