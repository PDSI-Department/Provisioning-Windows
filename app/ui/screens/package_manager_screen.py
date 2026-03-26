"""
Package manager screen.

Allows IT to import/update local package sources from file/folder
and generate package metadata used by provisioning tasks.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.models.package_definition import PackageDefinition
from app.ui.theme import TEXT_MUTED


class PackageManagerScreen(QWidget):
    """Import and manage package sources + metadata."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._packages: list[PackageDefinition] = []
        self._current_package_id: str | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel("Package Source Manager")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        subtitle = QLabel(
            "Import source installer (file/folder), simpan metadata package, lalu pakai di task profile."
        )
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(subtitle)

        note = QLabel(
            "Catatan: gunakan hanya source installer legal/lisensi resmi."
        )
        note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        root.addWidget(note)

        body = QHBoxLayout()
        body.setSpacing(16)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(280)
        self.list_widget.itemSelectionChanged.connect(self._on_select)
        body.addWidget(self.list_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_wrap = QWidget()
        form = QVBoxLayout(form_wrap)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        fields = QFormLayout()
        fields.setSpacing(8)

        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("Display name")
        self.f_name.textChanged.connect(self._update_auto_id_preview)
        fields.addRow("Name:", self.f_name)

        self.id_preview = QLabel("Package ID dibuat otomatis oleh sistem")
        self.id_preview.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        fields.addRow("", self.id_preview)

        self.f_install_type = QComboBox()
        self.f_install_type.addItems(["exe_installer", "msi_installer", "winget_install"])
        self.f_install_type.currentTextChanged.connect(self._on_install_type_changed)
        fields.addRow("Install Type:", self.f_install_type)

        source_row = QHBoxLayout()
        self.f_source = QLineEdit()
        self.f_source.setPlaceholderText("Path file/folder source installer")
        source_row.addWidget(self.f_source, stretch=1)
        pick_file = QPushButton("File")
        pick_file.clicked.connect(self._pick_file)
        source_row.addWidget(pick_file)
        pick_dir = QPushButton("Folder")
        pick_dir.clicked.connect(self._pick_dir)
        source_row.addWidget(pick_dir)
        fields.addRow("Source:", source_row)

        self.f_installer_rel = QLineEdit()
        self.f_installer_rel.setPlaceholderText("Optional: relative path installer di dalam source")
        fields.addRow("Installer Rel Path:", self.f_installer_rel)

        self.f_args = QLineEdit()
        self.f_args.setPlaceholderText("/S atau /quiet /norestart")
        fields.addRow("Installer Args:", self.f_args)

        self.f_winget = QLineEdit()
        self.f_winget.setPlaceholderText("e.g. Google.Chrome")
        fields.addRow("Winget ID:", self.f_winget)

        self.f_publisher = QComboBox()
        self.f_publisher.setEditable(True)
        fields.addRow("Publisher:", self.f_publisher)

        self.f_desc = QLineEdit()
        fields.addRow("Description:", self.f_desc)

        self.f_detect = QLineEdit()
        self.f_detect.setPlaceholderText(r"C:\Program Files\App\app.exe")
        fields.addRow("Detect Path:", self.f_detect)

        form.addLayout(fields)
        form.addStretch()
        scroll.setWidget(form_wrap)
        body.addWidget(scroll, stretch=1)
        root.addLayout(body, stretch=1)

        actions = QHBoxLayout()
        back = QPushButton("← Dashboard")
        back.clicked.connect(lambda: self.mw.navigate_to(self.mw.HOME))
        actions.addWidget(back)

        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self._clear_form)
        actions.addWidget(clear_btn)

        actions.addStretch()

        delete_btn = QPushButton("Delete Package")
        delete_btn.clicked.connect(self._delete_package)
        actions.addWidget(delete_btn)

        save_btn = QPushButton("Import / Update Package")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_package)
        actions.addWidget(save_btn)

        root.addLayout(actions)

        self._on_install_type_changed(self.f_install_type.currentText())

    def on_enter(self):
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        self._packages = self.mw.profile_loader.list_packages()
        self._refresh_publisher_options()
        for pkg in self._packages:
            item = QListWidgetItem(f"{pkg.name} ({pkg.package_id})")
            item.setData(Qt.ItemDataRole.UserRole, pkg.package_id)
            self.list_widget.addItem(item)

    def _on_select(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        package_id = items[0].data(Qt.ItemDataRole.UserRole)
        pkg = self.mw.profile_loader.load_package(package_id)
        if not pkg:
            return

        self._current_package_id = pkg.package_id
        self.f_name.setText(pkg.name)
        self.f_install_type.setCurrentText(pkg.install_type)
        self.f_winget.setText(pkg.winget_id or "")
        self.f_desc.setText(pkg.description)
        self.f_publisher.setCurrentText(pkg.publisher)
        self.f_args.setText(pkg.installer.arguments if pkg.installer else "")
        self.f_installer_rel.setText(pkg.installer.filename if pkg.installer else "")
        if pkg.detect_rule:
            self.f_detect.setText(pkg.detect_rule.value)
        else:
            self.f_detect.setText("")
        self._update_auto_id_preview()
        self._on_install_type_changed(self.f_install_type.currentText())

    def _on_install_type_changed(self, install_type: str):
        installer_based = install_type in {"exe_installer", "msi_installer"}
        self.f_source.setEnabled(installer_based)
        self.f_installer_rel.setEnabled(installer_based)
        self.f_args.setEnabled(installer_based)
        self.f_winget.setEnabled(install_type == "winget_install")

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose installer file",
            "",
            "Installers (*.exe *.msi *.msix *.msixbundle);;All Files (*.*)",
        )
        if path:
            self.f_source.setText(path)
            self.f_installer_rel.setText(Path(path).name)

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choose installer folder")
        if path:
            self.f_source.setText(path)

    def _clear_form(self):
        self._current_package_id = None
        self.f_name.clear()
        self.f_source.clear()
        self.f_installer_rel.clear()
        self.f_args.clear()
        self.f_winget.clear()
        self.f_desc.clear()
        self.f_publisher.setCurrentText("")
        self.f_detect.clear()
        self.f_install_type.setCurrentText("exe_installer")
        self._update_auto_id_preview()

    def _save_package(self):
        try:
            name = self.f_name.text().strip()
            if not name:
                QMessageBox.warning(self, "Validation", "Nama package wajib diisi.")
                return
            package_id = self._resolve_package_id(name)
            pkg = self.mw.profile_loader.import_package_source(
                package_id=package_id,
                name=name,
                source_path=self.f_source.text().strip() or None,
                install_type=self.f_install_type.currentText(),
                installer_arguments=self.f_args.text().strip(),
                winget_id=self.f_winget.text().strip(),
                description=self.f_desc.text().strip(),
                publisher=self.f_publisher.currentText().strip(),
                installer_relative_path=self.f_installer_rel.text().strip(),
                detect_path=self.f_detect.text().strip(),
            )
            self._current_package_id = pkg.package_id
            self._refresh_list()
            self._select_in_list(pkg.package_id)
            QMessageBox.information(self, "Success", f"Package '{pkg.name}' tersimpan.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_package(self):
        package_id = self._current_package_id or ""
        if not package_id:
            return
        ok = QMessageBox.question(
            self,
            "Confirm",
            f"Hapus package '{package_id}' dari local packages?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        deleted = self.mw.profile_loader.delete_package(package_id)
        if deleted:
            QMessageBox.information(self, "Deleted", f"Package '{package_id}' dihapus.")
            self._refresh_list()
            self._clear_form()
        else:
            QMessageBox.warning(
                self,
                "Not Found",
                "Package tidak ditemukan di local packages.",
            )

    def _select_in_list(self, package_id: str):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == package_id:
                self.list_widget.setCurrentRow(i)
                return

    def _refresh_publisher_options(self):
        publishers = sorted({(p.publisher or "").strip() for p in self._packages if p.publisher})
        current = self.f_publisher.currentText().strip() if hasattr(self, "f_publisher") else ""
        self.f_publisher.clear()
        self.f_publisher.addItem("")
        for pub in publishers:
            self.f_publisher.addItem(pub)
        if current:
            self.f_publisher.setCurrentText(current)

    def _update_auto_id_preview(self):
        if self._current_package_id:
            self.id_preview.setText("Package ID dikelola sistem secara otomatis.")
            return
        self.id_preview.setText("Package ID akan dibuat otomatis saat disimpan.")

    def _resolve_package_id(self, name: str) -> str:
        if self._current_package_id:
            return self._current_package_id
        used_ids = {p.package_id for p in self._packages}
        return self._make_unique_id(name, used_ids, "package")

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
