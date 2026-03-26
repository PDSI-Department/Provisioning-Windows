"""
Summary screen — post-provisioning recap.

Shows:
- Run status and duration
- Task results summary
- Inventory data overview
- Webhook status
- Actions: Export, New Run
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    ACCENT,
    BG_SECONDARY,
    BORDER,
    ERROR,
    FONT_MONO,
    FONT_SIZE_SM,
    STATUS_COLORS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


class SummaryScreen(QWidget):
    """Post-provisioning summary and actions."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("Provisioning Summary")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.content)
        layout.addWidget(scroll, stretch=1)

        # Action buttons
        actions = QHBoxLayout()

        export_btn = QPushButton("Export JSON")
        export_btn.clicked.connect(self._export)
        actions.addWidget(export_btn)

        actions.addStretch()

        new_run_btn = QPushButton("New Provisioning Run")
        new_run_btn.setObjectName("primaryButton")
        new_run_btn.clicked.connect(self._new_run)
        actions.addWidget(new_run_btn)

        layout.addLayout(actions)

    def on_enter(self):
        """Load run data and populate summary."""
        # Clear content
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        run_id = self.mw.last_run_id
        if not run_id:
            self.content_layout.addWidget(QLabel("No run data available"))
            return

        run = self.mw.repo.get_run(run_id)
        if not run:
            return

        # ── Run Overview Card ─────────────────────────────────
        overview = self._card("Run Overview")
        status = run.get("status", "?")
        color = STATUS_COLORS.get(status, TEXT_MUTED)

        self._add_row(overview, "Status", status.upper(), color, bold=True)
        self._add_row(overview, "Profile", run.get("profile_name", ""))
        self._add_row(overview, "Hostname", run.get("hostname", ""))
        self._add_row(overview, "Asset Tag", run.get("asset_tag", ""))
        self._add_row(overview, "User", run.get("user_name", ""))
        self._add_row(overview, "Department", run.get("department", ""))

        started = run.get("started_at", "")[:19].replace("T", " ")
        finished = run.get("finished_at", "")[:19].replace("T", " ")
        self._add_row(overview, "Started", started)
        self._add_row(overview, "Finished", finished)

        self.content_layout.addWidget(overview)

        # ── Task Results Card ─────────────────────────────────
        tasks_card = self._card("Task Results")

        succeeded = run.get("succeeded_tasks", 0)
        failed = run.get("failed_tasks", 0)
        skipped = run.get("skipped_tasks", 0)
        total = run.get("total_tasks", 0)

        stats_text = f"✓ {succeeded}  ✗ {failed}  ⊘ {skipped}  /  {total} total"
        stats = QLabel(stats_text)
        stats.setStyleSheet(f"font-family: {FONT_MONO}; font-size: 15px; padding: 4px 0;")
        tasks_card.layout().addWidget(stats)

        # Individual task results
        task_execs = self.mw.repo.get_task_executions(run_id)
        for tex in task_execs:
            t_status = tex.get("status", "?")
            t_color = STATUS_COLORS.get(t_status, TEXT_MUTED)
            t_duration = tex.get("duration_ms", 0)
            dur_str = f" ({t_duration / 1000:.1f}s)" if t_duration else ""
            err = tex.get("error_message", "")
            err_str = f" — {err}" if err and t_status == "failed" else ""

            row = QLabel(f"  {t_status:>9}  {tex.get('task_name', '')}{dur_str}{err_str}")
            row.setStyleSheet(
                f"color: {t_color}; font-family: {FONT_MONO}; font-size: {FONT_SIZE_SM}px;"
            )
            tasks_card.layout().addWidget(row)

        self.content_layout.addWidget(tasks_card)

        # ── Inventory Preview ─────────────────────────────────
        inv_card = self._card("Device Inventory (Preview)")
        # Fetch inventory from DB — simplified display
        inv_rows = self.mw.repo.db.conn.execute(
            "SELECT * FROM device_inventory WHERE run_id = ? LIMIT 1", (run_id,)
        ).fetchone()

        if inv_rows:
            inv = dict(inv_rows)
            self._add_row(inv_card, "Manufacturer", inv.get("manufacturer", ""))
            self._add_row(inv_card, "Model", inv.get("model", ""))
            self._add_row(inv_card, "Serial", inv.get("serial_number", ""))
            self._add_row(inv_card, "CPU", inv.get("cpu", ""))
            self._add_row(inv_card, "RAM", f"{inv.get('ram_gb', 0)} GB")
            self._add_row(inv_card, "OS", f"{inv.get('os_name', '')} {inv.get('os_build', '')}")
            self._add_row(inv_card, "Hostname", inv.get("hostname", ""))
        else:
            inv_card.layout().addWidget(
                QLabel("No inventory data collected")
            )

        self.content_layout.addWidget(inv_card)

        # ── Webhook Status ────────────────────────────────────
        wh_card = self._card("Webhook")
        wh_rows = self.mw.repo.db.conn.execute(
            "SELECT status, retry_count, last_error FROM webhook_queue WHERE run_id = ?",
            (run_id,),
        ).fetchall()

        if wh_rows:
            for wh in wh_rows:
                wh_status = wh["status"]
                wh_color = {"sent": ACCENT, "pending": WARNING, "failed": ERROR}.get(
                    wh_status, TEXT_MUTED
                )
                self._add_row(wh_card, "Status", wh_status.upper(), wh_color)
                if wh["retry_count"]:
                    self._add_row(wh_card, "Retries", str(wh["retry_count"]))
                if wh["last_error"]:
                    self._add_row(wh_card, "Last Error", wh["last_error"], ERROR)
        else:
            sent_label = QLabel("Sent directly (no queue entry)")
            sent_label.setStyleSheet(f"color: {ACCENT};")
            wh_card.layout().addWidget(sent_label)

        self.content_layout.addWidget(wh_card)

    # ── Helpers ───────────────────────────────────────────────

    def _card(self, title: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            f"background: {BG_SECONDARY}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; padding: 16px;"
        )
        layout = QVBoxLayout(card)
        layout.setSpacing(6)

        header = QLabel(title)
        header.setStyleSheet("font-size: 15px; font-weight: 600; padding-bottom: 4px;")
        layout.addWidget(header)

        return card

    def _add_row(
        self, parent: QWidget, label: str, value: str,
        color: str = TEXT_PRIMARY, bold: bool = False,
    ):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
        lbl.setFixedWidth(120)
        row.addWidget(lbl)

        val = QLabel(value)
        weight = "font-weight: 700;" if bold else ""
        val.setStyleSheet(f"color: {color}; {weight}")
        row.addWidget(val, stretch=1)

        parent.layout().addLayout(row)

    def _export(self):
        """Export run data as JSON to file."""
        run_id = self.mw.last_run_id
        if not run_id:
            return

        run = self.mw.repo.get_run(run_id)
        tasks = self.mw.repo.get_task_executions(run_id)

        export_data = {
            "run": run,
            "tasks": tasks,
        }

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Provisioning Data",
            f"provisioning_{run_id[:8]}.json",
            "JSON Files (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    def _new_run(self):
        """Reset state and go back to profile selection."""
        self.mw.selected_profile = None
        self.mw.device_metadata = None
        self.mw.task_overrides = {}
        self.mw.last_run_id = None
        self.mw.navigate_to(self.mw.HOME)
