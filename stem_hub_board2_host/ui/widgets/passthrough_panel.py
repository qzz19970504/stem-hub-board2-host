"""UART 透传面板 (板2 版).

功能:
- 透传目标: UART2 / UART3 / UART2&3 / 退出 (4 态互斥, 对应 AT+TRANS=1|2|1&2 与 +++)
- 发送框: 多行输入 + hex/文本切换
- 接收区: 滚动显示 +UARTxRX 事件解码后的数据, hex + 文本双视图
- 计数: TX / RX 字节
- 清空 / 自动滚动
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .. import theme


def text_to_bytes(s: str) -> bytes:
    """'AA BB CC' -> b'\\xaa\\xbb\\xcc' (允许空格 / '-' 分隔, 大小写无关)."""
    compact = "".join(
        character
        for character in s
        if not character.isspace() and character not in ",-"
    )
    if (
        not compact
        or len(compact) % 2
        or any(character not in "0123456789abcdefABCDEF" for character in compact)
    ):
        return b""
    try:
        return bytes.fromhex(compact)
    except ValueError:
        return b""


def bytes_to_hex(b: bytes) -> str:
    """b'\\xaa\\xbb' -> 'AA BB'."""
    return " ".join(f"{x:02X}" for x in b)


def bytes_to_text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1", errors="replace")


class PassthroughPanel(QFrame):
    """UART 透传面板."""

    # target: '1' / '2' / '1&2' / 'off'
    bridge_changed = Signal(str)
    # 发送 (bytes) — 透传模式下按原字节直发
    tx_requested = Signal(bytes)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("passthroughLayout")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._rx_buffer = bytearray()
        self._auto_scroll = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(theme.GRID_GAP)

        # 透传目标 — segmented chips
        self.bridge_panel = QFrame(self)
        self.bridge_panel.setObjectName("card")
        bridge_row = QHBoxLayout(self.bridge_panel)
        bridge_row.setContentsMargins(14, 10, 14, 10)
        bridge_row.setSpacing(8)
        outer.addWidget(self.bridge_panel)

        bridge_title = QLabel("TRANSPARENT TARGET")
        bridge_title.setObjectName("sectionTitle")
        bridge_row.addWidget(bridge_title)
        bridge_row.addSpacing(8)
        self.btn_uart2 = QRadioButton("UART2")
        self.btn_uart3 = QRadioButton("UART3")
        self.btn_both = QRadioButton("UART2 + UART3")
        self.btn_off = QRadioButton("EXIT (+++)")
        self.btn_off.setChecked(True)
        for control in (
            self.btn_uart2,
            self.btn_uart3,
            self.btn_both,
            self.btn_off,
        ):
            control.setObjectName("modeChip")
            control.setCursor(Qt.CursorShape.PointingHandCursor)
            bridge_row.addWidget(control)
        bridge_row.addStretch(1)

        self.mode_hint = QLabel("AT 模式 — 选择目标后进入透传")
        self.mode_hint.setObjectName("secondary")
        self._apply_mode_style(False)
        bridge_row.addWidget(self.mode_hint)

        self._bridge_group = QButtonGroup(self)
        self._bridge_group.setExclusive(True)
        for b in (self.btn_uart2, self.btn_uart3, self.btn_both, self.btn_off):
            self._bridge_group.addButton(b)
        self._bridge_group.buttonClicked.connect(self._on_bridge_changed)

        # 主区域: 左发送 / 右接收
        body = QHBoxLayout()
        body.setSpacing(theme.GRID_GAP)
        outer.addLayout(body, 1)

        # 发送
        self.tx_panel = QFrame(self)
        self.tx_panel.setObjectName("card")
        tx_col = QVBoxLayout(self.tx_panel)
        tx_col.setContentsMargins(14, 14, 14, 14)
        tx_col.setSpacing(10)
        body.addWidget(self.tx_panel, 1)

        tx_header = QHBoxLayout()
        tx_col.addLayout(tx_header)
        tx_title = QLabel("TRANSMIT")
        tx_title.setObjectName("sectionTitle")
        tx_header.addWidget(tx_title)
        self.hex_mode_cb = QCheckBox("HEX MODE")
        self.hex_mode_cb.toggled.connect(self._on_hex_mode_toggled)
        tx_header.addWidget(self.hex_mode_cb)
        tx_header.addStretch(1)

        self.tx_edit = QPlainTextEdit()
        self.tx_edit.setPlaceholderText(
            "文本模式: 直接输入文本, 按原字节透传 (不补 CRLF)\n"
            "Hex 模式: 输入 AA BB CC DD ..."
        )
        self.tx_edit.setMinimumHeight(240)
        tx_col.addWidget(self.tx_edit)

        tx_btn_row = QHBoxLayout()
        tx_col.addLayout(tx_btn_row)
        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("primary")
        self.send_btn.clicked.connect(self._on_send)
        tx_btn_row.addWidget(self.send_btn)
        self.clear_tx_btn = QPushButton("CLEAR TX")
        self.clear_tx_btn.setObjectName("secondaryAction")
        self.clear_tx_btn.clicked.connect(lambda: self.tx_edit.clear())
        tx_btn_row.addWidget(self.clear_tx_btn)
        tx_btn_row.addStretch(1)

        self.tx_count_label = QLabel("TX: 0 字节")
        self.tx_count_label.setObjectName("secondary")
        tx_btn_row.addSpacing(12)
        tx_btn_row.addWidget(self.tx_count_label)

        # 接收
        self.rx_panel = QFrame(self)
        self.rx_panel.setObjectName("card")
        rx_col = QVBoxLayout(self.rx_panel)
        rx_col.setContentsMargins(14, 14, 14, 14)
        rx_col.setSpacing(10)
        body.addWidget(self.rx_panel, 1)

        rx_header = QHBoxLayout()
        rx_col.addLayout(rx_header)
        rx_title = QLabel("RECEIVE")
        rx_title.setObjectName("sectionTitle")
        rx_header.addWidget(rx_title)
        self.show_hex_cb = QCheckBox("HEX VIEW")
        self.show_hex_cb.setChecked(False)
        self.show_hex_cb.toggled.connect(self._refresh_rx_view)
        rx_header.addWidget(self.show_hex_cb)
        self.auto_scroll_cb = QCheckBox("AUTO SCROLL")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(
            lambda c: setattr(self, "_auto_scroll", c)
        )
        rx_header.addWidget(self.auto_scroll_cb)
        rx_header.addStretch(1)

        self.rx_view = QPlainTextEdit()
        self.rx_view.setReadOnly(True)
        self.rx_view.setMaximumBlockCount(2000)
        self.rx_view.setFont(QFont(theme.FONT_MONO, 12))
        rx_col.addWidget(self.rx_view, 1)

        # RX panel footer
        bottom = QHBoxLayout()
        rx_col.addLayout(bottom)
        self.rx_count_label = QLabel("RX: 0 字节")
        self.rx_count_label.setObjectName("secondary")
        bottom.addWidget(self.rx_count_label)
        bottom.addStretch(1)
        self.clear_rx_btn = QPushButton("CLEAR RX")
        self.clear_rx_btn.setObjectName("secondaryAction")
        self.clear_rx_btn.clicked.connect(self._clear_rx)
        bottom.addWidget(self.clear_rx_btn)

    # ---- API ----
    def feed_rx(self, data: bytes) -> None:
        """从 SerialWorker 收到 +UARTxRX 事件数据时调."""
        self._rx_buffer.extend(data)
        self._rx_bytes += len(data)
        self._refresh_rx_view()
        self.rx_count_label.setText(f"RX: {self._rx_bytes} 字节")

    def reset(self) -> None:
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._rx_buffer.clear()
        self._refresh_rx_view()
        self._refresh_count()

    # ---- 内部 ----
    def _on_bridge_changed(self, btn: QRadioButton) -> None:
        if btn is self.btn_uart2:
            mode = "1"
        elif btn is self.btn_uart3:
            mode = "2"
        elif btn is self.btn_both:
            mode = "1&2"
        else:
            mode = "off"
        self.bridge_changed.emit(mode)

    def _on_hex_mode_toggled(self, hex_mode: bool) -> None:
        if hex_mode:
            self.tx_edit.setPlaceholderText("Hex 模式: AA BB CC DD ...（按原字节透传）")
        else:
            self.tx_edit.setPlaceholderText("文本模式: 直接输入文本, 按原字节透传")

    def _on_send(self) -> None:
        text = self.tx_edit.toPlainText()
        if not text:
            return
        if self.hex_mode_cb.isChecked():
            data = text_to_bytes(text)
        else:
            data = text.encode("utf-8")
        if not data:
            return
        self.tx_requested.emit(data)

    def confirm_tx_sent(self, byte_count: int) -> None:
        """Commit UI state only after the transport accepted the bytes."""
        self._tx_bytes += byte_count
        self._refresh_count()
        self.tx_edit.clear()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.set_bridge_controls_enabled(enabled)
        self.set_tx_controls_enabled(enabled)

    def set_bridge_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.btn_uart2,
            self.btn_uart3,
            self.btn_both,
            self.btn_off,
        ):
            control.setEnabled(enabled)

    def set_tx_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.hex_mode_cb,
            self.tx_edit,
            self.send_btn,
            self.clear_tx_btn,
        ):
            control.setEnabled(enabled)

    def set_bridge_mode(self, mode: str) -> None:
        target = {
            "1": self.btn_uart2,
            "2": self.btn_uart3,
            "1&2": self.btn_both,
            "off": self.btn_off,
        }.get(mode, self.btn_off)
        blocked = self._bridge_group.signalsBlocked()
        self._bridge_group.blockSignals(True)
        target.setChecked(True)
        self._bridge_group.blockSignals(blocked)
        if mode == "off":
            self.mode_hint.setText("AT 模式 — 选择目标后进入透传")
            self._apply_mode_style(False)
        else:
            # 目标 '1'/'2' 对应固件通道编号, 实际串口是 UART2/UART3
            target_label = {
                "1": "UART2",
                "2": "UART3",
                "1&2": "UART2 + UART3",
            }[mode]
            self.mode_hint.setText(
                f"透传中: UART1 → {target_label} (输入 +++ 退出)"
            )
            self._apply_mode_style(True)

    def _apply_mode_style(self, active: bool) -> None:
        color = theme.ACCENT if active else theme.FG_SECONDARY
        self.mode_hint.setStyleSheet(
            f"color: {color}; font-weight: {'700' if active else '400'};"
            " background: transparent;"
        )

    def refresh_theme(self) -> None:
        active = self.mode_hint.text().startswith("透传中")
        self._apply_mode_style(active)

    def _refresh_rx_view(self) -> None:
        if self.show_hex_cb.isChecked():
            display = bytes_to_hex(self._rx_buffer)
        else:
            display = bytes_to_text(bytes(self._rx_buffer))
        self.rx_view.setPlainText(display)
        if self._auto_scroll:
            sb = self.rx_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _clear_rx(self) -> None:
        self._rx_buffer.clear()
        self._refresh_rx_view()

    def _refresh_count(self) -> None:
        self.tx_count_label.setText(f"TX: {self._tx_bytes} 字节")
        self.rx_count_label.setText(f"RX: {self._rx_bytes} 字节")
