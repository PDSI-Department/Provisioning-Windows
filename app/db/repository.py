"""
Repository — data access methods for all tables.

All methods accept/return plain dicts or primitives, not ORM objects.
This keeps the DB layer thin and easy to test.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.db.database import Database

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    """Data access layer on top of Database."""

    def __init__(self, db: Database):
        self.db = db

    # ── Provisioning Runs ─────────────────────────────────────────

    def create_run(self, run_data: dict) -> str:
        run_data.setdefault("started_at", _now())
        cols = ", ".join(run_data.keys())
        placeholders = ", ".join(["?"] * len(run_data))
        self.db.conn.execute(
            f"INSERT INTO provisioning_runs ({cols}) VALUES ({placeholders})",
            list(run_data.values()),
        )
        self.db.conn.commit()
        return run_data["run_id"]

    def update_run(self, run_id: str, updates: dict) -> None:
        sets = ", ".join(f"{k} = ?" for k in updates)
        self.db.conn.execute(
            f"UPDATE provisioning_runs SET {sets} WHERE run_id = ?",
            [*updates.values(), run_id],
        )
        self.db.conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM provisioning_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM provisioning_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Task Executions ───────────────────────────────────────────

    def create_task_execution(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = self.db.conn.execute(
            f"INSERT INTO task_executions ({cols}) VALUES ({placeholders})",
            list(data.values()),
        )
        self.db.conn.commit()
        return cursor.lastrowid

    def update_task_execution(self, row_id: int, updates: dict) -> None:
        sets = ", ".join(f"{k} = ?" for k in updates)
        self.db.conn.execute(
            f"UPDATE task_executions SET {sets} WHERE id = ?",
            [*updates.values(), row_id],
        )
        self.db.conn.commit()

    def get_task_executions(self, run_id: str) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM task_executions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Inventory ─────────────────────────────────────────────────

    def save_inventory(self, run_id: str, inventory: dict) -> int:
        data = {
            "run_id": run_id,
            "manufacturer": inventory.get("manufacturer", ""),
            "model": inventory.get("model", ""),
            "serial_number": inventory.get("serial_number", ""),
            "cpu": inventory.get("cpu", ""),
            "ram_gb": inventory.get("ram_gb", 0),
            "storage_json": json.dumps(inventory.get("storage", [])),
            "gpu": inventory.get("gpu", ""),
            "os_name": inventory.get("os_name", ""),
            "os_version": inventory.get("os_version", ""),
            "os_build": inventory.get("os_build", ""),
            "hostname": inventory.get("hostname", ""),
            "ip_addresses": json.dumps(inventory.get("ip_addresses", [])),
            "mac_addresses": json.dumps(inventory.get("mac_addresses", [])),
            "software_json": json.dumps(inventory.get("installed_software", [])),
            "collected_at": _now(),
        }
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = self.db.conn.execute(
            f"INSERT INTO device_inventory ({cols}) VALUES ({placeholders})",
            list(data.values()),
        )
        self.db.conn.commit()
        return cursor.lastrowid

    # ── Webhook Queue ─────────────────────────────────────────────

    def enqueue_webhook(self, run_id: str, payload: dict, max_retries: int = 5) -> int:
        data = {
            "run_id": run_id,
            "payload_json": json.dumps(payload),
            "status": "pending",
            "max_retries": max_retries,
            "created_at": _now(),
        }
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = self.db.conn.execute(
            f"INSERT INTO webhook_queue ({cols}) VALUES ({placeholders})",
            list(data.values()),
        )
        self.db.conn.commit()
        return cursor.lastrowid

    def get_pending_webhooks(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM webhook_queue WHERE status = 'pending' AND retry_count < max_retries"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_webhook(self, wh_id: int, updates: dict) -> None:
        sets = ", ".join(f"{k} = ?" for k in updates)
        self.db.conn.execute(
            f"UPDATE webhook_queue SET {sets} WHERE id = ?",
            [*updates.values(), wh_id],
        )
        self.db.conn.commit()

    # ── Audit Log ─────────────────────────────────────────────────

    def audit(self, level: str, category: str, message: str, details: dict | None = None) -> None:
        self.db.conn.execute(
            "INSERT INTO audit_log (timestamp, level, category, message, details_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (_now(), level, category, message, json.dumps(details) if details else None),
        )
        self.db.conn.commit()

    # ── App Settings ──────────────────────────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.db.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, _now()),
        )
        self.db.conn.commit()
