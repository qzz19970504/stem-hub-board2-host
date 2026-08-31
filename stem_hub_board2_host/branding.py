"""Stable application identity and bundled icon access."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


APP_DISPLAY_NAME = "stem hub board2 host"
APP_ICON_FILE = "app_icon.png"


def app_icon_path() -> Path:
    """Return the source or PyInstaller-expanded runtime icon path."""

    return (
        Path(__file__).resolve().parent
        / "resources"
        / "icons"
        / APP_ICON_FILE
    )


def load_app_icon() -> QIcon:
    """Load the bundled icon, leaving Qt's normal null-icon fallback intact."""

    return QIcon(str(app_icon_path()))
