"""AT 指令控制台 (移植自 stem-hub-host, 板2 命令占位符调整)."""
from __future__ import annotations

import time
from collections import deque
from html import escape

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import theme


class AtConsole(QFrame):
    """AT 指令控制台 — 一整块框 + cyan 辉光.

    - log 区: 背景同卡片色, 无边框
    - 发送区: 一个圆角框 (含 > 提示符, 输入框, SEND 按钮)
    """

    send_requested = Signal(str)
    LOG_RETENTION_SECONDS = 180.0
    MAX_LOG_ENTRIES = 2000
    MAX_DOCUMENT_BLOCKS = 2200

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._entries: deque[tuple[float, str, str]] = deque()
        # cyan 外发光
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(12)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(theme.ACCENT_DEEP))
        self.setGraphicsEffect(self._glow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        # log 区 — 无边框, 仅背景同卡片色
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(self.MAX_DOCUMENT_BLOCKS)
        self.log_view.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.log_view.customContextMenuRequested.connect(
            self._show_log_context_menu
        )
        self.log_view.setFrameShape(QFrame.Shape.NoFrame)
        f_log = QFont(theme.FONT_MONO)
        f_log.setPointSizeF(13.5)
        self.log_view.setFont(f_log)
        outer.addWidget(self.log_view, 1)

        # 发送区 — 一个圆角框
        self.command_bar = QFrame()
        self.command_bar.setObjectName("commandBar")
        send_row = QHBoxLayout(self.command_bar)
        send_row.setContentsMargins(14, 8, 14, 8)
        send_row.setSpacing(10)

        # > 提示符
        self.prompt = QLabel(">")
        f_p = QFont(theme.FONT_MONO)
        f_p.setPointSize(17)
        f_p.setBold(True)
        self.prompt.setFont(f_p)
        self.prompt.setFixedWidth(18)
        send_row.addWidget(self.prompt)

        # 输入框 (无边框, 透明背景融入 send_bar)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("AT+STATUS=?")
        self.input_edit.returnPressed.connect(self._on_send)
        self.input_edit.setFixedHeight(theme.CONTROL_HEIGHT)
        f_in = QFont(theme.FONT_MONO)
        f_in.setPointSize(14)
        self.input_edit.setFont(f_in)
        send_row.addWidget(self.input_edit, 1)

        # SEND 按钮
        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("primary")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedHeight(theme.CONTROL_HEIGHT)
        self.send_btn.setMinimumWidth(120)
        f_btn = QFont(theme.FONT_DISPLAY)
        f_btn.setPointSize(14)
        f_btn.setBold(True)
        self.send_btn.setFont(f_btn)
        self.send_btn.clicked.connect(self._on_send)
        send_row.addWidget(self.send_btn)

        outer.addWidget(self.command_bar)
        self.refresh_theme()

    def _on_send(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.append_log("TX", text)
        cmd = text if text.endswith("\r\n") else text + "\r\n"
        self.send_requested.emit(cmd)
        self.input_edit.clear()

    def append_log(self, direction: str, text: str) -> None:
        now = time.monotonic()
        self._entries.append((now, direction, text))
        cutoff = now - self.LOG_RETENTION_SECONDS
        trimmed_count = 0
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()
            trimmed_count += 1
        while len(self._entries) > self.MAX_LOG_ENTRIES:
            self._entries.popleft()
            trimmed_count += 1
        self._remove_leading_rendered_entries(trimmed_count)
        self._append_rendered_entry(direction, text)

    def _remove_leading_rendered_entries(self, count: int) -> None:
        for _ in range(count):
            cursor = QTextCursor(self.log_view.document())
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _render_entries(self) -> None:
        self.log_view.clear()
        for _timestamp, direction, text in self._entries:
            self._append_rendered_entry(direction, text)

    def _create_log_context_menu(self) -> QMenu:
        menu = self.log_view.createStandardContextMenu()
        menu.addSeparator()
        clear_action = menu.addAction("清除全部")
        clear_action.triggered.connect(self.clear_log)
        return menu

    def _show_log_context_menu(self, position: QPoint) -> None:
        menu = self._create_log_context_menu()
        menu.exec(self.log_view.viewport().mapToGlobal(position))
        menu.deleteLater()

    def clear_log(self) -> None:
        self._entries.clear()
        self.log_view.clear()

    def _append_rendered_entry(self, direction: str, text: str) -> None:
        prefix_map = {
            "TX":  (">>", theme.ACCENT),
            "RX":  ("<<", theme.STATUS_OK),
            "INFO": ("··", theme.FG_SECONDARY),
            "ERR": ("!!", theme.STATUS_ERROR),
        }
        prefix, color = prefix_map.get(direction, ("??", theme.FG_PRIMARY))
        normalized_text = text.replace("\r\n", "↵\n").replace("\r", "↵")
        escaped_text = escape(normalized_text)
        escaped_prefix = escape(prefix)
        message_color = color
        if direction == "RX" and normalized_text.strip() != "OK":
            message_color = theme.FG_PRIMARY
        self.log_view.appendHtml(
            f'<span style="color: {color}; font-weight: 700;">{escaped_prefix}</span> '
            f'<span style="color: {message_color}; font-family: \'{theme.FONT_MONO}\';">'
            f"{escaped_text}</span>"
        )
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_theme(self) -> None:
        self._glow.setColor(QColor(theme.ACCENT_DEEP))
        self.log_view.setStyleSheet(
            "QPlainTextEdit {"
            "  background: transparent;"
            f"  color: {theme.FG_PRIMARY};"
            "  border: none;"
            "  padding: 8px;"
            "}"
        )
        self.prompt.setStyleSheet(
            f"color: {theme.ACCENT}; background: transparent; border: none;"
        )
        self.input_edit.setStyleSheet(
            "QLineEdit {"
            "  background: transparent;"
            f"  color: {theme.FG_PRIMARY};"
            "  border: none;"
            "  padding: 4px 8px;"
            f"  selection-background-color: {theme.ACCENT};"
            f"  selection-color: {theme.BG_BASE};"
            "}"
        )
        if self._entries:
            self._render_entries()

    def append_info(self, text: str) -> None:
        self.append_log("INFO", text)

    def append_error(self, text: str) -> None:
        self.append_log("ERR", text)
