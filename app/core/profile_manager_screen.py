"""
Profile Manager screen — create, edit, duplicate, delete provisioning profiles.

Layout: left sidebar (profile list) + right panel (editor form).
"""

from __future__ import annotations

import copy
import logging
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.enums import TaskType
from app.models.profile_definition import ProfileDefinition
from app.models.task_definition import TaskDefinition
from app.ui.theme import (
    ACCENT,
    BG_PRIMARY,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    ERROR,
    FONT_MONO,
    FONT_SIZE_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

logger = logging.getLogger(__name__)


class ProfileManagerScreen(QWidget):
    """Manage provisioning profiles — CRUD + task editing."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._editing_profile: ProfileDefinition | None = None
        self._current_profile_id: str | None = None
        self._editing_tasks: list[dict] = []
        self._is_new = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left sidebar ──────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"background: {BG_SECONDARY};")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 20, 16, 16)
        sb.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(self._label("Profiles", 18, bold=True))
        hdr.addStretch()
        add_btn = QPushButton("+")
        add_btn.setFixedSize(32, 32)
        add_btn.setStyleSheet(
            f"background:{ACCENT};color:{BG_PRIMARY};font-size:18px;"
            f"font-weight:700;border-radius:6px;border:none;"
        )
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._create_new)
        hdr.addWidget(add_btn)
        sb.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;background:transparent;")
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background:transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(4)
        scroll.setWidget(self.list_widget)
        sb.addWidget(scroll, stretch=1)

        back = QPushButton("← Dashboard")
        back.clicked.connect(lambda: self.mw.navigate_to(self.mw.HOME))
        sb.addWidget(back)
        layout.addWidget(sidebar)

        # ── Right editor ──────────────────────────────────────
        right = QWidget()
        self.right_layout = QVBoxLayout(right)
        self.right_layout.setContentsMargins(32, 24, 32, 24)
        self.right_layout.setSpacing(14)

        self.placeholder = QLabel("Select a profile or create a new one")
        self.placeholder.setStyleSheet(f"color:{TEXT_MUTED};font-size:15px;padding:60px;")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(self.placeholder)

        self.form_widget = QWidget()
        self.form_widget.hide()
        fl = QVBoxLayout(self.form_widget)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(10)

        # Meta fields
        meta = QFormLayout()
        meta.setSpacing(8)
        self.f_name = QLineEdit()
        meta.addRow("Name:", self.f_name)
        self.f_desc = QLineEdit()
        meta.addRow("Description:", self.f_desc)
        self.f_icon = QComboBox()
        self.f_icon.addItems(["briefcase", "palette", "code", "settings", "computer"])
        meta.addRow("Icon:", self.f_icon)
        self.f_author = QComboBox()
        self.f_author.addItems(["IT Support", "PDSI"])
        self.f_author.setCurrentText("IT Support")
        meta.addRow("Author:", self.f_author)
        self.auto_id_hint = QLabel("Profile ID dibuat otomatis oleh sistem")
        self.auto_id_hint.setStyleSheet(f"color:{TEXT_MUTED};font-size:{FONT_SIZE_SM}px;")
        meta.addRow("", self.auto_id_hint)
        fl.addLayout(meta)

        # Tasks header
        th = QHBoxLayout()
        th.addWidget(self._label("Tasks", 15, bold=True))
        th.addStretch()
        at = QPushButton("+ Add Task")
        at.setStyleSheet("font-size:12px;padding:4px 12px;")
        at.clicked.connect(self._add_task)
        th.addWidget(at)
        fl.addLayout(th)

        ts = QScrollArea()
        ts.setWidgetResizable(True)
        self.tasks_widget = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_widget)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tasks_layout.setSpacing(3)
        ts.setWidget(self.tasks_widget)
        fl.addWidget(ts, stretch=1)

        # Actions
        acts = QHBoxLayout()
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet(f"background:{ERROR};color:white;")
        del_btn.clicked.connect(self._delete)
        acts.addWidget(del_btn)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._duplicate)
        acts.addWidget(dup_btn)
        acts.addStretch()
        save_btn = QPushButton("Save Profile")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        acts.addWidget(save_btn)
        fl.addLayout(acts)

        self.right_layout.addWidget(self.form_widget)
        layout.addWidget(right, stretch=1)

    # ── Refresh ───────────────────────────────────────────────

    def on_enter(self):
        self._refresh_list()

    def _refresh_list(self):
        self._clear_layout(self.list_layout)
        for p in self.mw.profile_loader.load_profiles():
            active = self._editing_profile and self._editing_profile.profile_id == p.profile_id
            row = self._profile_row(p, active)
            self.list_layout.addWidget(row)

    def _refresh_tasks(self):
        self._clear_layout(self.tasks_layout)
        for i, td in enumerate(self._editing_tasks):
            self.tasks_layout.addWidget(self._task_row(i, td))

    # ── Profile CRUD ──────────────────────────────────────────

    def _load(self, profile: ProfileDefinition):
        self._editing_profile = profile
        self._current_profile_id = profile.profile_id
        self._is_new = False
        self._editing_tasks = [t.model_dump() for t in profile.tasks]
        self.placeholder.hide()
        self.form_widget.show()
        self.f_name.setText(profile.name)
        self.f_desc.setText(profile.description)
        author_idx = self.f_author.findText(profile.author)
        if author_idx >= 0:
            self.f_author.setCurrentIndex(author_idx)
        else:
            self.f_author.addItem(profile.author)
            self.f_author.setCurrentText(profile.author)
        idx = self.f_icon.findText(profile.icon)
        if idx >= 0:
            self.f_icon.setCurrentIndex(idx)
        self._refresh_tasks()
        self._refresh_list()

    def _create_new(self):
        self._editing_profile = None
        self._current_profile_id = None
        self._is_new = True
        self._editing_tasks = []
        self.placeholder.hide()
        self.form_widget.show()
        self.f_name.setText("")
        self.f_desc.setText("")
        self.f_author.setCurrentText("IT Support")
        self.f_icon.setCurrentIndex(0)
        self._refresh_tasks()

    def _duplicate(self):
        if not self._editing_profile:
            return
        self._editing_profile = None
        self._current_profile_id = None
        self._is_new = True
        self._editing_tasks = copy.deepcopy(self._editing_tasks)
        self.f_name.setText(self.f_name.text().strip() + " (Copy)")

    def _save(self):
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Profile name wajib diisi.")
            return

        # Keep stable profile ID for existing profile, auto-generate for new profile.
        profile_ids = {p.profile_id for p in self.mw.profile_loader.load_profiles()}
        if self._current_profile_id:
            profile_ids.discard(self._current_profile_id)
            pid = self._current_profile_id
        else:
            pid = self._make_unique_id(name, profile_ids, prefix="profile")

        tasks = []
        task_ids: set[str] = set()
        for i, td in enumerate(self._editing_tasks):
            td = dict(td)
            task_name = str(td.get("name", "")).strip()
            if not task_name:
                QMessageBox.warning(self, "Validation", "Nama task tidak boleh kosong.")
                return
            original_id = str(td.get("id", "")).strip()
            if original_id and original_id not in task_ids:
                task_id = original_id
            else:
                task_id = self._make_unique_id(task_name, task_ids, prefix="task")
            td["id"] = task_id
            td["order"] = (i + 1) * 10
            task_ids.add(task_id)
            try:
                tasks.append(TaskDefinition.model_validate(td))
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Task Error",
                    f"Invalid task '{td.get('name', '?')}': {exc}",
                )
                return

        profile = ProfileDefinition(
            profile_id=pid,
            name=name,
            description=self.f_desc.text().strip(),
            icon=self.f_icon.currentText(),
            author=self.f_author.currentText().strip(),
            tasks=tasks,
        )
        try:
            self.mw.profile_loader.save_profile(profile)
            self._editing_profile = profile
            self._current_profile_id = profile.profile_id
            self._is_new = False
            self._refresh_list()
            self.mw.repo.audit("INFO", "profile", f"Profile saved: {pid}")
            QMessageBox.information(self, "Saved", f"Profile '{name}' saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete(self):
        if not self._editing_profile or self._is_new:
            return
        pid = self._editing_profile.profile_id
        if QMessageBox.question(
            self, "Confirm", f"Delete '{self._editing_profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            deleted = self.mw.profile_loader.delete_profile(pid)
            if not deleted:
                QMessageBox.warning(
                    self,
                    "Cannot Delete",
                    "Profile ini bukan local override, jadi tidak bisa dihapus dari sini.",
                )
                return
            self._editing_profile = None
            self._current_profile_id = None
            self.form_widget.hide()
            self.placeholder.show()
            self._refresh_list()

    # ── Task Operations ───────────────────────────────────────

    def _add_task(self):
        dlg = TaskEditDialog(self, None, self.mw.profile_loader.list_packages())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["order"] = (len(self._editing_tasks) + 1) * 10
            self._editing_tasks.append(data)
            self._refresh_tasks()

    def _edit_task(self, index: int):
        dlg = TaskEditDialog(self, self._editing_tasks[index], self.mw.profile_loader.list_packages())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._editing_tasks[index] = dlg.get_data()
            self._refresh_tasks()

    def _move_task(self, index: int, direction: int):
        ni = index + direction
        if 0 <= ni < len(self._editing_tasks):
            self._editing_tasks[index], self._editing_tasks[ni] = (
                self._editing_tasks[ni], self._editing_tasks[index]
            )
            for i, t in enumerate(self._editing_tasks):
                t["order"] = (i + 1) * 10
            self._refresh_tasks()

    def _remove_task(self, index: int):
        del self._editing_tasks[index]
        self._refresh_tasks()

    # ── UI Builders ───────────────────────────────────────────

    def _profile_row(self, p: ProfileDefinition, active: bool) -> QWidget:
        w = QWidget()
        bg = BG_TERTIARY if active else "transparent"
        bdr = ACCENT if active else "transparent"
        w.setStyleSheet(f"background:{bg};border-left:3px solid {bdr};border-radius:4px;")
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(10, 8, 10, 8)
        vl.setSpacing(2)
        vl.addWidget(self._label(p.name, 13, bold=True))
        vl.addWidget(self._label(f"{len(p.get_enabled_tasks())} tasks", FONT_SIZE_SM, color=TEXT_MUTED))
        w.mousePressEvent = lambda e, pr=p: self._load(pr)
        return w

    def _task_row(self, idx: int, td: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_SECONDARY};border-radius:4px;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(10, 5, 6, 5)

        hl.addWidget(self._label(f"{td.get('order',0):>3}", FONT_SIZE_SM, mono=True, color=TEXT_MUTED))
        n = QLabel(td.get("name", "?"))
        n.setStyleSheet("font-size:12px;")
        hl.addWidget(n, stretch=1)
        hl.addWidget(self._badge(td.get("type", "?")))

        for text, cb in [("Edit", lambda c, i=idx: self._edit_task(i)),
                         ("↑", lambda c, i=idx: self._move_task(i, -1)),
                         ("↓", lambda c, i=idx: self._move_task(i, 1))]:
            b = QPushButton(text)
            b.setFixedSize(36 if len(text) > 1 else 26, 24)
            b.setStyleSheet("font-size:11px;padding:0;")
            b.clicked.connect(cb)
            hl.addWidget(b)

        rm = QPushButton("✕")
        rm.setFixedSize(24, 24)
        rm.setStyleSheet(f"color:{ERROR};font-size:13px;padding:0;")
        rm.clicked.connect(lambda c, i=idx: self._remove_task(i))
        hl.addWidget(rm)
        return w

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _label(text, size=13, bold=False, color=TEXT_PRIMARY, mono=False) -> QLabel:
        lbl = QLabel(str(text))
        fw = "font-weight:700;" if bold else ""
        ff = f"font-family:{FONT_MONO};" if mono else ""
        lbl.setStyleSheet(f"color:{color};font-size:{size}px;{fw}{ff}")
        return lbl

    @staticmethod
    def _badge(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{TEXT_MUTED};font-family:{FONT_MONO};font-size:10px;"
            f"background:{BORDER};padding:1px 6px;border-radius:3px;"
        )
        return lbl

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

    @classmethod
    def _make_unique_id(cls, text: str, used_ids: set[str], prefix: str) -> str:
        base = cls._slugify(text) or prefix
        candidate = base
        n = 2
        while candidate in used_ids:
            candidate = f"{base}-{n}"
            n += 1
        return candidate


class TaskEditDialog(QDialog):
    """Dialog for adding/editing a single task."""

    def __init__(self, parent, task_data: dict | None, packages: list):
        super().__init__(parent)
        self.setWindowTitle("Edit Task" if task_data else "Add Task")
        self.setMinimumSize(520, 560)
        self.setStyleSheet(f"background:{BG_PRIMARY};color:{TEXT_PRIMARY};")

        self._data = task_data or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.f_name = QLineEdit(self._data.get("name", ""))
        form.addRow("Name:", self.f_name)
        auto_task_id_note = QLabel("Task ID dibuat otomatis oleh sistem")
        auto_task_id_note.setStyleSheet(f"color:{TEXT_MUTED};font-size:{FONT_SIZE_SM}px;")
        form.addRow("", auto_task_id_note)

        self.f_type = QComboBox()
        self.f_type.addItems([t.value for t in TaskType])
        if self._data.get("type"):
            idx = self.f_type.findText(self._data["type"])
            if idx >= 0:
                self.f_type.setCurrentIndex(idx)
        else:
            idx = self.f_type.findText(TaskType.EXE_INSTALLER.value)
            if idx >= 0:
                self.f_type.setCurrentIndex(idx)
        self.f_type.currentTextChanged.connect(self._on_type_change)
        form.addRow("Type:", self.f_type)

        self.f_package = QComboBox()
        self.f_package.addItem("(none)", "")
        for pkg in packages:
            self.f_package.addItem(f"{pkg.name} ({pkg.package_id})", pkg.package_id)
        if not packages:
            self.f_package.addItem("No package found (import dari Package Sources)", "")
        if self._data.get("package_ref"):
            idx = self.f_package.findData(self._data["package_ref"])
            if idx >= 0:
                self.f_package.setCurrentIndex(idx)
        form.addRow("Package:", self.f_package)

        self.f_command = QTextEdit()
        self.f_command.setMaximumHeight(80)
        self.f_command.setPlainText(self._data.get("command", "") or "")
        self.f_command.setPlaceholderText("PowerShell command (inline)")
        form.addRow("Command:", self.f_command)

        self.f_path = QLineEdit(self._data.get("path", "") or "")
        self.f_path.setPlaceholderText("scripts/my_script.ps1")
        form.addRow("Script Path:", self.f_path)

        self.f_winget = QLineEdit(self._data.get("winget_id", "") or "")
        self.f_winget.setPlaceholderText("e.g. Google.Chrome")
        form.addRow("Winget ID:", self.f_winget)

        self.f_timeout = QSpinBox()
        self.f_timeout.setRange(10, 3600)
        self.f_timeout.setValue(self._data.get("timeout", 300))
        self.f_timeout.setSuffix(" sec")
        form.addRow("Timeout:", self.f_timeout)

        self.f_retry = QSpinBox()
        self.f_retry.setRange(0, 10)
        self.f_retry.setValue(self._data.get("retry_count", 0))
        form.addRow("Retries:", self.f_retry)

        self.f_continue = QCheckBox("Continue on error")
        self.f_continue.setChecked(self._data.get("continue_on_error", False))
        form.addRow("", self.f_continue)

        self.f_admin = QCheckBox("Requires admin")
        self.f_admin.setChecked(self._data.get("requires_admin", True))
        form.addRow("", self.f_admin)

        self.f_enabled = QCheckBox("Enabled")
        self.f_enabled.setChecked(self._data.get("enabled", True))
        form.addRow("", self.f_enabled)

        dr = self._data.get("detect_rule") or {}
        self.f_dr_type = QComboBox()
        self.f_dr_type.addItems(["", "path_exists", "registry_exists", "winget_list", "command_exit_code"])
        self.f_dr_type.setCurrentText(dr.get("type", ""))
        form.addRow("Detect Type:", self.f_dr_type)

        self.f_dr_val = QLineEdit(dr.get("value", ""))
        self.f_dr_val.setPlaceholderText("C:\\Program Files\\App\\app.exe")
        form.addRow("Detect Value:", self.f_dr_val)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._on_type_change(self.f_type.currentText())

    def _on_type_change(self, tt: str):
        self.f_package.setVisible(tt in ("exe_installer", "msi_installer"))
        self.f_command.setVisible(tt == "powershell_command")
        self.f_path.setVisible(tt == "powershell_script")
        self.f_winget.setVisible(tt == "winget_install")

    def get_data(self) -> dict:
        dr = None
        if self.f_dr_type.currentText() and self.f_dr_val.text().strip():
            dr = {"type": self.f_dr_type.currentText(), "value": self.f_dr_val.text().strip()}
        return {
            "id": (self._data.get("id") or "").strip(),
            "name": self.f_name.text().strip(),
            "type": self.f_type.currentText(),
            "package_ref": self.f_package.currentData() or None,
            "command": self.f_command.toPlainText().strip() or None,
            "path": self.f_path.text().strip() or None,
            "winget_id": self.f_winget.text().strip() or None,
            "timeout": self.f_timeout.value(),
            "retry_count": self.f_retry.value(),
            "continue_on_error": self.f_continue.isChecked(),
            "requires_admin": self.f_admin.isChecked(),
            "enabled": self.f_enabled.isChecked(),
            "detect_rule": dr,
            "order": self._data.get("order", 0),
            "arguments": self._data.get("arguments", {}),
        }
