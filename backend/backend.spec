# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = []
binaries = []
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'comtypes.stream',
    'tkinter',
    'ctypes',
    'ctypes.wintypes',
    'backend.eye_tracking.click_feedback_overlay',
    'backend.fusion.fusion_engine',
    'backend.services.system_cursor',
    'backend.vision.head_pose',
    'backend.voice.recognizer',
    'backend.voice.pipeline',
    'backend.sys_platform',
    'backend.sys_platform.config_validator',
    'backend.sys_platform.lifecycle',
    'backend.sys_platform.health',
    'backend.sys_platform.diagnostics',
    'backend.core.di.container',
]

packages_to_collect = [
    'sounddevice',
    'faster_whisper',
    'av',
    'ctranslate2',
    'cv2',
    'scipy',
    'mediapipe',
    'pyautogui',
    'mouseinfo',
    'pygetwindow',
    'pymsgbox',
    'pyperclip',
    'pyrect',
    'pyscreeze',
    'pytweening',
    'uvicorn',
    'fastapi',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'pyttsx3',
    'comtypes',
    'psutil',
]

for pkg in packages_to_collect:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"collect_all warning for {pkg}: {e}")

try:
    import mediapipe
    mp_dir = os.path.dirname(mediapipe.__file__)
    mp_modules = os.path.join(mp_dir, 'modules')
    if os.path.exists(mp_modules):
        datas.append((mp_modules, 'mediapipe/modules'))
        datas.append((mp_modules, 'modules'))
except Exception as e:
    print(f"Failed to add mediapipe modules: {e}")

if os.path.exists('resources'):
    datas.append(('resources', 'resources'))

if os.path.basename(os.getcwd()) == 'backend':
    pathex = ['..']
    main_script = 'main.py'
else:
    pathex = ['.']
    main_script = 'backend/main.py'

a = Analysis(
    [main_script],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='backend',
)
