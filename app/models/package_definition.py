"""Package metadata model — describes a software package and how to install it."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.task_definition import DetectRule


class InstallerInfo(BaseModel):
    filename: str
    arguments: str = ""
    exit_codes: dict[str, list[int]] = {"success": [0]}


class PackageDefinition(BaseModel):
    """
    Metadata for a software package.
    Loaded from packages/<PackageId>/meta.json.
    """

    package_id: str
    name: str
    version: str = "latest"
    description: str = ""
    publisher: str = ""
    install_type: str = "exe_installer"
    installer: InstallerInfo | None = None
    winget_id: str | None = None
    detect_rule: DetectRule | None = None
    tags: list[str] = []

    def get_installer_path(self, packages_dir: str) -> str | None:
        """Resolve full path to installer file within the packages directory."""
        if self.installer:
            from pathlib import Path
            return str(Path(packages_dir) / self.package_id / self.installer.filename)
        return None
