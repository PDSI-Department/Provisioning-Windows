"""
Provisioning Orchestrator — the main engine.

Coordinates the full provisioning flow:
1. Accept profile + device metadata
2. Build ordered task queue
3. Execute tasks sequentially, emitting signals for UI updates
4. Collect inventory
5. Send webhook
6. Save everything to SQLite

Runs in a QThread to keep the UI responsive. Communicates with UI
via Qt signals (progress updates, task status changes, log lines).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from app.core.inventory import InventoryCollector
from app.core.powershell_runner import PowerShellRunner
from app.core.profile_loader import ProfileLoader
from app.core.task_runner import TaskResult, TaskRunner
from app.core.webhook import WebhookSender
from app.db.repository import Repository
from app.models.device_metadata import DeviceMetadata
from app.models.enums import RunStatus, TaskStatus, TaskType
from app.models.profile_definition import ProfileDefinition
from app.models.task_definition import TaskDefinition

logger = logging.getLogger(__name__)


class Orchestrator(QThread):
    """
    Provisioning orchestrator thread.

    Signals:
        task_started(task_id, task_name)
        task_finished(task_id, status, duration_ms, error)
        log_line(message)
        progress_updated(current, total)
        run_finished(run_id, status)
        inventory_collected(inventory_dict)
    """

    task_started = Signal(str, str)
    task_finished = Signal(str, str, int, str)
    log_line = Signal(str)
    progress_updated = Signal(int, int)
    run_finished = Signal(str, str)
    inventory_collected = Signal(dict)

    def __init__(
        self,
        profile: ProfileDefinition,
        device: DeviceMetadata,
        task_overrides: dict[str, bool],  # task_id -> enabled
        repo: Repository,
        profile_loader: ProfileLoader,
        webhook_sender: WebhookSender,
        parent=None,
    ):
        super().__init__(parent)
        self.profile = profile
        self.device = device
        self.task_overrides = task_overrides
        self.repo = repo
        self.profile_loader = profile_loader
        self.webhook_sender = webhook_sender

        self.run_id = str(uuid.uuid4())
        self._cancelled = False

    def cancel(self):
        """Request cancellation. Current running task will complete first."""
        self._cancelled = True
        self._log("Cancellation requested")

    def run(self):
        """Main execution — called by QThread.start()."""
        self._log(f"=== Provisioning started: {self.profile.name} ===")

        # Build task list with overrides applied
        tasks = self._build_task_list()
        total = len(tasks)

        # Create run record
        self.repo.create_run({
            "run_id": self.run_id,
            "profile_id": self.profile.profile_id,
            "profile_name": self.profile.name,
            "status": RunStatus.RUNNING,
            "asset_tag": self.device.asset_tag,
            "user_name": self.device.user_name,
            "department": self.device.department,
            "location": self.device.location,
            "hostname": self.device.hostname,
            "notes": self.device.notes,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_tasks": total,
            "kit_path": str(self.profile_loader.kit.path) if self.profile_loader.kit else None,
        })
        self.repo.audit("INFO", "provisioning", f"Run started: {self.run_id}", {
            "profile": self.profile.profile_id,
            "hostname": self.device.hostname,
        })

        # Initialize runners
        ps_runner = PowerShellRunner()

        def package_resolver(pkg_id):
            pkg = self.profile_loader.load_package(pkg_id)
            path = self.profile_loader.resolve_installer_path(pkg_id)
            return (str(path) if path else None, pkg)

        task_runner = TaskRunner(
            ps_runner=ps_runner,
            packages_resolver=package_resolver,
            script_resolver=lambda p: self.profile_loader.resolve_script_path(p),
        )
        inventory_collector = InventoryCollector(ps_runner)
        context = self.device.to_context()

        # Execute tasks
        succeeded = 0
        failed = 0
        skipped = 0
        inventory_data = None

        for idx, task in enumerate(tasks):
            if self._cancelled:
                self._mark_remaining_cancelled(tasks[idx:])
                break

            self.progress_updated.emit(idx, total)

            # Handle special task types
            if task.type == TaskType.INVENTORY_COLLECTION:
                self._log(f"[{idx+1}/{total}] Collecting inventory...")
                self.task_started.emit(task.id, task.name)
                try:
                    inventory_data = inventory_collector.collect(timeout=task.timeout)
                    self.inventory_collected.emit(inventory_data.model_dump())
                    self._record_task(task, TaskStatus.SUCCESS, 0)
                    self.task_finished.emit(task.id, TaskStatus.SUCCESS, 0, "")
                    succeeded += 1
                except Exception as exc:
                    self._record_task(task, TaskStatus.FAILED, 0, error=str(exc))
                    self.task_finished.emit(task.id, TaskStatus.FAILED, 0, str(exc))
                    failed += 1
                continue

            if task.type == TaskType.WEBHOOK:
                self._log(f"[{idx+1}/{total}] Sending webhook...")
                self.task_started.emit(task.id, task.name)
                payload = self._build_webhook_payload(inventory_data)
                sent = self.webhook_sender.send(self.run_id, payload)
                status = TaskStatus.SUCCESS if sent else TaskStatus.FAILED
                self._record_task(task, status, 0)
                self.task_finished.emit(task.id, status, 0, "" if sent else "Queued for retry")
                if sent:
                    succeeded += 1
                else:
                    failed += 1
                continue

            # Standard task execution
            self._log(f"[{idx+1}/{total}] {task.name}")
            self.task_started.emit(task.id, task.name)

            # Check detect rule
            if task_runner.check_detect_rule(task):
                self._log(f"  → Skipped (already satisfied)")
                self._record_task(task, TaskStatus.SKIPPED, 0)
                self.task_finished.emit(task.id, TaskStatus.SKIPPED, 0, "")
                skipped += 1
                continue

            # Execute with retry
            result = self._execute_with_retry(task_runner, task, context)

            # Record result
            self._record_task(
                task, result.status, result.duration_ms,
                stdout=result.stdout, stderr=result.stderr, error=result.error_message,
                exit_code=result.exit_code,
            )
            self.task_finished.emit(task.id, result.status, result.duration_ms, result.error_message)

            if result.status == TaskStatus.SUCCESS:
                succeeded += 1
            else:
                failed += 1
                if not task.continue_on_error:
                    self._log(f"  → ABORT: Task failed and continue_on_error=false")
                    self._mark_remaining_cancelled(tasks[idx + 1:])
                    break

        # Finalize run
        self.progress_updated.emit(total, total)
        final_status = self._determine_final_status(succeeded, failed, skipped, total)

        self.repo.update_run(self.run_id, {
            "status": final_status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "succeeded_tasks": succeeded,
            "failed_tasks": failed,
            "skipped_tasks": skipped,
        })

        if inventory_data:
            self.repo.save_inventory(self.run_id, inventory_data.model_dump())

        self.repo.audit("INFO", "provisioning", f"Run finished: {final_status}", {
            "run_id": self.run_id,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
        })

        self._log(f"=== Provisioning {final_status}: {succeeded} ok, {failed} failed, {skipped} skipped ===")
        self.run_finished.emit(self.run_id, final_status)

    # ── Private ───────────────────────────────────────────────────

    def _build_task_list(self) -> list[TaskDefinition]:
        tasks = self.profile.get_enabled_tasks()
        # Apply user overrides from review screen
        return [t for t in tasks if self.task_overrides.get(t.id, t.enabled)]

    def _execute_with_retry(
        self, runner: TaskRunner, task: TaskDefinition, context: dict
    ) -> TaskResult:
        max_attempts = task.retry_count + 1
        for attempt in range(max_attempts):
            if attempt > 0:
                self._log(f"  → Retry {attempt}/{task.retry_count}")
                time.sleep(2)  # Brief pause between retries

            result = runner.execute(task, context)
            if result.status == TaskStatus.SUCCESS:
                return result

        return result  # Return last failed result

    def _record_task(
        self, task: TaskDefinition, status: str, duration_ms: int,
        stdout: str = "", stderr: str = "", error: str = "", exit_code: int = 0,
    ):
        self.repo.create_task_execution({
            "run_id": self.run_id,
            "task_id": task.id,
            "task_name": task.name,
            "task_type": task.type,
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "stdout": stdout[:5000],   # Truncate long output
            "stderr": stderr[:5000],
            "error_message": error,
        })

    def _mark_remaining_cancelled(self, remaining: list[TaskDefinition]):
        for task in remaining:
            self._record_task(task, TaskStatus.CANCELLED, 0)
            self.task_finished.emit(task.id, TaskStatus.CANCELLED, 0, "Cancelled")

    def _build_webhook_payload(self, inventory) -> dict:
        return {
            "run_id": self.run_id,
            "profile_id": self.profile.profile_id,
            "profile_name": self.profile.name,
            "device": self.device.model_dump(),
            "inventory": inventory.model_dump() if inventory else None,
            "tasks": [dict(r) for r in self.repo.get_task_executions(self.run_id)],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _determine_final_status(succeeded: int, failed: int, skipped: int, total: int) -> str:
        if failed == 0:
            return RunStatus.COMPLETED
        if succeeded == 0:
            return RunStatus.FAILED
        return RunStatus.PARTIAL

    def _log(self, message: str):
        logger.info(message)
        self.log_line.emit(message)
