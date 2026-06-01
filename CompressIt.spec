# -*- mode: python ; coding: utf-8 -*-
"""
CompressIt — PyInstaller spec
Build : pyinstaller compressit.spec

Avant de builder, placer les binaires dans bin/ :
  Windows : bin/ffmpeg.exe  bin/ffprobe.exe  bin/pdftoppm.exe  bin/pdfinfo.exe
  macOS   : bin/ffmpeg      bin/ffprobe      bin/pdftoppm      bin/pdfinfo
  Linux   : bin/ffmpeg      bin/ffprobe      bin/pdftoppm      bin/pdfinfo

Téléchargements :
  FFmpeg   — https://github.com/BtbN/FFmpeg-Builds/releases  (Windows/Linux)
             https://evermeet.cx/ffmpeg/  (macOS)
  Poppler  — https://github.com/oschwartz10612/poppler-windows/releases  (Windows)
             brew install poppler  (macOS)
             apt install poppler-utils  (Linux)
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
IS_WIN   = sys.platform == 'win32'
IS_MAC   = sys.platform == 'darwin'

# ---- Binaires externes ----
BIN_DIR = Path('bin')
binaries = []

def _add(name):
    p = BIN_DIR / name
    if p.exists():
        binaries.append((str(p), '.'))

if IS_WIN:
    _add('ffmpeg.exe');  _add('ffprobe.exe')
    _add('pdftoppm.exe'); _add('pdfinfo.exe')
else:
    _add('ffmpeg');  _add('ffprobe')
    _add('pdftoppm'); _add('pdfinfo')

# ---- Assets statiques ----
datas = [
    ('static', 'static'),
    ('compressors', 'compressors'),
]
datas += collect_data_files('pikepdf')
datas += collect_data_files('pdf2image')

# ---- Imports cachés ----
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'anyio', 'anyio._backends._asyncio',
    'starlette', 'starlette.staticfiles',
    'PIL', 'PIL.Image', 'PIL._imaging',
    'pikepdf', 'pikepdf._core',
    'zstandard', 'brotli',
    'multipart',
]
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('fastapi')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'notebook'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CompressIt',
    icon='static/icons/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
