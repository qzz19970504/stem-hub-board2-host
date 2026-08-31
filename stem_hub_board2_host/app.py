"""QApplication 装配 — 集中管控 application-level 资源.

业务 UI 不要直接用 QApplication, 通过本模块的 get_app() 获取.
确保整个进程只有一个 QApplication 实例.
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .branding import APP_DISPLAY_NAME, load_app_icon
from .ui import theme
from .ui.fonts import FontFamilies, load_application_fonts


_app: Optional[QApplication] = None
_font_families: Optional[FontFamilies] = None


def get_app() -> QApplication:
    """获取全局 QApplication 实例, 第一次调用时创建."""
    global _app, _font_families
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
        _app.setApplicationName(APP_DISPLAY_NAME)
        _app.setOrganizationName("stem-hub")
        _app.setWindowIcon(load_app_icon())
    if _font_families is None:
        _font_families = load_application_fonts()
        theme.configure_font_families(
            display=_font_families.display,
            mono=_font_families.mono,
            cjk=_font_families.cjk,
        )
        application_font = QFont(_font_families.cjk, 11)
        application_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        _app.setFont(application_font)
    return _app
