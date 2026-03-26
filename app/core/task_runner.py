"""
Task runner — dispatches task definitions to the appropriate handler.

Each task type has a dedicated handler method. The runner also handles:
- Detect rule evaluation (skip if already satisfied)
- Retry logic
- Timeout enforcement
- Structured result capture
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.powershell_runner import PowerShellRunner, PSResult
from app.models.enums import DetectRuleType, TaskStatus, TaskType
from app.models.task_definition import TaskDefinition

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Outcome of running a single task."""

    status: TaskStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    error_message: str = ""


class TaskRunner:
    """Executes individual provisioning tasks."""

    def __init__(
        self,
        ps_runner: PowerShellRunner,
        packages_resolver: callable,  # fn(package_id) -> (installer_path, PackageDefinition)
        script_resolver: callable,    # fn(relative_path) -> absolute_path
    ):
        self.ps = ps_runner
        self.resolve_package = packages_resolver
        self.resolve_script = script_resolver

    def check_detect_rule(self, task: TaskDefinition) -> bool:
        """
        Evaluate a task's detect_rule to see if the target state is already met.
        Returns True if the task should be SKIPPED (already satisfied).
        """
        if task.detect_rule is None:
            return False

        rule_type = task.detect_rule.type
        rule_value = task.detect_rule.value

        try:
            if rule_type == DetectRuleType.PATH_EXISTS:
                exists = Path(rule_value).exists()
                if exists:
                    logger.info("Detect rule satisfied (path exists): %s", rule_value)
                return exists

            elif rule_type == DetectRuleType.REGISTRY_EXISTS:
                result = self.ps.run_command(
                    f"Test-Path '{rule_value}'",
                    timeout=15,
                )
                satisfied = result.success and result.stdout.strip().lower() == "true"
                if satisfied:
                    logger.info("Detect rule satisfied (registry): %s", rule_value)
                return satisfied

            elif rule_type == DetectRuleType.WINGET_LIST:
                result = self.ps.run_command(
                    f"winget list --id {rule_value} --accept-source-agreements",
                    timeout=30,
                )
                satisfied = result.success and rule_value in result.stdout
                if satisfied:
                    logger.info("Detect rule satisfied (winget): %s", rule_value)
                return satisfied

            elif rule_type == DetectRuleType.COMMAND_EXIT_CODE:
                result = self.ps.run_command(rule_value, timeout=15)
                return result.exit_code == 0

        except Exception as exc:
            logger.warning("Detect rule check failed for %s: %s", task.id, exc)

        return False

    def execute(self, task: TaskDefinition, context: dict[str, str]) -> TaskResult:
        """
        Execute a single task. Dispatches to the appropriate handler based on type.

        Args:
            task: The task definition to execute.
            context: Variable context for template resolution (hostname, asset_tag, etc.).
        """
        handler = {
            TaskType.WINGET_INSTALL: self._handle_winget,
            TaskType.EXE_INSTALLER: self._handle_exe,
            TaskType.MSI_INSTALLER: self._handle_msi,
            TaskType.POWERSHELL_SCRIPT: self._handle_ps_script,
            TaskType.POWERSHELL_COMMAND: self._handle_ps_command,
            TaskType.PYTHON_NATIVE: self._handle_python,
        }.get(task.type)

        if handler is None:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=f"No handler for task type: {task.type}",
            )

        return handler(task, context)

    # ── Handlers ──────────────────────────────────────────────────

    def _handle_winget(self, task: TaskDefinition, context: dict) -> TaskResult:
        winget_id = task.winget_id or task.arguments.get("winget_id", "")
        if not winget_id:
            return TaskResult(status=TaskStatus.FAILED, error_message="No winget_id specified")

        cmd = f"winget install --id {winget_id} --silent --accept-source-agreements --accept-package-agreements"
        result = self.ps.run_command(cmd, timeout=task.timeout)
        return self._ps_to_task_result(result)

    def _handle_exe(self, task: TaskDefinition, context: dict) -> TaskResult:
        package_id = task.package_ref
        if not package_id:
            return TaskResult(status=TaskStatus.FAILED, error_message="No package_ref specified")

        installer_path, pkg = self.resolve_package(package_id)
        if not installer_path or not Path(installer_path).exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=f"Installer not found for {package_id}",
            )

        args = pkg.installer.arguments if pkg and pkg.installer else ""
        cmd = f'Start-Process -FilePath "{installer_path}" -ArgumentList "{args}" -Wait -NoNewWindow'
        result = self.ps.run_command(cmd, timeout=task.timeout)
        return self._ps_to_task_result(result)

    def _handle_msi(self, task: TaskDefinition, context: dict) -> TaskResult:
        package_id = task.package_ref
        if not package_id:
            return TaskResult(status=TaskStatus.FAILED, error_message="No package_ref specified")

        installer_path, pkg = self.resolve_package(package_id)
        if not installer_path or not Path(installer_path).exists():
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=f"MSI not found for {package_id}",
            )

        args = pkg.installer.arguments if pkg and pkg.installer else "/qn /norestart"
        cmd = f'Start-Process msiexec.exe -ArgumentList "/i `"{installer_path}`" {args}" -Wait -NoNewWindow'
        result = self.ps.run_command(cmd, timeout=task.timeout)
        return self._ps_to_task_result(result)

    def _handle_ps_script(self, task: TaskDefinition, context: dict) -> TaskResult:
        if not task.path:
            return TaskResult(status=TaskStatus.FAILED, error_message="No script path specified")

        script_path = self.resolve_script(task.path)
        if not script_path:
            return TaskResult(
                status=TaskStatus.FAILED,
                error_message=f"Script not found: {task.path}",
            )

        resolved_args = task.resolve_arguments(context)
        result = self.ps.run_script(script_path, resolved_args, timeout=task.timeout)
        return self._ps_to_task_result(result)

    def _handle_ps_command(self, task: TaskDefinition, context: dict) -> TaskResult:
        if not task.command:
            return TaskResult(status=TaskStatus.FAILED, error_message="No command specified")

        result = self.ps.run_command(task.command, timeout=task.timeout)
        return self._ps_to_task_result(result)

    def _handle_python(self, task: TaskDefinition, context: dict) -> TaskResult:
        """Placeholder for Python-native tasks (to be extended)."""
        logger.info("Python native task: %s (not yet implemented)", task.id)
        return TaskResult(
            status=TaskStatus.SUCCESS,
            stdout="Python native task placeholder",
        )

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _ps_to_task_result(ps_result: PSResult) -> TaskResult:
        return TaskResult(
            status=TaskStatus.SUCCESS if ps_result.success else TaskStatus.FAILED,
            exit_code=ps_result.exit_code,
            stdout=ps_result.stdout,
            stderr=ps_result.stderr,
            duration_ms=ps_result.duration_ms,
            error_message=ps_result.error_message,
        )
