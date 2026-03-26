# WinProv — Windows Provisioning Tool
## Architecture Blueprint

---

## A. Arsitektur Sistem

### Gambaran Umum

```
┌─────────────────────────────────────────────────────────┐
│                    PySide6 UI Layer                      │
│  Home │ Profile │ Metadata │ Review │ Exec │ Summary     │
├─────────────────────────────────────────────────────────┤
│                  Orchestrator (Python)                    │
│  Profile Loader │ Task Queue │ State Machine │ Signals    │
├──────────┬──────────┬───────────┬───────────────────────┤
│ PS Runner│ Inventory│ Webhook   │ Kit Detector           │
│ (subproc)│ (PS+Py)  │ (httpx)   │ (pathlib)              │
├──────────┴──────────┴───────────┴───────────────────────┤
│              SQLite (runtime state/history)               │
├─────────────────────────────────────────────────────────┤
│          JSON Files (profiles/packages/config)           │
│          [Local App Dir] + [External SSD Kit]            │
└─────────────────────────────────────────────────────────┘
```

### Prinsip Arsitektur

1. **JSON = Source of Truth** untuk konfigurasi deklaratif (profile, package, app config)
2. **SQLite = Runtime State** untuk histori, log, audit, webhook queue
3. **PowerShell = Execution Engine** untuk task Windows-native
4. **Python = Orchestrator + UI Host** yang mengoordinasikan semua komponen
5. **Signal-based Communication** antara orchestrator dan UI via Qt signals
6. **Semi-offline First** — semua task bisa jalan tanpa internet kecuali webhook

### Keputusan Teknis

| Keputusan | Pilihan | Alasan |
|---|---|---|
| ORM vs raw SQL | **Raw sqlite3 + dataclass** | Lebih ringan untuk PyInstaller bundle, SQLite usage sederhana, menghindari SQLAlchemy overhead |
| HTTP client | **httpx** | Async-capable, timeout handling lebih baik, modern API |
| Validation | **Pydantic v2** | Validasi JSON config kuat, serialization gratis, error messages jelas |
| UI framework | **PySide6** | LGPL license, Qt ecosystem matang, native look |
| Logging | **Python logging** | Cukup untuk kebutuhan ini, bisa dual-output ke file dan UI |

---

## B. Struktur Folder

```
winprov/
├── main.py                          # Entry point
├── pyproject.toml                   # Project metadata + dependencies
├── build.spec                       # PyInstaller spec file
├── requirements.txt                 # Pip dependencies
│
├── app/
│   ├── __init__.py
│   │
│   ├── core/                        # Business logic layer
│   │   ├── __init__.py
│   │   ├── orchestrator.py          # Main provisioning orchestrator
│   │   ├── powershell_runner.py     # PowerShell execution engine
│   │   ├── inventory.py             # HW/SW inventory collection
│   │   ├── webhook.py               # Webhook sender + retry logic
│   │   ├── kit_detector.py          # SSD provisioning kit auto-detect
│   │   ├── profile_loader.py        # JSON profile/package loader
│   │   └── task_runner.py           # Task execution dispatcher
│   │
│   ├── db/                          # Database layer
│   │   ├── __init__.py
│   │   ├── database.py              # Connection manager + migrations
│   │   └── repository.py            # Data access methods
│   │
│   ├── models/                      # Data models (Pydantic + dataclass)
│   │   ├── __init__.py
│   │   ├── task_definition.py       # Task schema
│   │   ├── profile_definition.py    # Profile schema
│   │   ├── package_definition.py    # Package metadata schema
│   │   ├── app_config.py            # App config schema
│   │   ├── device_metadata.py       # Device info input model
│   │   ├── inventory_data.py        # Inventory result model
│   │   └── enums.py                 # Status, TaskType, etc.
│   │
│   ├── ui/                          # UI layer (PySide6)
│   │   ├── __init__.py
│   │   ├── main_window.py           # Main window + navigation
│   │   ├── theme.py                 # Colors, fonts, stylesheet
│   │   ├── widgets/                 # Reusable UI components
│   │   │   ├── __init__.py
│   │   │   ├── task_card.py
│   │   │   ├── progress_bar.py
│   │   │   └── log_viewer.py
│   │   └── screens/                 # Screen pages
│   │       ├── __init__.py
│   │       ├── home_screen.py
│   │       ├── profile_screen.py
│   │       ├── metadata_screen.py
│   │       ├── review_screen.py
│   │       ├── execution_screen.py
│   │       └── summary_screen.py
│   │
│   └── utils/                       # Utilities
│       ├── __init__.py
│       ├── logger.py                # Logging setup
│       ├── paths.py                 # Path resolution helpers
│       └── admin.py                 # Admin privilege checker
│
├── config/                          # Default app config (bundled)
│   └── app_config.json
│
├── profiles/                        # Built-in profiles (bundled)
│   └── staff-office.json
│
├── packages/                        # Built-in package metadata (bundled)
│   ├── GoogleChrome/
│   │   └── meta.json
│   └── SevenZip/
│       └── meta.json
│
├── scripts/                         # PowerShell helper scripts (bundled)
│   ├── collect_inventory.ps1
│   ├── rename_hostname.ps1
│   ├── configure_power.ps1
│   └── install_winget.ps1
│
├── assets/                          # Icons, images
│   └── icon.ico
│
└── tests/                           # Unit tests
    ├── __init__.py
    ├── test_orchestrator.py
    └── test_powershell_runner.py
```

