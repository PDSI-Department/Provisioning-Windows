"""Tests for core modules (platform-independent where possible)."""

import json
import tempfile
from pathlib import Path

import pytest

from app.models.app_config import AppConfig
from app.models.device_metadata import DeviceMetadata
from app.models.enums import TaskStatus, TaskType
from app.models.profile_definition import ProfileDefinition
from app.models.task_definition import TaskDefinition


# ── Model Tests ──────────────────────────────────────────────


def test_task_definition_resolve_arguments():
    task = TaskDefinition(
        id="test",
        name="Test",
        type=TaskType.POWERSHELL_SCRIPT,
        arguments={"Hostname": "{{hostname}}", "Static": "fixed"},
    )
    resolved = task.resolve_arguments({"hostname": "DP-PC-042"})
    assert resolved["Hostname"] == "DP-PC-042"
    assert resolved["Static"] == "fixed"


def test_profile_get_enabled_tasks():
    profile = ProfileDefinition(
        profile_id="test",
        name="Test",
        tasks=[
            TaskDefinition(id="a", name="A", type=TaskType.POWERSHELL_COMMAND, enabled=True, order=20),
            TaskDefinition(id="b", name="B", type=TaskType.POWERSHELL_COMMAND, enabled=False, order=10),
            TaskDefinition(id="c", name="C", type=TaskType.POWERSHELL_COMMAND, enabled=True, order=5),
        ],
    )
    enabled = profile.get_enabled_tasks()
    assert len(enabled) == 2
    assert enabled[0].id == "c"  # order=5 first
    assert enabled[1].id == "a"  # order=20 second


def test_device_metadata_to_context():
    meta = DeviceMetadata(
        asset_tag="DP-001",
        hostname="DP-PC-TEST",
        department="PDSI",
    )
    ctx = meta.to_context()
    assert ctx["asset_tag"] == "DP-001"
    assert ctx["hostname"] == "DP-PC-TEST"
    assert ctx["department"] == "PDSI"


def test_app_config_defaults():
    config = AppConfig()
    assert config.app.name == "WinProv"
    assert config.provisioning.default_task_timeout_seconds == 300
    assert config.webhook.max_retries == 5


def test_app_config_from_json():
    data = {
        "app": {"name": "Custom", "version": "2.0.0"},
        "webhook": {"url": "https://example.com/hook", "enabled": False},
    }
    config = AppConfig.model_validate(data)
    assert config.app.name == "Custom"
    assert config.webhook.enabled is False
    assert config.provisioning.default_task_timeout_seconds == 300  # default


# ── Profile Loading Tests ────────────────────────────────────


def test_load_profile_from_json_file():
    profile_data = {
        "profile_id": "test-profile",
        "name": "Test Profile",
        "description": "For testing",
        "tasks": [
            {
                "id": "task-1",
                "name": "Task One",
                "type": "powershell_command",
                "command": "echo hello",
                "timeout": 30,
                "order": 10,
            }
        ],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(profile_data, f)
        f.flush()

        data = json.loads(Path(f.name).read_text(encoding="utf-8"))
        profile = ProfileDefinition.model_validate(data)

    assert profile.profile_id == "test-profile"
    assert len(profile.tasks) == 1
    assert profile.tasks[0].type == TaskType.POWERSHELL_COMMAND


# ── Database Tests ───────────────────────────────────────────


def test_database_init_and_crud():
    from app.db.database import Database
    from app.db.repository import Repository

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        db.initialize()
        repo = Repository(db)

        # Create a run
        run_id = repo.create_run({
            "run_id": "test-run-001",
            "profile_id": "test",
            "profile_name": "Test Profile",
            "status": "running",
            "started_at": "2026-03-25T10:00:00Z",
        })
        assert run_id == "test-run-001"

        # Read back
        run = repo.get_run("test-run-001")
        assert run is not None
        assert run["profile_name"] == "Test Profile"

        # Update
        repo.update_run("test-run-001", {"status": "completed"})
        run = repo.get_run("test-run-001")
        assert run["status"] == "completed"

        # Recent runs
        runs = repo.get_recent_runs(limit=5)
        assert len(runs) == 1

        # Settings
        repo.set_setting("last_kit", "E:\\")
        assert repo.get_setting("last_kit") == "E:\\"
        assert repo.get_setting("nonexistent", "default") == "default"

        # Audit
        repo.audit("INFO", "test", "Test log entry", {"key": "value"})

        db.close()


# ── Kit Detector Tests ───────────────────────────────────────


def test_kit_detector_scan_path():
    from app.core.kit_detector import KitDetector

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # No marker → None
        detector = KitDetector()
        assert detector.scan_path(root) is None

        # Create marker + manifest
        (root / ".winprov-kit").touch()
        manifest = {
            "kit_name": "Test Kit",
            "kit_version": "1.0",
            "profiles_dir": "profiles",
            "packages_dir": "packages",
            "scripts_dir": "scripts",
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        kit = detector.scan_path(root)
        assert kit is not None
        assert kit.kit_name == "Test Kit"
        assert kit.profiles_dir == root / "profiles"
