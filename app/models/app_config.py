"""App configuration model — loaded from config/app_config.json."""

from __future__ import annotations

from pydantic import BaseModel


class AppSection(BaseModel):
    name: str = "WinProv"
    version: str = "0.1.0"
    log_level: str = "INFO"
    log_dir: str = "logs"
    db_path: str = "data/winprov.db"


class ProvisioningSection(BaseModel):
    default_task_timeout_seconds: int = 300
    max_parallel_tasks: int = 1
    continue_on_error_default: bool = False
    collect_inventory_after_run: bool = True


class WebhookSection(BaseModel):
    enabled: bool = True
    url: str = ""
    timeout_seconds: int = 30
    max_retries: int = 5
    retry_interval_seconds: int = 60
    headers: dict[str, str] = {}


class KitSection(BaseModel):
    marker_filename: str = ".winprov-kit"
    manifest_filename: str = "manifest.json"
    scan_removable_only: bool = True


class UiSection(BaseModel):
    theme: str = "dark"
    window_width: int = 1100
    window_height: int = 750


class AppConfig(BaseModel):
    """Root application configuration."""

    app: AppSection = AppSection()
    provisioning: ProvisioningSection = ProvisioningSection()
    webhook: WebhookSection = WebhookSection()
    kit: KitSection = KitSection()
    ui: UiSection = UiSection()
