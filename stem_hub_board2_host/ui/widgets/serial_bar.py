"""Serial selection, connection state, and connect action bar."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from .. import theme


STATE_OFFLINE = "offline"
STATE_OPENING = "opening"
STATE_CONNECTED = "connected"
STATE_ERROR = "error"


def _strip_cjk(s: str) -> str:
    return "".join(c for c in s if ord(c) < 128).strip() or "Serial Port"


class _ChevronCombo(QComboBox):
    """下拉框 + 自绘 chevron."""

    about_to_show = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.setStyleSheet(
            f"QComboBox {{"
            f"  background: {theme.BG_INPUT};"
            f"  color: {theme.FG_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 10px;"
            f"  padding: 8px 36px 8px 16px;"
            f"  font-family: '{theme.FONT_MONO}';"
            f"  font-size: 14px;"
            f"}}"
            f"QComboBox:hover {{ border-color: {theme.BORDER_LIGHT}; }}"
            f"QComboBox:focus {{ border-color: {theme.ACCENT}; }}"
            f"QComboBox:disabled {{"
            f"  background: {theme.BG_BASE};"
            f"  color: {theme.FG_DISABLED};"
            f"  border-color: {theme.BORDER};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 32px;"
            f"  subcontrol-origin: padding;"
            f"  subcontrol-position: top right;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: {theme.BG_CARD};"
            f"  color: {theme.FG_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 8px;"
            f"  padding: 4px;"
            f"  selection-background-color: {theme.ACCENT_DIM};"
            f"  selection-color: {theme.FG_PRIMARY};"
            f"  outline: 0;"
            f"}}"
        )

    def paintEvent(self, ev) -> None:  # type: ignore[override]
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = self.width() - 18
        y = self.height() / 2
        color = QColor(
            theme.FG_SECONDARY if self.isEnabled() else theme.FG_DISABLED
        )
        p.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(x - 5, y - 2)
        path.lineTo(x, y + 3)
        path.lineTo(x + 5, y - 2)
        p.drawPath(path)

    def showPopup(self) -> None:  # type: ignore[override]
        self.about_to_show.emit()
        super().showPopup()


class _DotLabel(QLabel):
    DOT_CENTER_X = theme.SERIAL_DOT_CENTER_X
    TEXT_LEFT_INSET = theme.SERIAL_BADGE_TEXT_INSET

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.dot_color = STATE_OFFLINE

    def set_dot_state(self, state: str) -> None:
        self.dot_color = state
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        color = {
            STATE_OFFLINE: theme.FG_TERTIARY,
            STATE_OPENING: theme.STATUS_WARN,
            STATE_CONNECTED: theme.STATUS_OK,
            STATE_ERROR: theme.STATUS_ERROR,
        }.get(self.dot_color, theme.FG_TERTIARY)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        halo = QColor(color)
        halo.setAlpha(theme.EFFECT_HALO_ALPHA)
        p.setBrush(halo)
        p.drawEllipse(
            QPointF(self.DOT_CENTER_X, self.height() / 2),
            6.5,
            6.5,
        )
        p.setBrush(QColor(color))
        p.drawEllipse(
            QPointF(self.DOT_CENTER_X, self.height() / 2),
            3.5,
            3.5,
        )


class SerialBar(QWidget):
    """Top serial bar with explicit connection state semantics."""

    open_requested = Signal(str, int)
    close_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("serialBar")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(
            theme.SERIAL_HEADER_WIDTH,
            theme.SERIAL_HEADER_HEIGHT,
        )

        # 全部左对齐, 不放 stretch
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(12)

        self.port_combo = _ChevronCombo()
        self.port_combo.setFixedSize(
            theme.SERIAL_COMBO_WIDTH,
            theme.SERIAL_CONTROL_HEIGHT,
        )
        lay.addWidget(self.port_combo, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.port_combo.about_to_show.connect(self.refresh_requested)

        self.status_badge = _DotLabel("OFFLINE")
        self.status_badge.setObjectName("connectionBadge")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedSize(
            theme.SERIAL_BADGE_WIDTH,
            theme.SERIAL_CONTROL_HEIGHT,
        )
        badge_font = QFont(theme.FONT_DISPLAY)
        badge_font.setPointSize(theme.SERIAL_CONTROL_FONT_SIZE)
        badge_font.setBold(True)
        self.status_badge.setFont(badge_font)
        lay.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.setFixedSize(
            theme.SERIAL_BUTTON_WIDTH,
            theme.SERIAL_CONTROL_HEIGHT,
        )
        button_font = QFont(theme.FONT_DISPLAY)
        button_font.setPointSize(theme.SERIAL_CONTROL_FONT_SIZE)
        button_font.setBold(True)
        self.connect_btn.setFont(button_font)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        lay.addWidget(self.connect_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.refresh_ports()
        self._set_connection_state(STATE_OFFLINE, "OFFLINE")

    # ---- 公开 API ----
    def refresh_ports(self) -> None:
        cur = self.port_combo.currentData()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for p in QSerialPortInfo.availablePorts():
            desc = _strip_cjk(p.description() or "Serial Port")
            self.port_combo.addItem(f"{p.portName()} — {desc}", p.portName())
        if cur:
            idx = self.port_combo.findData(cur)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        self.port_combo.blockSignals(False)

    def set_connected(self, port_name: str, baudrate: int) -> None:
        """已打开串口."""
        self._set_connection_state(STATE_OPENING, "CONNECTING")
        self.port_combo.setEnabled(False)

    def set_handshake_ok(self, port_name: str) -> None:
        """握手成功."""
        self._set_connection_state(STATE_CONNECTED, "CONNECTED")
        self.port_combo.setEnabled(False)

    def set_handshake_failed(self, reason: str) -> None:
        """握手失败."""
        self._set_connection_state(STATE_ERROR, "ERROR")

    def set_disconnected(self) -> None:
        """未连接."""
        self._set_connection_state(STATE_OFFLINE, "OFFLINE")
        self.port_combo.setEnabled(True)

    # ---- 内部 ----
    def _set_connection_state(self, state: str, label: str) -> None:
        is_offline = state == STATE_OFFLINE
        self.connect_btn.setText("CONNECT" if is_offline else "DISCONNECT")
        self.connect_btn.setProperty("connectionState", state)
        self.status_badge.setText(label)
        self.status_badge.setProperty("connectionState", state)
        self.status_badge.set_dot_state(state)

        for widget in (self.connect_btn, self.status_badge):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def refresh_theme(self) -> None:
        self.port_combo.refresh_theme()
        self.status_badge.update()
        self.connect_btn.update()

    def _is_connected(self) -> bool:
        return self.connect_btn.property("connectionState") != STATE_OFFLINE

    def _on_connect_clicked(self) -> None:
        if self._is_connected():
            self.close_requested.emit()
            return
        port = self.port_combo.currentData()
        if not port:
            return
        self.open_requested.emit(port, 9600)
