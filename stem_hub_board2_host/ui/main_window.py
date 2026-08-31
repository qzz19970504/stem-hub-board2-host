"""Main window and controller-to-UI state binding (板2 版)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..at_protocol import cmd_raw
from ..branding import APP_DISPLAY_NAME, load_app_icon
from ..controller import Controller
from ..models import StatusState
from . import native_chrome
from .stylesheet import apply_to
from .tab1_console import ConsoleTab
from .tab2_passthrough import PassthroughTab
from . import theme
from .widgets.serial_bar import SerialBar
from .widgets.theme_toggle import ThemeToggleButton


# 板2 错误码 → 用户可读说明
ERROR_DESCRIPTIONS = {
    "PARSE": "未知命令或格式错误",
    "RANGE": "参数超出范围 (PWM ≤ 100, HEX ≤ 32 字节)",
    "UART_DISABLED": "AT 模式下没有启用透传目标",
    "UART_TX": "固件串口发送失败",
    "LINE_TOO_LONG": "输入帧超过 127 字节",
    "RX_OVERFLOW": "固件接收缓冲溢出",
    "12V_DISABLED": "12V 未开启，不能开启 NMOS",
    "18V_DISABLED": "18V 未开启，PWM 只能为 0",
    "BREATH_ACTIVE": "呼吸灯演示期间不接受普通 PWM 命令",
    "STORAGE": "渐变时间写入 Flash 失败",
    "TIMEOUT": "响应超时",
}

WINDOW_W = theme.WINDOW_WIDTH
WINDOW_H = theme.WINDOW_HEIGHT
QT_WIDGET_SIZE_LIMIT = (1 << 24) - 1


def describe_error(code: str) -> str:
    return ERROR_DESCRIPTIONS.get(code, "未知错误")


class MainWindow(QMainWindow):
    """上位机主窗口."""

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self._controller = controller
        self._handshake_connected = False
        self._passthrough_transition_active = False
        self._passthrough_mode = "off"
        self._latest_status: StatusState | None = None
        self._appearance_settings = QSettings()
        saved_scheme = str(
            self._appearance_settings.value("appearance/colorScheme", "dark")
        )
        if saved_scheme not in {"dark", "light"}:
            saved_scheme = "dark"
        theme.set_color_scheme(saved_scheme)
        self.color_scheme = saved_scheme
        self._normal_geometry = None
        self._was_maximized_before_fullscreen = False

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(load_app_icon())

        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.setMaximumSize(QT_WIDGET_SIZE_LIMIT, QT_WIDGET_SIZE_LIMIT)
        self.resize(WINDOW_W, WINDOW_H)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)

        # 状态栏 (隐藏 — 设计稿没有)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setFixedHeight(0)
        self.statusBar().setVisible(False)

        self.root = QFrame(self)
        self.root.setObjectName("rootContainer")
        self.setCentralWidget(self.root)

        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 顶部: Tab (无全屏按钮)
        self.tabs = QTabWidget(self.root)
        self.console_tab = ConsoleTab()
        self.passthrough_tab = PassthroughTab()
        self.tabs.addTab(self.console_tab, "CONSOLE")
        self.tabs.addTab(self.passthrough_tab, "PASSTHROUGH")
        self.serial_bar = SerialBar(self.tabs)
        self.theme_toggle = ThemeToggleButton(self.color_scheme, self.tabs)
        self.theme_toggle.scheme_changed.connect(self.set_color_scheme)
        root_lay.addWidget(self.tabs)
        self.tabs.installEventFilter(self)
        self.tabs.tabBar().installEventFilter(self)
        QTimer.singleShot(0, self._position_theme_toggle)

        # ---- UI signal -> Controller ----
        self.serial_bar.open_requested.connect(self._on_open_serial)
        self.serial_bar.close_requested.connect(self._on_close_serial)
        self.serial_bar.refresh_requested.connect(self.serial_bar.refresh_ports)
        self.console_tab.power12_changed.connect(self._controller.set_power_12v)
        self.console_tab.power18_changed.connect(self._controller.set_power_18v)
        self.console_tab.nmos_changed.connect(self._on_nmos_changed)
        self.console_tab.pwm_changed.connect(self._controller.set_pwm)
        self.console_tab.pwm_time_changed.connect(self._controller.set_pwm_time)
        self.console_tab.breath_changed.connect(self._controller.set_breath)
        self.console_tab.at_send.connect(self._on_at_send)
        self.passthrough_tab.panel.bridge_changed.connect(
            self._on_bridge_changed
        )
        self.passthrough_tab.panel.tx_requested.connect(self._on_passthrough_tx)

        # ---- Controller -> UI ----
        self._controller.worker.connected.connect(self._on_worker_connected)
        self._controller.worker.disconnected.connect(self._on_worker_disconnected)
        self._controller.error_occurred.connect(self._on_worker_error)
        self._controller.handshake_failed.connect(self._on_handshake_failed)
        self._controller.handshake_completed.connect(self._on_handshake_completed)
        self._controller.worker.response_received.connect(self._on_response)
        self._controller.worker.uart_rx_received.connect(self._on_uart_rx)
        self._controller.worker.at_data_received.connect(self._on_at_data)
        self._controller.status_changed.connect(self._on_status_changed)
        self._controller.passthrough_tx_confirmed.connect(
            self.passthrough_tab.panel.confirm_tx_sent
        )
        self._controller.command_failed.connect(self._on_command_failed)
        self._controller.passthrough_mode_changed.connect(
            self._on_passthrough_mode_changed
        )
        self._controller.passthrough_transition_changed.connect(
            self._on_passthrough_transition_changed
        )

        from ..app import get_app
        apply_to(get_app())
        QTimer.singleShot(0, self._apply_native_title_bar)

        # 初始: 未连接 → 所有交互禁用
        self._apply_handshake_gate(connected=False)

    def set_color_scheme(
        self,
        scheme: str,
        *,
        persist: bool = True,
    ) -> None:
        """Switch the complete application palette without losing UI state."""

        if scheme not in {"dark", "light"}:
            return
        self.setUpdatesEnabled(False)
        try:
            theme.set_color_scheme(scheme)
            self.color_scheme = scheme
            self.theme_toggle.set_color_scheme(scheme)
            from ..app import get_app
            apply_to(get_app())

            for widget in self.findChildren(QWidget):
                refresh = getattr(widget, "refresh_theme", None)
                if callable(refresh):
                    refresh()
            native_chrome.apply_windows_title_bar(self, scheme)
        finally:
            self.setUpdatesEnabled(True)
            self.update()

        if persist:
            self._appearance_settings.setValue("appearance/colorScheme", scheme)

    def _apply_native_title_bar(self) -> None:
        """Synchronize the Windows caption after its native handle exists."""

        native_chrome.apply_windows_title_bar(self, self.color_scheme)

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen while restoring the previous normal window state."""

        if self.isFullScreen():
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()
                if self._normal_geometry is not None:
                    self.setGeometry(self._normal_geometry)
            return

        self._was_maximized_before_fullscreen = self.isMaximized()
        if not self._was_maximized_before_fullscreen:
            self._normal_geometry = self.geometry()
        self.showFullScreen()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if (
            watched in (self.tabs, self.tabs.tabBar())
            and event.type() == QEvent.Type.Resize
        ):
            self._position_theme_toggle()
            return super().eventFilter(watched, event)

        if event.type() != QEvent.Type.MouseButtonDblClick:
            return super().eventFilter(watched, event)

        tab_bar = self.tabs.tabBar()
        if watched is tab_bar and tab_bar.tabAt(event.position().toPoint()) >= 0:
            return super().eventFilter(watched, event)
        if watched is self.tabs or watched is tab_bar:
            self.toggle_fullscreen()
            return True
        return super().eventFilter(watched, event)

    def _position_theme_toggle(self) -> None:
        """Place persistent serial and theme controls in the tab header."""

        if not hasattr(self, "theme_toggle") or not hasattr(self, "serial_bar"):
            return
        tab_bar = self.tabs.tabBar()
        toggle_x = max(
            0,
            self.tabs.width() - self.theme_toggle.width() - theme.PAGE_MARGIN_X,
        )
        serial_x = (
            toggle_x
            - theme.SERIAL_HEADER_GAP
            - self.serial_bar.width()
        )
        header_height = max(tab_bar.height(), theme.SERIAL_HEADER_HEIGHT)
        serial_y = max(
            0,
            (header_height - self.serial_bar.height()) // 2,
        )
        toggle_y = max(
            0,
            (header_height - self.theme_toggle.height()) // 2,
        )
        self.serial_bar.move(serial_x, serial_y)
        self.theme_toggle.move(toggle_x, toggle_y)
        self.serial_bar.show()
        self.serial_bar.raise_()
        self.theme_toggle.raise_()

    # ---- 门禁与联锁 ----
    def _apply_handshake_gate(self, connected: bool) -> None:
        """握手成功后才启用设备控制。"""
        self._handshake_connected = connected
        self._refresh_control_gates()

    def _on_passthrough_transition_changed(self, active: bool) -> None:
        self._passthrough_transition_active = active
        self._refresh_control_gates()

    def _on_passthrough_mode_changed(self, mode: str) -> None:
        self._passthrough_mode = mode
        self.passthrough_tab.panel.set_bridge_mode(mode)
        self._refresh_control_gates()

    def _on_status_changed(self, status: StatusState | None) -> None:
        self._latest_status = status
        self.console_tab.status_card.update_from_status(status)
        # 同步各卡片开关位置到固件确认状态
        console = self.console_tab
        if status is None:
            console.power_card.set_state(power_12v=False, power_18v=False)
            console.nmos_card.set_state({1: False, 2: False, 3: False})
            console.pwm_card.reset_input()
            return
        console.power_card.set_state(
            power_12v=status.power_12v, power_18v=status.power_18v
        )
        console.nmos_card.set_state(
            {1: status.nmos1, 2: status.nmos2, 3: status.nmos3}
        )
        console.pwm_card.update_state(
            pwm=status.pwm,
            pwm_target=status.pwm_target,
            pwm_time_ms=status.pwm_time_ms,
            breath=status.breath,
        )
        # 联锁门禁依赖最新状态, 状态变化后立即刷新
        self._refresh_control_gates()

    def _refresh_control_gates(self) -> None:
        standard_enabled = (
            self._handshake_connected
            and self._passthrough_mode == "off"
            and not self._passthrough_transition_active
        )
        console = self.console_tab
        console.power_card.set_controls_enabled(standard_enabled)

        # 12V 联锁: NMOS 卡
        nmos_available = (
            standard_enabled
            and self._latest_status is not None
            and self._latest_status.power_12v
        )
        console.nmos_card.set_controls_enabled(standard_enabled)
        console.nmos_card.set_rail_available(nmos_available)

        # 18V 联锁: PWM 卡
        pwm_available = (
            standard_enabled
            and self._latest_status is not None
            and self._latest_status.power_18v
        )
        console.pwm_card.set_controls_enabled(standard_enabled)
        console.pwm_card.set_rail_available(pwm_available)

        console.at_console.input_edit.setEnabled(standard_enabled)
        console.at_console.send_btn.setEnabled(standard_enabled)

        bridge_enabled = (
            self._handshake_connected
            and not self._passthrough_transition_active
        )
        tx_enabled = (
            self._handshake_connected
            and self._passthrough_mode != "off"
            and not self._passthrough_transition_active
        )
        panel = self.passthrough_tab.panel
        panel.set_bridge_controls_enabled(bridge_enabled)
        panel.set_tx_controls_enabled(tx_enabled)

        self._refresh_connection_hint()

    def _refresh_connection_hint(self) -> None:
        """按连接/透传状态更新控制台底部引导条."""
        hint = self.console_tab.conn_hint
        if not self._controller.worker.is_open():
            text = "未连接：选择串口并点击 CONNECT (固定 9600 8N1)"
            color = theme.FG_SECONDARY
        elif not self._handshake_connected:
            text = "串口已打开，握手中… (AT+STATUS=?)"
            color = theme.STATUS_WARN
        elif self._passthrough_mode != "off":
            target_label = {
                "1": "UART2",
                "2": "UART3",
                "1&2": "UART2 + UART3",
            }.get(self._passthrough_mode, self._passthrough_mode)
            text = (
                f"透传中 (UART1 → {target_label})："
                "控制台控制暂停，请切到 PASSTHROUGH 页操作"
            )
            color = theme.STATUS_WARN
        else:
            text = "已连接：状态每秒自动回读，开关位置以回读为准"
            color = theme.STATUS_OK
        hint.setText(text)
        hint.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

    # ---- 串口 ----
    def _on_open_serial(self, port: str, baud: int) -> None:
        if not self._controller.open(port, baud):
            self.serial_bar.set_disconnected()
            self.console_tab.at_console.append_error(f"Open failed: {port}")
            QMessageBox.warning(
                self,
                "连接失败",
                f"无法打开串口 {port}。\n\n请检查端口是否被占用后重试。",
            )

    def _on_close_serial(self) -> None:
        self._controller.close()

    def _on_at_send(self, cmd: str) -> None:
        self._controller.send_raw(cmd_raw(cmd.strip()))

    def _on_nmos_changed(self, idx: int, on: bool) -> None:
        self._controller.set_nmos(idx, on)

    def _on_bridge_changed(self, target: str) -> None:
        if target == "off":
            self._controller.exit_transparent()
        else:
            self._controller.enter_transparent(target)

    def _on_passthrough_tx(self, data: bytes) -> None:
        if not self._controller.send_transparent_bytes(data):
            self._on_worker_error("透传发送失败: 未连接或不在透传模式")

    def _on_command_failed(self, control: str, reason: str) -> None:
        self.console_tab.at_console.append_error(
            f"{control} 失败: {reason} — {describe_error(reason)}"
        )

    def _on_handshake_failed(self, reason: str) -> None:
        self._apply_handshake_gate(connected=False)
        self.serial_bar.set_handshake_failed(reason)
        self.console_tab.at_console.append_error(f"连接失败: {reason}")
        QMessageBox.warning(
            self,
            "连接失败",
            "串口已打开，但未能在 5 秒内完成设备握手。\n"
            f"原因：{reason}\n\n"
            "板2 握手使用 AT+STATUS=?，请检查端口、波特率 (9600) 和下位机状态。",
        )

    def _on_worker_connected(self, port: str, baud: int) -> None:
        self.serial_bar.set_connected(port, baud)
        self.console_tab.at_console.append_info(f"Opened: {port} @ {baud}")

    def _on_worker_disconnected(self) -> None:
        self.serial_bar.set_disconnected()
        self.console_tab.at_console.append_info("Disconnected")
        self._on_status_changed(None)
        self._apply_handshake_gate(connected=False)

    def _on_worker_error(self, msg: str) -> None:
        self.console_tab.at_console.append_error(msg)

    def _on_handshake_completed(self) -> None:
        """握手成功只提示一次, 后续轮询不再重复."""
        if self._handshake_connected:
            return
        self.serial_bar.set_handshake_ok("board2")
        self.console_tab.at_console.append_info("Handshake OK: board2 AT ready")
        self._apply_handshake_gate(connected=True)

    def _on_response(self, cmd: str, resp) -> None:
        stripped = cmd.strip()
        if resp.ok:
            self.console_tab.at_console.append_log("RX", "OK")
        elif resp.error is not None:
            self.console_tab.at_console.append_error(
                f"{stripped} → {resp.error} — {describe_error(resp.error.code)}"
            )

    def _on_at_data(self, cmd: str, resp) -> None:
        self.console_tab.at_console.append_log("RX", resp.raw_line)

    def _on_uart_rx(self, uart_index: int, data: bytes) -> None:
        if self._controller.passthrough_mode == "off":
            return
        self.passthrough_tab.panel.feed_rx(data)
        display = self._format_serial_payload(data)
        self.console_tab.at_console.append_log(
            "RX", f"[UART{uart_index}] {display}"
        )

    @staticmethod
    def _format_serial_payload(data: bytes) -> str:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return data.hex(" ").upper()
        if all(character.isprintable() or character in "\r\n\t" for character in text):
            return text
        return data.hex(" ").upper()
