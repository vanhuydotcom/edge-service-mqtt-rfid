# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for RFID Edge Service
Builds the FastAPI backend into a standalone Windows executable
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Paths
backend_path = os.path.abspath('../backend')
frontend_static_path = os.path.abspath('../frontend/static')

# Collect all backend modules
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'paho.mqtt.client',
    'aiosqlite',
    'websockets',
    'fastapi',
    'pydantic',
    'pydantic_settings',
]

# Collect data files
datas = [
    (os.path.join(backend_path, 'conf'), 'conf'),  # Configuration files
]

# Add frontend static files if they exist
if os.path.exists(frontend_static_path):
    datas.append((frontend_static_path, 'static'))

a = Analysis(
    [os.path.join(backend_path, 'main.py')],
    pathex=[backend_path],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='edge-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'circa-icon.ico') if os.path.exists(os.path.join('assets', 'circa-icon.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='edge-service',
)

