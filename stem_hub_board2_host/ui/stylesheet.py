"""Load and strictly render the tokenized application QSS."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from PySide6.QtWidgets import QApplication

from . import theme


_QSS_CACHE: Optional[str] = None
_TOKEN_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _qss_path() -> Path:
    return Path(__file__).parent / "style.qss"


def load_qss_source() -> str:
    """Return the unrendered QSS template for validation and tooling."""

    return _qss_path().read_text(encoding="utf-8-sig")


def qss_tokens() -> dict[str, str]:
    """Return the complete semantic token context for QSS rendering."""

    color_names = (
        "BG_OUTER",
        "BG_BASE",
        "BG_CARD",
        "BG_CARD_HOVER",
        "BG_SUB_CARD",
        "BG_INPUT",
        "BG_CONTROL",
        "BORDER",
        "BORDER_LIGHT",
        "BG_TEAL_DARK",
        "BORDER_TEAL",
        "BG_ACCENT_SOFT",
        "FG_PRIMARY",
        "FG_SECONDARY",
        "FG_TERTIARY",
        "FG_DISABLED",
        "FG_ON_ACCENT",
        "FG_ON_DANGER",
        "ACCENT",
        "ACCENT_HOVER",
        "ACCENT_PRESSED",
        "ACCENT_DIM",
        "STATUS_OK",
        "STATUS_WARN",
        "STATUS_ERROR",
        "STATUS_OK_BORDER",
        "STATUS_OK_HOVER",
        "STATUS_OK_PRESSED",
        "STATUS_WARN_BORDER",
        "STATUS_ERROR_BORDER",
        "DANGER_ACTION",
        "DANGER_ACTION_HOVER",
        "DANGER_TEXT",
        "DANGER_SURFACE",
        "DANGER_BORDER",
        "DANGER_ACTION_STRONG",
        "DANGER_ACTION_PRESSED",
        "DANGER_FOCUS",
        "SWITCH_KNOB_TOP",
        "SWITCH_KNOB_BORDER",
    )
    tokens = {name: str(getattr(theme, name)) for name in color_names}
    tokens.update(
        {
            "FONT_DISPLAY": theme.FONT_DISPLAY,
            "FONT_MONO": theme.FONT_MONO,
            "BORDER_WIDTH": str(theme.BORDER_WIDTH),
            "FOCUS_BORDER_WIDTH": str(theme.FOCUS_BORDER_WIDTH),
            "CARD_RADIUS": str(theme.CARD_RADIUS),
            "SUBCARD_RADIUS": str(theme.SUBCARD_RADIUS),
            "COMMAND_RADIUS": str(theme.COMMAND_RADIUS),
            "CONTROL_RADIUS": str(theme.CONTROL_RADIUS),
            "CHIP_RADIUS": str(theme.CHIP_RADIUS),
            "SERIAL_BADGE_TEXT_INSET": str(
                theme.SERIAL_BADGE_TEXT_INSET
            ),
        }
    )
    return tokens


def _render_qss(source: str) -> str:
    tokens = qss_tokens()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        try:
            return tokens[name]
        except KeyError as error:
            raise ValueError(f"Unknown QSS design token: {name}") from error

    return _TOKEN_PATTERN.sub(replace, source)


def get_qss() -> str:
    global _QSS_CACHE
    if _QSS_CACHE is None:
        _QSS_CACHE = _render_qss(load_qss_source())
    return _QSS_CACHE


def invalidate_cache() -> None:
    global _QSS_CACHE
    _QSS_CACHE = None


def apply_to(app: QApplication) -> None:
    invalidate_cache()
    app.setStyleSheet(get_qss())
