# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for WinProv.

Build command:
    pyinstaller build.spec

Notes:
- Uses --onedir mode (more reliable for PySide6 than --onefile)
- Bundles config/, profiles/, packages/, scripts/ as data
- Sets UAC admin manifest for Windows
- Output goes to dist/winprov/
"""

import os
from pathlib import Path

block_cipher = None
root = Path(os.path.abspath(SPECPATH))

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        # Bundle JSON configs, profiles, packages, scripts
        (str(root / 'config'), 'config'),
        (str(root / 'profiles'), 'profiles'),
        (str(root / 'packages'), 'packages'),
        (str(root / 'scripts'), 'scripts'),
        (str(root / 'assets'), 'assets'),
    ],
    hiddenimports=[
        'pydantic',
        'httpx',
        'httpx._transports',
        'httpx._transports.default',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'xml',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WinProv',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                    # GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets' / 'icon.ico') if (root / 'assets' / 'icon.ico').exists() else None,
    uac_admin=True,                   # Request admin elevation
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='winprov',
)
