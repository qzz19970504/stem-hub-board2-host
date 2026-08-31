"""电源轨卡片 — 12V / 18V Buck 开关."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from .toggle_switch import ToggleSwitch


class _RailRow(QWidget):
    """一条电源轨: 名称 + 状态点 + 开关."""

    toggled = Signal(bool)

    def __init__(self, title: str, subtitle: str, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("toolbarLabel")
        text_col.addWidget(self.title_label)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("secondary")
        text_col.addWidget(self.subtitle_label)
        lay.addLayout(text_col, 1)

        self.switch = ToggleSwitch()
        self.switch.toggled.connect(self.toggled)
        lay.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        # 状态点: 开关左侧小圆, 颜色随开关状态
        color = (
            theme.STATUS_OK
            if self.switch.is_on() and self.switch.isEnabled()
            else theme.STATUS_OFF
        )
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        halo = QColor(color)
        halo.setAlpha(theme.EFFECT_HALO_ALPHA)
        p.setBrush(halo)
        p.drawEllipse(QPointF(self.width() - 84, self.height() / 2), 6.5, 6.5)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(self.width() - 84, self.height() / 2), 3.5, 3.5)

    def refresh_theme(self) -> None:
        self.update()


class PowerCard(QFrame):
    """12V / 18V 两路电源轨控制."""

    power12_changed = Signal(bool)
    power18_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        col = QVBoxLayout(self)
        col.setContentsMargins(
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
        )
        col.setSpacing(theme.LAYOUT_GAP_CONTROL)

        title = QLabel("POWER RAILS")
        title.setObjectName("sectionTitle")
        col.addWidget(title)

        self.rail_12v = _RailRow("12V RAIL", "PB12 · 低电平开启 Buck")
        self.rail_12v.toggled.connect(self.power12_changed)
        col.addWidget(self.rail_12v)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(theme.DIVIDER_HEIGHT)
        col.addWidget(divider)

        self.rail_18v = _RailRow("18V RAIL", "PB3 · 低电平开启 Buck / PWM 前置")
        self.rail_18v.toggled.connect(self.power18_changed)
        col.addWidget(self.rail_18v)

        hint = QLabel("关 12V 自动关闭三路 NMOS；关 18V 自动清零 PWM")
        hint.setObjectName("secondary")
        hint.setWordWrap(True)
        col.addWidget(hint)
        col.addStretch(1)

    # ---- 公开 API ----
    def set_state(self, *, power_12v: bool, power_18v: bool) -> None:
        self.rail_12v.switch.set_on(power_12v, animate=False)
        self.rail_18v.switch.set_on(power_18v, animate=False)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.rail_12v.switch.setEnabled(enabled)
        self.rail_18v.switch.setEnabled(enabled)
        self.rail_12v.update()
        self.rail_18v.update()

    def refresh_theme(self) -> None:
        self.rail_12v.refresh_theme()
        self.rail_18v.refresh_theme()