---

## C. Tanggung Jawab Module

| Module | Tanggung Jawab |
|---|---|
| `main.py` | Bootstrap app, init DB, init UI, start event loop |
| `orchestrator.py` | State machine provisioning: load profile → build task queue → execute tasks → collect inventory → send webhook → save history |
| `powershell_runner.py` | Menjalankan PS script/command via subprocess, capture output, handle timeout |
| `task_runner.py` | Dispatch task ke handler yang sesuai (winget/exe/msi/ps/python) |
| `inventory.py` | Kumpulkan data hardware + software via PS + WMI |
| `webhook.py` | Kirim JSON ke webhook URL, queue retry jika gagal |
| `kit_detector.py` | Scan semua drive letter, cari marker file, return kit path |
| `profile_loader.py` | Load + validate profile JSON + resolve package metadata |
| `database.py` | Create/migrate SQLite, provide connection |
| `repository.py` | CRUD operations untuk semua tabel |
| `models/*` | Pydantic models untuk validasi + serialization |
| `main_window.py` | QMainWindow dengan stacked widget navigation |
| `screens/*` | Masing-masing screen sebagai QWidget |
| `logger.py` | Setup rotating file handler + custom UI handler |
| `paths.py` | Resolve path relatif terhadap app dir / kit dir |
| `admin.py` | Check + request UAC elevation |

---

## D. Database Schema SQLite

Lihat `app/db/database.py` untuk implementasi lengkap. Ringkasan tabel:

### provisioning_runs
Setiap kali IT Support menjalankan provisioning = 1 row.

### task_executions
Setiap task yang dijalankan dalam 1 run = 1 row. FK ke provisioning_runs.

### device_inventory
Snapshot hardware/software setelah provisioning. FK ke provisioning_runs.

### webhook_queue
Antrian webhook yang perlu dikirim/retry.

### app_settings
Key-value store sederhana untuk preferences.

### audit_log
Log ringkas aktivitas penting.

---

## E. Format JSON

Lihat file-file di `config/`, `profiles/`, `packages/` untuk contoh lengkap.

---

## F. Flow Aplikasi

### F1. Provisioning End-to-End

