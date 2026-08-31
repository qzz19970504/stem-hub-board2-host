"""Dark console design tokens shared by every UI component.

从 stem-hub-host 移植, 按板2 功能裁剪: 去掉电池/温度策略, 保留完整配色体系.
"""
from __future__ import annotations


# ---- Window and layout ----
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 720
PAGE_MARGIN_X = 24
PAGE_MARGIN_Y = 18
GRID_GAP = 18
SERIAL_GRID_GAP = 8
COLUMN_STRETCH_LEFT = 100
COLUMN_STRETCH_CENTER = 126
COLUMN_STRETCH_RIGHT = 100
ROW_STRETCH_TOP = 52
ROW_STRETCH_BOTTOM = 48
SERIAL_COMBO_WIDTH = 260
SERIAL_BADGE_WIDTH = 152
SERIAL_BUTTON_WIDTH = 156
SERIAL_CONTROL_HEIGHT = 40
SERIAL_HEADER_HEIGHT = 48
SERIAL_HEADER_WIDTH = 592
SERIAL_HEADER_GAP = 18
SERIAL_DOT_CENTER_X = 14
SERIAL_BADGE_TEXT_INSET = 34
SERIAL_CONTROL_FONT_SIZE = 14
SWITCH_WIDTH = 60
SWITCH_HEIGHT = 36
SWITCH_KNOB_SIZE = 28
SWITCH_KNOB_GAP = 4
SWITCH_BORDER_WIDTH = 1.0
SWITCH_FOCUS_WIDTH = 1.5
SWITCH_SHADOW_ALPHA = 52
SWITCH_SHADOW_OFFSET_Y = 1.0
CONTROL_HEIGHT = 40
CONTROL_HEIGHT_SM = 38
BORDER_WIDTH = 1
FOCUS_BORDER_WIDTH = 2
CARD_RADIUS = 14
SUBCARD_RADIUS = 12
COMMAND_RADIUS = 10
CONTROL_RADIUS = 8
CHIP_RADIUS = 9
DIVIDER_HEIGHT = 1
LAYOUT_MARGIN_CARD = 16
LAYOUT_MARGIN_CARD_Y = 14
LAYOUT_GAP_CONTROL = 10
LAYOUT_GAP_COMPACT = 8
EFFECT_HALO_ALPHA = 45
EFFECT_GLOW_ALPHA = 90
EFFECT_BORDER_ALPHA = 145

# ---- Motion ----
ANIMATION_FAST_MS = 140
ANIMATION_NORMAL_MS = 240

# ---- 背景 ----
BG_OUTER = "#09111B"
BG_BASE = "#0F1825"
BG_CARD = "#172332"           # 卡片主背景
BG_CARD_HOVER = "#1D2C3E"     # 卡片悬停
BG_SUB_CARD = "#121D2B"       # 嵌套子卡 (PWM 行 / AT 输入)
BG_INPUT = "#101A27"          # 输入框 / log 区
BG_ELEVATED = "#1A2839"       # 工具条等抬升面
BG_CONTROL = "#1C2B3D"        # 统一按钮和选择 chip
BG_CONTROL_TOP = "#293A50"    # 自绘按钮的轻微顶部高光
BG_PLOT = "#111C2A"           # 图表绘图区
BG_ACCENT_SOFT = "#17383B"    # 低饱和 cyan 状态面
BORDER = "#2A394D"            # 卡片边框
BORDER_LIGHT = "#3A4D65"
BORDER_FOCUS = "#5EEAD4"
BORDER_GLOW = "#2DD4BF"       # 边缘 cyan 辉光

# 串口状态徽章 / 按钮: 深青蓝 (CONNECTED badge / Disconnect 按钮)
BG_TEAL_DARK = "#0E3D3A"
BORDER_TEAL = "#1F6F66"

# ---- 文字 ----
FG_PRIMARY = "#E6EDF3"
FG_SECONDARY = "#8DA0B8"
FG_TERTIARY = "#70849C"
FG_DISABLED = "#506277"
FG_ON_ACCENT = "#07110D"
FG_ON_DANGER = "#FFFFFF"

FG_DIM = FG_TERTIARY

# ---- Cyan accent ----
ACCENT = "#5EEAD4"
ACCENT_HOVER = "#7FF0DD"
ACCENT_PRESSED = "#2DD4BF"
ACCENT_DARK = "#0E7490"
ACCENT_DIM = "#1A4A45"        # active 按钮背景
ACCENT_DEEP = "#2DD4BF"

