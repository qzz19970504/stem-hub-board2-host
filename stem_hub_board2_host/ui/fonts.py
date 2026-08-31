"""Application font registration with deterministic fallbacks."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase


LOGGER = logging.getLogger(__name__)

DISPLAY_FONT_FILE = "Rajdhani-SemiBold.ttf"
MONO_FONT_FILES = ("JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf")
CJK_FONT_FILE = "NotoSansSC-Regular.ttf"

DISPLAY_FONT_FAMILY = "Rajdhani"
MONO_FONT_FAMILY = "JetBrains Mono"
CJK_FONT_FAMILY = "Noto Sans SC"

DISPLAY_FONT_FALLBACK = "Segoe UI"
MONO_FONT_FALLBACK = "Consolas"
CJK_FONT_FALLBACK = "Microsoft YaHei UI"


@dataclass(frozen=True)
class FontFamilies:
    """Font family names selected for each UI role."""

    display: str
    mono: str
    cjk: str


_loaded_families: FontFamilies | None = None


def _font_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "fonts"


def _register_font(path: Path) -> set[str]:
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        LOGGER.warning("Unable to register bundled font: %s", path)
        return set()
    return set(QFontDatabase.applicationFontFamilies(font_id))


def _select_family(
    preferred: str,
    fallback: str,
    available_families: set[str],
) -> str:
    if preferred in available_families:
        return preferred
    LOGGER.warning("Bundled font family %s unavailable; using %s", preferred, fallback)
    return fallback


def load_application_fonts() -> FontFamilies:
    """Register bundled fonts and return stable UI family names.

    The function is idempotent. Missing or corrupt resource files are logged and
    replaced with Windows fallbacks so startup remains usable.
    """

    global _loaded_families
    if _loaded_families is not None:
        return _loaded_families

    font_directory = _font_directory()
    font_files = (DISPLAY_FONT_FILE, *MONO_FONT_FILES, CJK_FONT_FILE)
    registered_families: set[str] = set()
    for font_file in font_files:
        font_path = font_directory / font_file
        if not font_path.is_file():
            LOGGER.warning("Bundled font file missing: %s", font_path)
            continue
        registered_families.update(_register_font(font_path))

    available_families = set(QFontDatabase.families()) | registered_families
    _loaded_families = FontFamilies(
        display=_select_family(
            DISPLAY_FONT_FAMILY,
            DISPLAY_FONT_FALLBACK,
            available_families,
        ),
        mono=_select_family(
            MONO_FONT_FAMILY,
            MONO_FONT_FALLBACK,
            available_families,
        ),
        cjk=_select_family(
            CJK_FONT_FAMILY,
            CJK_FONT_FALLBACK,
            available_families,
        ),
    )
    return _loaded_families
