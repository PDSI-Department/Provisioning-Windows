"""Enumerations used throughout the application."""

from enum import StrEnum


class TaskType(StrEnum):
    WINGET_INSTALL = "winget_install"
    EXE_INSTALLER = "exe_installer"
    MSI_INSTALLER = "msi_installer"
    POWERSHELL_SCRIPT = "powershell_script"
    POWERSHELL_COMMAND = "powershell_command"
    PYTHON_NATIVE = "python_native"
    INVENTORY_COLLECTION = "inventory_collection"
    WEBHOOK = "webhook"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WebhookStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class DetectRuleType(StrEnum):
    PATH_EXISTS = "path_exists"
    REGISTRY_EXISTS = "registry_exists"
    WINGET_LIST = "winget_list"
    COMMAND_EXIT_CODE = "command_exit_code"