# ---- 状态色 ----
STATUS_OK = "#3FB950"
STATUS_WARN = "#D29922"
STATUS_ERROR = "#F85149"
STATUS_OFF = "#2A3A4E"
STATUS_OK_BORDER = "#67D878"
STATUS_OK_HOVER = "#56C867"
STATUS_OK_PRESSED = "#2E923E"
STATUS_WARN_BORDER = "#6E5318"
STATUS_ERROR_BORDER = "#7A2E2A"
DANGER_ACTION = "#C9413A"
DANGER_ACTION_HOVER = "#E04D46"
DANGER_TEXT = "#FF8B84"
DANGER_SURFACE = "#45252B"
DANGER_BORDER = "#8C3C3A"
DANGER_ACTION_STRONG = "#A63835"
DANGER_ACTION_PRESSED = "#742825"
DANGER_FOCUS = "#FFB4AF"
SWITCH_KNOB_TOP = "#FFFFFF"
SWITCH_KNOB_BOTTOM = "#DDE7F0"
SWITCH_KNOB_BORDER = "#C3D0DC"
SWITCH_SHADOW = "#000000"

# PWM 渐变进度色
PWM_TRACK = BG_INPUT
PWM_FILL = ACCENT


_DARK_PALETTE = {
    "BG_OUTER": "#09111B",
    "BG_BASE": "#0F1825",
    "BG_CARD": "#172332",
    "BG_CARD_HOVER": "#1D2C3E",
    "BG_SUB_CARD": "#121D2B",
    "BG_INPUT": "#101A27",
    "BG_ELEVATED": "#1A2839",
    "BG_CONTROL": "#1C2B3D",
    "BG_CONTROL_TOP": "#293A50",
    "BG_PLOT": "#111C2A",
    "BG_ACCENT_SOFT": "#17383B",
    "BORDER": "#2A394D",
    "BORDER_LIGHT": "#3A4D65",
    "BORDER_FOCUS": "#5EEAD4",
    "BORDER_GLOW": "#2DD4BF",
    "BG_TEAL_DARK": "#0E3D3A",
    "BORDER_TEAL": "#1F6F66",
    "FG_PRIMARY": "#E6EDF3",
    "FG_SECONDARY": "#8DA0B8",
    "FG_TERTIARY": "#70849C",
    "FG_DISABLED": "#506277",
    "FG_ON_ACCENT": "#07110D",
    "FG_ON_DANGER": "#FFFFFF",
    "FG_DIM": "#70849C",
    "ACCENT": "#5EEAD4",
    "ACCENT_HOVER": "#7FF0DD",
    "ACCENT_PRESSED": "#2DD4BF",
    "ACCENT_DARK": "#0E7490",
    "ACCENT_DIM": "#1A4A45",
    "ACCENT_DEEP": "#2DD4BF",
    "STATUS_OK": "#3FB950",
    "STATUS_WARN": "#D29922",
    "STATUS_ERROR": "#F85149",
    "STATUS_OFF": "#2A3A4E",
    "STATUS_OK_BORDER": "#67D878",
    "STATUS_OK_HOVER": "#56C867",
    "STATUS_OK_PRESSED": "#2E923E",
    "STATUS_WARN_BORDER": "#6E5318",
    "STATUS_ERROR_BORDER": "#7A2E2A",
    "DANGER_ACTION": "#C9413A",
    "DANGER_ACTION_HOVER": "#E04D46",
    "DANGER_TEXT": "#FF8B84",
    "DANGER_SURFACE": "#45252B",
    "DANGER_BORDER": "#8C3C3A",
    "DANGER_ACTION_STRONG": "#A63835",
    "DANGER_ACTION_PRESSED": "#742825",
    "DANGER_FOCUS": "#FFB4AF",
    "SWITCH_KNOB_TOP": "#FFFFFF",
    "SWITCH_KNOB_BOTTOM": "#DDE7F0",
    "SWITCH_KNOB_BORDER": "#C3D0DC",
    "SWITCH_SHADOW": "#000000",
}

