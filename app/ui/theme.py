"""
UI Theme — dark industrial/utilitarian aesthetic for IT tooling.

Design rationale:
- Dark background reduces eye strain during long provisioning sessions
- High contrast text for readability
- Teal accent for active/success states
- Orange/red for warnings and errors
- Monospace font for logs and technical data
- Minimal decoration — this is a tool, not a consumer app
"""

# ── Color Palette ─────────────────────────────────────────────

BG_PRIMARY = "#1a1b1e"      # Main background
BG_SECONDARY = "#25262b"    # Cards, panels
BG_TERTIARY = "#2c2e33"     # Input fields, hover states
BG_ELEVATED = "#373a40"     # Tooltips, dropdowns

TEXT_PRIMARY = "#e4e5e7"     # Main text
TEXT_SECONDARY = "#909296"   # Subdued text
TEXT_MUTED = "#5c5f66"       # Disabled, hints

ACCENT = "#20c997"           # Teal — primary action, success
ACCENT_HOVER = "#12b886"
ACCENT_DIM = "#0ca678"

WARNING = "#fd7e14"          # Orange
ERROR = "#ff6b6b"            # Red
INFO = "#4dabf7"             # Blue

BORDER = "#373a40"
BORDER_FOCUS = "#20c997"

# ── Status Colors ─────────────────────────────────────────────

STATUS_COLORS = {
    "pending": TEXT_MUTED,
    "running": INFO,
    "success": ACCENT,
    "failed": ERROR,
    "skipped": WARNING,
    "cancelled": TEXT_SECONDARY,
}

# ── Fonts ─────────────────────────────────────────────────────

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Cascadia Code, Consolas, monospace"
FONT_SIZE = 13
FONT_SIZE_SM = 11
FONT_SIZE_LG = 16
FONT_SIZE_XL = 22
FONT_SIZE_TITLE = 28

# ── Global Stylesheet ────────────────────────────────────────

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}";
    font-size: {FONT_SIZE}px;
}}

/* ── Buttons ─────────────────── */

QPushButton {{
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {BG_ELEVATED};
    border-color: {TEXT_SECONDARY};
}}

QPushButton:pressed {{
    background-color: {BG_SECONDARY};
}}

QPushButton:disabled {{
    color: {TEXT_MUTED};
    border-color: {BG_TERTIARY};
}}

QPushButton#primaryButton {{
    background-color: {ACCENT};
    color: {BG_PRIMARY};
    border: none;
    font-weight: 700;
}}

QPushButton#primaryButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primaryButton:disabled {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
}}

/* ── Inputs ──────────────────── */

QLineEdit, QTextEdit, QComboBox {{
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: {ACCENT_DIM};
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

/* ── Labels ──────────────────── */

QLabel#titleLabel {{
    font-size: {FONT_SIZE_TITLE}px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

QLabel#subtitleLabel {{
    font-size: {FONT_SIZE_LG}px;
    color: {TEXT_SECONDARY};
}}

QLabel#sectionLabel {{
    font-size: {FONT_SIZE_LG}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    padding-bottom: 4px;
}}

/* ── Progress Bar ────────────── */

QProgressBar {{
    background-color: {BG_TERTIARY};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

/* ── Scroll Area ─────────────── */

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {BG_SECONDARY};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BG_ELEVATED};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Cards / Frames ──────────── */

QFrame#card {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 16px;
}}

QFrame#card:hover {{
    border-color: {ACCENT};
}}

/* ── CheckBox ────────────────── */

QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_TERTIARY};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Log Viewer ──────────────── */

QPlainTextEdit#logViewer {{
    background-color: #0d0e10;
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO};
    font-size: {FONT_SIZE_SM}px;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {BG_ELEVATED};
}}
"""
