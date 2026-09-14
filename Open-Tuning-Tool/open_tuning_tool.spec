# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Open-Tuning-Tool
This file configures how PyInstaller builds the executable
"""

import sys
from pathlib import Path

# Get the fpv_tuner directory
fpv_tuner_path = Path(__file__).parent / 'fpv_tuner'

block_cipher = None

a = Analysis(
    ['fpv_tuner/main.py'],
    pathex=[str(Path(__file__).parent)],
    binaries=[],
    datas=[
        (str(fpv_tuner_path), 'fpv_tuner'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'pyqtgraph',
        'pandas',
        'numpy',
        'scipy',
        'serial',
        'serial.tools.list_ports',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Open-Tuning-Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='Open-Tuning-Tool.app',
    icon=None,
    bundle_identifier='com.opentuningtool.fpv',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
    },
)