```
User buka app
  → [Home Screen] tampilkan status kit, recent runs
  → [Profile Screen] pilih profile (dari bundled + kit)
  → [Metadata Screen] isi asset tag, user, dept, lokasi, hostname, notes
  → [Review Screen] tampilkan semua task yang akan dijalankan, bisa toggle
  → User klik "Start Provisioning"
  → [Execution Screen]:
      Orchestrator.start():
        1. Create provisioning_run record (status=running)
        2. Iterate task queue:
           for each task:
             a. Update UI: task status → running
             b. Check detect_rule (skip if already satisfied)
             c. Dispatch ke task_runner
             d. task_runner panggil handler sesuai tipe
             e. Capture result, update task_execution record
             f. If failed & !continue_on_error → abort
             g. Update UI: task status → success/failed/skipped
        3. Run inventory collection
        4. Save inventory to DB
        5. Build webhook payload
        6. Send webhook (or queue if offline)
        7. Update provisioning_run status → completed/partial
  → [Summary Screen] tampilkan ringkasan, bisa copy/export
```

### F2. PowerShell Execution Flow

```
task_runner receives PS task
  → powershell_runner.execute(script_path_or_command, args, timeout)
  → Build command:
      powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass
        -File script.ps1 -Arg1 val1
      OR
      powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass
        -Command "inline command here"
  → subprocess.run() with timeout, capture stdout+stderr
  → Parse exit code
  → Return TaskResult(status, output, error, duration)
```

### F3. Inventory Collection Flow

```
orchestrator triggers inventory
  → inventory.collect()
  → Run collect_inventory.ps1 (outputs JSON to stdout)
  → Parse JSON result
  → Merge with Python-collected data if needed
  → Return InventoryData model
  → Save to device_inventory table
```

### F4. Webhook + Retry Flow

```
webhook.send(payload)
  → POST to webhook_url with JSON
  → If success (2xx): mark sent, save to DB
  → If fail:
      Insert into webhook_queue (status=pending, retry_count=0)
      Log error
  → Background timer (every 60s):
      Query pending webhooks where retry_count < max_retries
      For each: attempt POST
        If success: update status=sent
        If fail: increment retry_count
        If retry_count >= max: update status=failed
```

---

## G. Desain UI

### Prinsip
- **Industrial/utilitarian** aesthetic — tools, not decoration
- Dark theme dengan accent color biru/teal untuk status
- Monospace font untuk log, sans-serif untuk label
- Setiap screen punya header jelas + action button di bawah
- Progress bar prominent di execution screen
- Realtime log auto-scroll

### Screen Layout

1. **Home**: Status kit (detected/not), recent provisioning runs, "Start New" button
2. **Profile Selection**: Card grid untuk tiap profile, klik untuk select
3. **Device Metadata**: Form fields — asset tag, user name, department (dropdown), location, hostname, notes
4. **Task Review**: Checklist semua task, bisa enable/disable per task, reorder
5. **Execution**: Overall progress bar, per-task status list (icon + name + status + duration), live log panel di bawah
6. **Summary**: Recap semua task results, inventory data, webhook status, "Export" dan "New Run" buttons

---

## I. Build & Packaging Notes

- Gunakan PyInstaller dengan `--onedir` (bukan `--onefile`) — lebih reliable untuk PySide6
- Bundle `config/`, `profiles/`, `packages/`, `scripts/` sebagai data files
- Set `--uac-admin` manifest agar app minta elevation saat launch
- Icon: `--icon=assets/icon.ico`
- Hidden imports: pastikan include `pydantic`, `httpx`, `PySide6.QtWidgets`, dll
- Test build di clean Windows VM sebelum distribusi

---

## J. Best Practices

### Error Handling
- Setiap task execution di-wrap try/except, error disimpan ke DB
- `continue_on_error` flag per task menentukan apakah abort atau lanjut
- PS runner punya timeout enforcement via subprocess

### Idempotency
- `detect_rule` pada setiap task memungkinkan skip jika sudah terpenuhi
- Contoh: check apakah Chrome sudah terinstall sebelum install ulang

### Audit Logging
- Setiap action penting (start run, task complete, webhook sent) dicatat di audit_log
- Dual output: file log + SQLite audit_log

### Security
- PowerShell dijalankan dengan `-NoProfile -NonInteractive -ExecutionPolicy Bypass`
- Tidak ada credential yang disimpan di JSON — webhook URL tanpa auth token di config, token disimpan terpisah
- App request UAC elevation saat startup
