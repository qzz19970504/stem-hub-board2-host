"""Windows native title-bar colors synchronized with the Qt application theme."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from . import theme


DWMWA_USE_IMMERSIVE_DARK_MODE_FALLBACK = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


@dataclass(frozen=True)
class CaptionPalette:
    background: str
    foreground: str
    use_dark_mode: bool


def caption_palette(scheme: str) -> CaptionPalette:
    """Return title-bar colors from the same palette as the adjacent tab header."""

    if scheme == "dark":
        palette = theme._DARK_PALETTE
        use_dark_mode = True
    elif scheme == "light":
        palette = theme._LIGHT_PALETTE
        use_dark_mode = False
    else:
        raise ValueError(f"Unsupported color scheme: {scheme}")
    return CaptionPalette(
        background=palette["BG_BASE"],
        foreground=palette["FG_PRIMARY"],
        use_dark_mode=use_dark_mode,
    )


def hex_to_colorref(color: str) -> int:
    """Convert #RRGGBB to the BGR COLORREF representation used by DWM."""

    value = color.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {color!r}")
    red, green, blue = (
        int(value[index:index + 2], 16)
        for index in (0, 2, 4)
    )
    return red | (green << 8) | (blue << 16)


def _set_attribute(dwmapi, hwnd: int, attribute: int, value: int) -> bool:
    native_value = wintypes.DWORD(value)
    result = dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(attribute),
        ctypes.byref(native_value),
        ctypes.sizeof(native_value),
    )
    return result == 0


def apply_windows_title_bar(window: QWidget, scheme: str) -> bool:
    """Apply native caption colors, returning False on unsupported platforms."""

    if sys.platform != "win32":
        return False
    application = QGuiApplication.instance()
    if application is None or application.platformName().lower() != "windows":
        return False

    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmSetWindowAttribute.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

        hwnd = int(window.winId())
        colors = caption_palette(scheme)
        dark_value = int(colors.use_dark_mode)
        dark_applied = _set_attribute(
            dwmapi,
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            dark_value,
        )
        if not dark_applied:
            dark_applied = _set_attribute(
                dwmapi,
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_FALLBACK,
                dark_value,
            )

        background = hex_to_colorref(colors.background)
        foreground = hex_to_colorref(colors.foreground)
        color_results = (
            _set_attribute(dwmapi, hwnd, DWMWA_CAPTION_COLOR, background),
            _set_attribute(dwmapi, hwnd, DWMWA_TEXT_COLOR, foreground),
            _set_attribute(dwmapi, hwnd, DWMWA_BORDER_COLOR, background),
        )
        return dark_applied and all(color_results)
    except (AttributeError, OSError, ValueError):
        return False
