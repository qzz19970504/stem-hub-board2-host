"""Compact vector-painted day/night appearance switch."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from .. import theme


class ThemeToggleButton(QAbstractButton):
    scheme_changed = Signal(str)

    def __init__(
        self,
        scheme: str = "dark",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scheme = scheme
        self.setFixedSize(106, theme.CONTROL_HEIGHT_SM)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Toggle day and night appearance")
        self.setToolTip("Switch day / night appearance")
        self.clicked.connect(self._toggle)

    @property
    def color_scheme(self) -> str:
        return self._scheme

    def set_color_scheme(self, scheme: str) -> None:
        self._scheme = scheme
        self.update()

    def _toggle(self) -> None:
        target = "light" if self._scheme == "dark" else "dark"
        self.scheme_changed.emit(target)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        hovered = self.underMouse()
        fill = QColor(theme.BG_CARD_HOVER if hovered else theme.BG_CONTROL)
        border = QColor(theme.ACCENT if self.hasFocus() else theme.BORDER_LIGHT)
        p.setPen(QPen(border, 1.5))
        p.setBrush(fill)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        icon_center = QPointF(18, self.height() / 2)
        icon_color = QColor(theme.STATUS_WARN if self._scheme == "dark" else theme.ACCENT_DARK)
        p.setPen(QPen(icon_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._scheme == "dark":
            p.drawEllipse(icon_center, 5.0, 5.0)
            for index in range(8):
                angle = math.radians(index * 45)
                inner = QPointF(
                    icon_center.x() + math.cos(angle) * 8,
                    icon_center.y() + math.sin(angle) * 8,
                )
                outer = QPointF(
                    icon_center.x() + math.cos(angle) * 10,
                    icon_center.y() + math.sin(angle) * 10,
                )
                p.drawLine(inner, outer)
            label = "DAY"
        else:
            p.setBrush(icon_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(icon_center, 8, 8)
            p.setBrush(QColor(theme.BG_CONTROL))
            p.drawEllipse(QPointF(icon_center.x() + 4, icon_center.y() - 3), 7, 7)
            label = "NIGHT"

        font = QFont(theme.FONT_DISPLAY)
        font.setPointSize(11)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(theme.FG_PRIMARY))
        p.drawText(
            QRectF(32, 0, self.width() - 38, self.height()),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
