"""Soft, supersampled output switch used by the hardware control card."""
from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import theme


class ToggleSwitch(QWidget):
    """Animated pill switch with inset geometry and soft material highlights."""

    toggled = Signal(bool)

    TRACK_WIDTH = theme.SWITCH_WIDTH
    TRACK_HEIGHT = theme.SWITCH_HEIGHT
    KNOB_SIZE = theme.SWITCH_KNOB_SIZE
    KNOB_GAP = theme.SWITCH_KNOB_GAP
    RENDER_SCALE = 4

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: bool = False,
    ) -> None:
        super().__init__(parent)
        self._on = bool(initial)
        self.setFixedSize(self.TRACK_WIDTH, self.TRACK_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAccessibleName("Output switch")
        self._pressed = False
        self._anim: QPropertyAnimation | None = None
        self._knob_x = self._target_x()

    def is_on(self) -> bool:
        return self._on

    def set_on(self, on: bool, *, animate: bool = True) -> None:
        on = bool(on)
        if on == self._on:
            return
        self._on = on
        if animate:
            self._animate_to(self._target_x())
        else:
            self._knob_x = self._target_x()
            self.update()

    def _target_x(self) -> float:
        if self._on:
            return float(
                self.TRACK_WIDTH - self.KNOB_GAP - self.KNOB_SIZE
            )
        return float(self.KNOB_GAP)

    def _animate_to(self, x: float) -> None:
        if self._anim is not None:
            self._anim.stop()
        animation = QPropertyAnimation(self, b"knob_x", self)
        animation.setDuration(theme.ANIMATION_NORMAL_MS)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.setStartValue(self._knob_x)
        animation.setEndValue(x)
        animation.start()
        self._anim = animation

    def _get_knob_x(self) -> float:
        return self._knob_x

    def _set_knob_x(self, value: float) -> None:
        self._knob_x = value
        self.update()

    knob_x = Property(float, _get_knob_x, _set_knob_x)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if (
            event.button() != Qt.MouseButton.LeftButton
            or not self.isEnabled()
        ):
            super().mousePressEvent(event)
            return
        self._pressed = True
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if (
            event.button() != Qt.MouseButton.LeftButton
            or not self._pressed
        ):
            super().mouseReleaseEvent(event)
            return
        self._pressed = False
        if self.rect().contains(event.position().toPoint()) and self.isEnabled():
            self._toggle_from_user()
        self.update()
        event.accept()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.update()
        super().enterEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        activation_keys = (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if event.key() in activation_keys and self.isEnabled():
            self._toggle_from_user()
            event.accept()
            return
        super().keyPressEvent(event)

    def _toggle_from_user(self) -> None:
        self.set_on(not self._on)
        self.toggled.emit(self._on)

    def _track_colors(self) -> tuple[QColor, QColor]:
        if not self.isEnabled():
            return (
                QColor(theme.BG_INPUT),
                QColor(theme.BORDER),
            )
        if self._on:
            return QColor(theme.ACCENT), QColor(theme.ACCENT_HOVER)
        return QColor(theme.BG_CONTROL), QColor(theme.BORDER_LIGHT)

    def _knob_color(self) -> QColor:
        if not self.isEnabled():
            return QColor(theme.FG_DISABLED)
        color = QColor(theme.SWITCH_KNOB_TOP)
        if self._pressed:
            color = color.darker(110)
        return color

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        scale = self.RENDER_SCALE
        image = QImage(
            self.width() * scale,
            self.height() * scale,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)

        track_rect = QRectF(
            theme.SWITCH_BORDER_WIDTH / 2,
            (self.height() - self.TRACK_HEIGHT) / 2,
            self.TRACK_WIDTH - theme.SWITCH_BORDER_WIDTH,
            self.TRACK_HEIGHT - theme.SWITCH_BORDER_WIDTH,
        )
        radius = self.TRACK_HEIGHT / 2
        track_fill, border = self._track_colors()
        if self.isEnabled() and self.underMouse():
            border = QColor(theme.ACCENT_HOVER)

        painter.setBrush(track_fill)
        painter.setPen(QPen(border, theme.SWITCH_BORDER_WIDTH))
        painter.drawRoundedRect(track_rect, radius, radius)

        if self.hasFocus():
            focus_rect = track_rect.adjusted(1.5, 1.5, -1.5, -1.5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(
                QColor(theme.FG_PRIMARY),
                theme.SWITCH_FOCUS_WIDTH,
            ))
            painter.drawRoundedRect(
                focus_rect,
                radius - 1.5,
                radius - 1.5,
            )

        knob_y = (self.height() - self.KNOB_SIZE) / 2
        knob_center = QPointF(
            self._knob_x + self.KNOB_SIZE / 2,
            knob_y + self.KNOB_SIZE / 2,
        )
        shadow = QColor(theme.SWITCH_SHADOW)
        shadow.setAlpha(theme.SWITCH_SHADOW_ALPHA)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(
            QPointF(
                knob_center.x(),
                knob_center.y() + theme.SWITCH_SHADOW_OFFSET_Y,
            ),
            self.KNOB_SIZE / 2 + 0.8,
            self.KNOB_SIZE / 2 + 0.8,
        )

        painter.setBrush(self._knob_color())
        painter.setPen(QPen(QColor(theme.SWITCH_KNOB_BORDER), 0.9))
        painter.drawEllipse(
            knob_center,
            self.KNOB_SIZE / 2,
            self.KNOB_SIZE / 2,
        )

        painter.end()

        target = QPainter(self)
        target.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target.drawImage(self.rect(), image)
