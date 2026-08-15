# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import os

datas = []
try:
    datas += collect_data_files('mediapipe')
except Exception:
    pass

repo_root = os.path.abspath(os.path.join(SPECPATH, '..'))
bundled_models_dir = os.path.join(repo_root, 'resources', 'models')
if os.path.exists(bundled_models_dir):
    datas.append((bundled_models_dir, 'resources/models'))

hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.lifespan.on',
    'fastapi',
    'pydantic',
    'pydantic_settings',
    'sqlalchemy.dialects.sqlite',
    'mediapipe',
    'cv2',
    'sounddevice',
    'faster_whisper',
    'ctranslate2',
    'pyautogui',
    'PIL',
]
hiddenimports += collect_submodules('backend')

a = Analysis(
    ['main.py'],
    pathex=['..'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='iris_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='iris_backend',
)