_LIGHT_PALETTE = {
    "BG_OUTER": "#D7E2EC",
    "BG_BASE": "#EAF1F6",
    "BG_CARD": "#F8FBFD",
    "BG_CARD_HOVER": "#E5EEF5",
    "BG_SUB_CARD": "#EDF3F7",
    "BG_INPUT": "#E7EEF4",
    "BG_ELEVATED": "#E0EAF1",
    "BG_CONTROL": "#D9E5ED",
    "BG_CONTROL_TOP": "#F4F8FB",
    "BG_PLOT": "#F3F7FA",
    "BG_ACCENT_SOFT": "#D5F0EC",
    "BORDER": "#B6C7D5",
    "BORDER_LIGHT": "#91A8BA",
    "BORDER_FOCUS": "#0F9F92",
    "BORDER_GLOW": "#16A89A",
    "BG_TEAL_DARK": "#CDECE7",
    "BORDER_TEAL": "#6CBEB4",
    "FG_PRIMARY": "#142638",
    "FG_SECONDARY": "#40576C",
    "FG_TERTIARY": "#6F8294",
    "FG_DISABLED": "#9AAAB8",
    "FG_ON_ACCENT": "#07110D",
    "FG_ON_DANGER": "#FFFFFF",
    "FG_DIM": "#6F8294",
    "ACCENT": "#0F9F92",
    "ACCENT_HOVER": "#18B4A6",
    "ACCENT_PRESSED": "#0B7F76",
    "ACCENT_DARK": "#08766F",
    "ACCENT_DIM": "#C4E9E4",
    "ACCENT_DEEP": "#0F9F92",
    "STATUS_OK": "#218B4B",
    "STATUS_WARN": "#A76B00",
    "STATUS_ERROR": "#CF3E3A",
    "STATUS_OFF": "#AABAC8",
    "STATUS_OK_BORDER": "#67D878",
    "STATUS_OK_HOVER": "#56C867",
    "STATUS_OK_PRESSED": "#2E923E",
    "STATUS_WARN_BORDER": "#8A650E",
    "STATUS_ERROR_BORDER": "#A84440",
    "DANGER_ACTION": "#C9413A",
    "DANGER_ACTION_HOVER": "#E04D46",
    "DANGER_TEXT": "#B52F2B",
    "DANGER_SURFACE": "#F8DDDB",
    "DANGER_BORDER": "#C76560",
    "DANGER_ACTION_STRONG": "#A63835",
    "DANGER_ACTION_PRESSED": "#742825",
    "DANGER_FOCUS": "#A84440",
    "SWITCH_KNOB_TOP": "#FFFFFF",
    "SWITCH_KNOB_BOTTOM": "#E8EEF3",
    "SWITCH_KNOB_BORDER": "#9FB2C2",
    "SWITCH_SHADOW": "#284155",
}

_COLOR_SCHEME = "dark"


def set_color_scheme(scheme: str) -> None:
    """Activate one complete palette while preserving token names."""

    global _COLOR_SCHEME
    if scheme not in {"dark", "light"}:
        raise ValueError(f"Unsupported color scheme: {scheme}")
    palette = _DARK_PALETTE if scheme == "dark" else _LIGHT_PALETTE
    globals().update(palette)
    _COLOR_SCHEME = scheme


def color_scheme() -> str:
    return _COLOR_SCHEME


def blend_hex(background: str, foreground: str, alpha: float) -> str:
    """Blend two opaque #RRGGBB colors without coupling theme tokens to Qt."""

    alpha = max(0.0, min(1.0, float(alpha)))
    bg = tuple(int(background[index:index + 2], 16) for index in (1, 3, 5))
    fg = tuple(int(foreground[index:index + 2], 16) for index in (1, 3, 5))
    channels = tuple(
        round(bg_channel * (1.0 - alpha) + fg_channel * alpha)
        for bg_channel, fg_channel in zip(bg, fg)
    )
    return "#{:02X}{:02X}{:02X}".format(*channels)


# ---- 间距 ----
SP_XS = 8
SP_SM = 12
SP_MD = 16
SP_LG = 20
SP_XL = 28
SP_XXL = 40

# ---- 圆角 ----
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 20

# ---- 字体 ----
FONT_DISPLAY = "Rajdhani"
FONT_FAMILY = "Noto Sans SC"
FONT_MONO = "JetBrains Mono"


def configure_font_families(display: str, mono: str, cjk: str) -> None:
    """Update font role tokens after QApplication registers bundled fonts."""

    global FONT_DISPLAY, FONT_MONO, FONT_FAMILY
    FONT_DISPLAY = display
    FONT_MONO = mono
    FONT_FAMILY = cjk

# ---- 字号 (整体提升一档, 保持级差) ----
FS_CAPTION = 12
FS_FOOTNOTE = 13
FS_BODY = 14
FS_HEADLINE = 15
FS_TITLE3 = 16
FS_TITLE2 = 17
FS_TITLE1 = 21
FS_LARGE_TITLE = 33
FS_DISPLAY = 43
FS_HUGE = 65
