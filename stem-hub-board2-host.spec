# PyInstaller spec for stem-hub-board2-host
# Build:  pyinstaller --noconfirm stem-hub-board2-host.spec
# Output: dist/stem-hub-board2-host.exe

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve()

block_cipher = None

# A venv created from Conda keeps its matching native runtime under the base
# interpreter's Library/bin. Put it ahead of unrelated Conda installations so
# dependency analysis cannot pair Python 3.11 extensions with Python 3.13 DLLs.
PYTHON_BASE_LIBRARY_BIN = Path(sys.base_prefix) / "Library" / "bin"
if PYTHON_BASE_LIBRARY_BIN.is_dir():
    os.environ["PATH"] = (
        f"{PYTHON_BASE_LIBRARY_BIN}{os.pathsep}{os.environ.get('PATH', '')}"
    )

# 数据文件 (style.qss / fonts / icons)
datas = [
    (str(PROJECT_ROOT / "stem_hub_board2_host" / "ui" / "style.qss"), "stem_hub_board2_host/ui"),
    (
        str(PROJECT_ROOT / "stem_hub_board2_host" / "resources" / "fonts"),
        "stem_hub_board2_host/resources/fonts",
    ),
    (
        str(PROJECT_ROOT / "stem_hub_board2_host" / "resources" / "icons"),
        "stem_hub_board2_host/resources/icons",
    ),
]

# 隐式 import (确保所有 widget 模块都被收集)
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSerialPort",
    "PySide6.QtNetwork",
    "stem_hub_board2_host.app",
    "stem_hub_board2_host.branding",
    "stem_hub_board2_host.at_protocol",
    "stem_hub_board2_host.controller",
    "stem_hub_board2_host.fake_firmware",
    "stem_hub_board2_host.main",
    "stem_hub_board2_host.models",
    "stem_hub_board2_host.serial_worker",
    "stem_hub_board2_host.transport",
    "stem_hub_board2_host.ui.main_window",
    "stem_hub_board2_host.ui.native_chrome",
    "stem_hub_board2_host.ui.fonts",
    "stem_hub_board2_host.ui.stylesheet",
    "stem_hub_board2_host.ui.tab1_console",
    "stem_hub_board2_host.ui.tab2_passthrough",
    "stem_hub_board2_host.ui.theme",
    "stem_hub_board2_host.ui.widgets.at_console",
    "stem_hub_board2_host.ui.widgets.nmos_card",
    "stem_hub_board2_host.ui.widgets.passthrough_panel",
    "stem_hub_board2_host.ui.widgets.power_card",
    "stem_hub_board2_host.ui.widgets.pwm_card",
    "stem_hub_board2_host.ui.widgets.serial_bar",
    "stem_hub_board2_host.ui.widgets.status_card",
    "stem_hub_board2_host.ui.widgets.theme_toggle",
    "stem_hub_board2_host.ui.widgets.toggle_switch",
    "shiboken6",
]

a = Analysis(
    [str(PROJECT_ROOT / "stem_hub_board2_host" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除没用的大库, 让 .exe 小一点.
        # 警告: PySide6 内部 import xml.etree / pydoc 等 stdlib, 别排这些.
        # stdlib 本身不大, 别手贱.
        "tkinter",
        "unittest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="stem-hub-board2-host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # GUI 程序, 不弹 console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(
        PROJECT_ROOT
        / "stem_hub_board2_host"
        / "resources"
        / "icons"
        / "app_icon.ico"
    ),
)
