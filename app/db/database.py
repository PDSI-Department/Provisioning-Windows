"""
SQLite database manager — connection handling and schema migration.

Design notes:
- Raw sqlite3 chosen over SQLAlchemy: simpler PyInstaller bundling,
  fewer dependencies, and our schema is straightforward enough.
- WAL mode for better concurrent read performance.
- All timestamps stored as ISO 8601 strings (UTC).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Provisioning run: one row per provisioning session
CREATE TABLE IF NOT EXISTS provisioning_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL UNIQUE,       -- UUID
    profile_id      TEXT    NOT NULL,
    profile_name    TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'running',  -- running/completed/partial/failed/cancelled
    asset_tag       TEXT,
    user_name       TEXT,
    department      TEXT,
    location        TEXT,
    hostname        TEXT,
    notes           TEXT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    total_tasks     INTEGER DEFAULT 0,
    succeeded_tasks INTEGER DEFAULT 0,
    failed_tasks    INTEGER DEFAULT 0,
    skipped_tasks   INTEGER DEFAULT 0,
    kit_path        TEXT
);

-- Task execution: one row per task within a run
CREATE TABLE IF NOT EXISTS task_executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL REFERENCES provisioning_runs(run_id),
    task_id         TEXT    NOT NULL,
    task_name       TEXT    NOT NULL,
    task_type       TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending/running/success/failed/skipped/cancelled
    started_at      TEXT,
    finished_at     TEXT,
    duration_ms     INTEGER,
    exit_code       INTEGER,
    stdout          TEXT,
    stderr          TEXT,
    error_message   TEXT,
    retry_attempt   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_task_exec_run ON task_executions(run_id);

-- Device inventory snapshot
CREATE TABLE IF NOT EXISTS device_inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    REFERENCES provisioning_runs(run_id),
    manufacturer    TEXT,
    model           TEXT,
    serial_number   TEXT,
    cpu             TEXT,
    ram_gb          REAL,
    storage_json    TEXT,           -- JSON array of disk info
    gpu             TEXT,
    os_name         TEXT,
    os_version      TEXT,
    os_build        TEXT,
    hostname        TEXT,
    ip_addresses    TEXT,           -- JSON array
    mac_addresses   TEXT,           -- JSON array
    software_json   TEXT,           -- JSON array of installed software
    collected_at    TEXT    NOT NULL
);

-- Webhook retry queue
CREATE TABLE IF NOT EXISTS webhook_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL,
    payload_json    TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending/sent/failed
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 5,
    last_attempt_at TEXT,
    last_error      TEXT,
    created_at      TEXT    NOT NULL,
    sent_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_webhook_status ON webhook_queue(status);

-- Simple key-value app settings
CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT NOT NULL
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    level           TEXT    NOT NULL,       -- INFO/WARN/ERROR
    category        TEXT    NOT NULL,       -- provisioning/task/webhook/app
    message         TEXT    NOT NULL,
    details_json    TEXT                    -- optional extra data
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT    NOT NULL
);
"""


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        """Create tables if they don't exist and apply migrations."""
        logger.info("Initializing database at %s", self.db_path)
        self.conn.executescript(SCHEMA_SQL)

        # Record schema version
        existing = self.conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if existing is None or existing["version"] < SCHEMA_VERSION:
            from datetime import datetime, timezone

            self.conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()
        logger.info("Database initialized (schema v%d)", SCHEMA_VERSION)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
