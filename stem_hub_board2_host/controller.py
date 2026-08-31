"""Controller — UI <-> SerialWorker 联动.

- 持有 SerialWorker 实例
- 监听 UI 信号 → 翻译成板2 AT 命令下发
- 监听 SerialWorker 响应 → 推送到 UI 更新
- 周期拉取 AT+STATUS=? (1 Hz, 透传期间暂停)
- 握手: 打开串口后 200ms 发起 AT+STATUS=?, 完整回包 + OK 即成功
- 透传: AT+TRANS=x 进入; raw `+++` (静默保护) 退出
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from .at_protocol import (
    CRLF,
    EXIT_TRANSPARENT_BYTES,
    cmd_query_status,
    cmd_set_breath,
    cmd_set_nmos,
    cmd_set_power_12v,
    cmd_set_power_18v,
    cmd_set_pwm,
    cmd_set_pwm_time,
    cmd_trans,
)
from .models import StatusState
from .serial_worker import SerialError, SerialTimeout, SerialWorker


# 发送 +++ 前的静默保护: 覆盖 9600 baud 下最后若干字节的传输时间
EXIT_GUARD_DELAY_MS = 30
TRANS_TARGETS = ("1", "2", "1&2")


class Controller(QObject):
    """UI 与串口之间的胶水."""

    # ---- 状态 ----
    error_occurred = Signal(str)
    handshake_failed = Signal(str)
    handshake_completed = Signal()
    command_failed = Signal(str, str)  # (control, reason)
    status_changed = Signal(object)    # StatusState
    passthrough_mode_changed = Signal(str)   # 'off' / '1' / '2' / '1&2'
    passthrough_transition_changed = Signal(bool)
    passthrough_tx_confirmed = Signal(int)

    def __init__(
        self,
        worker: SerialWorker,
        parent: QObject | None = None,
        *,
        handshake_deadline_ms: int = 5000,
        handshake_retry_ms: int = 1000,
        handshake_attempt_timeout_ms: int = 500,
        handshake_initial_delay_ms: int = 200,
        poll_interval_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._handshake_deadline_ms = handshake_deadline_ms
        self._handshake_retry_ms = handshake_retry_ms
        self._handshake_attempt_timeout_ms = handshake_attempt_timeout_ms
        self._handshake_initial_delay_ms = handshake_initial_delay_ms

        # 状态缓存
        self._is_open = False
        self._handshake_ok = False
        self._connection_attempt_active = False
        self._last_handshake_error = "TIMEOUT"
        self._latest_status: StatusState | None = None
        self._pending_commands: dict[
            str,
            deque[
                tuple[
                    str,
                    Callable[[], None] | None,
                    Callable[[str], None] | None,
                ]
            ],
        ] = defaultdict(deque)
        self._passthrough_mode = "off"
        self._passthrough_transition_active = False
        self._queued_passthrough_mode: str | None = None
        self._exit_pending = False

        # 周期状态轮询
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_once)
        self._poll_timer.setInterval(poll_interval_ms)

        # 握手专用
        self._handshake_delay_timer = QTimer(self)
        self._handshake_delay_timer.setSingleShot(True)
        self._handshake_delay_timer.timeout.connect(self._do_handshake)
        self._handshake_retry_timer = QTimer(self)
        self._handshake_retry_timer.setSingleShot(True)
        self._handshake_retry_timer.timeout.connect(self._do_handshake)
        self._handshake_deadline_timer = QTimer(self)
        self._handshake_deadline_timer.setSingleShot(True)
        self._handshake_deadline_timer.timeout.connect(
            self._fail_connection_attempt
        )

        # 透传退出静默延时
        self._exit_guard_timer = QTimer(self)
        self._exit_guard_timer.setSingleShot(True)
        self._exit_guard_timer.timeout.connect(self._send_exit_sequence)

        # 连 worker 信号 (轮询数据行也要驱动状态更新)
        worker.connected.connect(self._on_worker_connected)
        worker.disconnected.connect(self._on_worker_disconnected)
        worker.error_occurred.connect(self._on_worker_error)
        worker.at_data_received.connect(self._on_at_data)
        worker.poll_data_received.connect(self._on_at_data)
        worker.response_received.connect(self._on_response)

    # ---- 公开 API ----
    @property
    def worker(self) -> SerialWorker:
        return self._worker

    @property
    def is_connected(self) -> bool:
        return self._is_open

    @property
    def is_handshake_ok(self) -> bool:
        return self._handshake_ok

    @property
    def latest_status(self) -> StatusState | None:
        return self._latest_status

    @property
    def passthrough_mode(self) -> str:
        return self._passthrough_mode

    def open(self, port: str, baud: int = 9600) -> bool:
        return self._worker.open(port, baud)

    def close(self) -> None:
        self._connection_attempt_active = False
        self._cancel_handshake_timers()
        self._stop_polling()
        self._worker.close()

    # ---- 周期拉取 ----
    def _start_polling(self) -> None:
        self._poll_timer.start()

    def _stop_polling(self) -> None:
        self._poll_timer.stop()

    def _poll_once(self) -> None:
        """Queue one periodic status query without blocking the UI thread."""
        if (
            not self._is_open
            or not self._handshake_ok
            or self._passthrough_mode != "off"
            or self._passthrough_transition_active
        ):
            return
        try:
            # 周期轮询静默: 响应仍更新状态, 但不刷 AT 终端日志
            self._worker.send_command(cmd_query_status(), silent=True)
        except SerialError as error:
            self._on_worker_error(f"状态查询暂停: {error}")

    def query_status_now(self) -> None:
        if not self._standard_commands_available():
            return
        try:
            self._worker.send_command(cmd_query_status())
        except SerialError as error:
            self._on_worker_error(f"状态查询失败: {error}")

    # ---- 用户操作: AT 控制命令 ----
    def set_power_12v(self, on: bool) -> None:
        self._send_control(cmd_set_power_12v(on), "12V")

    def set_power_18v(self, on: bool) -> None:
        self._send_control(cmd_set_power_18v(on), "18V")

    def set_nmos(self, idx: int, on: bool) -> None:
        self._send_control(cmd_set_nmos(idx, on), f"NMOS{idx}")

    def set_pwm(self, percent: int) -> None:
        self._send_control(cmd_set_pwm(percent), "PWM")

    def set_pwm_time(self, ms: int) -> None:
        self._send_control(cmd_set_pwm_time(ms), "PWM_TIME")

    def set_breath(self, on: bool) -> None:
        self._send_control(cmd_set_breath(on), "BREATH")

    def send_raw(self, cmd: str) -> None:
        """AT 输入框直接发, 不做联锁拦截."""
        if not self._is_open:
            return
        try:
            self._worker.send_command(cmd)
        except SerialError as e:
            self._on_worker_error(f"AT 发送失败: {e}")

    def _send_control(
        self,
        cmd: str,
        control: str,
        on_success: Callable[[], None] | None = None,
        on_failure: Callable[[str], None] | None = None,
        *,
        force: bool = False,
    ) -> None:
        if not self._is_open:
            return
        # 透传切换命令自身需要在 transition 状态下发送, 用 force 绕过门禁
        if not force and not self._standard_commands_available():
            return
        self._pending_commands[cmd].append((control, on_success, on_failure))
        try:
            self._worker.send_command(cmd)
        except SerialError as e:
            self._pending_commands[cmd].pop()
            if not self._pending_commands[cmd]:
                self._pending_commands.pop(cmd, None)
            self.command_failed.emit(control, str(e))
            if on_failure is not None:
                on_failure(str(e))
            self._on_worker_error(f"{control} 命令失败: {e}")

    def _standard_commands_available(self) -> bool:
        return (
            self._is_open
            and self._handshake_ok
            and self._passthrough_mode == "off"
            and not self._passthrough_transition_active
        )

    # ---- 透传 ----
    def enter_transparent(self, target: str) -> None:
        """target: '1' / '2' / '1&2'."""
        if target not in TRANS_TARGETS:
            return
        if not self._is_open:
            return
        if self._passthrough_transition_active or self._exit_pending:
            self._queued_passthrough_mode = target
            return

        self._passthrough_transition_active = True
        self.passthrough_transition_changed.emit(True)

        def confirm() -> None:
            self._apply_passthrough_mode(target)
            self._finish_passthrough_transition()

        def fail(reason: str) -> None:
            self._on_worker_error(f"透传命令失败: {reason}")
            self._finish_passthrough_transition()

        self._send_control(
            cmd_trans(target), f"TRANS={target}", confirm, fail, force=True
        )

    def exit_transparent(self) -> None:
        """发送受静默保护的 +++ 并等待固件 OK."""
        if self._passthrough_mode == "off":
            return
        if self._passthrough_transition_active or self._exit_pending:
            self._queued_passthrough_mode = "off"
            return

        self._passthrough_transition_active = True
        self._exit_pending = True
        self.passthrough_transition_changed.emit(True)
        self._stop_polling()
        # 固件要求 +++ 前后各有 >=1ms 静默; 9600 baud 一字符约 1.04ms,
        # 这里保守等待 30ms 覆盖最后一段用户数据的传输时间.
        self._exit_guard_timer.start(EXIT_GUARD_DELAY_MS)

    def _send_exit_sequence(self) -> None:
        if not self._is_open:
            self._exit_pending = False
            self._finish_passthrough_transition()
            return
        try:
            self._worker.send_bytes(EXIT_TRANSPARENT_BYTES)
            resp = self._worker.await_completion("EXIT_TRANS", timeout_ms=1000)
        except (SerialError, SerialTimeout) as error:
            self._on_worker_error(f"退出透传失败: {error}")
            self._exit_pending = False
            # +++ 可能未被固件消耗, 保持原模式并恢复轮询
            self._finish_passthrough_transition()
            return
        self._exit_pending = False
        if resp.ok:
            self._apply_passthrough_mode("off")
        else:
            reason = resp.error.code if resp.error is not None else "UNKNOWN"
            self._on_worker_error(f"退出透传失败: {reason}")
        self._finish_passthrough_transition()

    def send_transparent_bytes(self, data: bytes) -> bool:
        """透传模式下按原字节发送到已选目标."""
        if (
            not self._is_open
            or not self._handshake_ok
            or self._passthrough_mode == "off"
            or self._passthrough_transition_active
            or not data
        ):
            return False
        try:
            self._worker.send_bytes(data)
        except SerialError as error:
            self._on_worker_error(f"透传发送失败: {error}")
            return False
        self.passthrough_tx_confirmed.emit(len(data))
        return True

    def _apply_passthrough_mode(self, mode: str) -> None:
        self._passthrough_mode = mode
        if mode == "off":
            # 退出透传会清空目标, 恢复 AT 模式轮询
            if self._is_open and self._handshake_ok:
                self._start_polling()
        else:
            self._stop_polling()
        self.passthrough_mode_changed.emit(mode)

    def _finish_passthrough_transition(self) -> None:
        next_mode = self._queued_passthrough_mode
        self._queued_passthrough_mode = None
        if (
            next_mode is not None
            and next_mode != self._passthrough_mode
            and self._is_open
        ):
            self._passthrough_transition_active = False
            if next_mode == "off":
                self.exit_transparent()
            else:
                self.enter_transparent(next_mode)
            return

        self._passthrough_transition_active = False
        self.passthrough_transition_changed.emit(False)

    # ---- Worker 信号处理 ----
    def _on_worker_connected(self, port: str, baud: int) -> None:
        self._is_open = True
        self._handshake_ok = False
        self._connection_attempt_active = True
        self._last_handshake_error = "TIMEOUT"
        self._cancel_handshake_timers()
        self._handshake_deadline_timer.start(self._handshake_deadline_ms)
        self._handshake_delay_timer.start(self._handshake_initial_delay_ms)

    def _on_worker_disconnected(self) -> None:
        self._is_open = False
        self._handshake_ok = False
        self._connection_attempt_active = False
        self._stop_polling()
        self._exit_guard_timer.stop()
        self._cancel_handshake_timers()
        self._latest_status = None
        self.status_changed.emit(None)
        self._pending_commands.clear()
        was_transition = self._passthrough_transition_active
        self._passthrough_transition_active = False
        self._queued_passthrough_mode = None
        self._exit_pending = False
        self._passthrough_mode = "off"
        if was_transition:
            self.passthrough_transition_changed.emit(False)
        self.passthrough_mode_changed.emit("off")

    def _on_worker_error(self, msg: str) -> None:
        self.error_occurred.emit(msg)

    def _on_response(self, cmd: str, resp) -> None:
        pending = self._pending_commands.get(cmd)
        if pending:
            control, on_success, on_failure = pending.popleft()
            if not pending:
                self._pending_commands.pop(cmd, None)
            if resp.error is not None:
                reason = resp.error.code
                self.command_failed.emit(control, reason)
                if on_failure is not None:
                    on_failure(reason)
            else:
                if on_success is not None:
                    on_success()
                # 控制命令成功后补一次状态确认 (透传切换后不补发,
                # 否则该查询会作为透传 payload 发给下游设备); 静默避免刷屏
                if cmd != cmd_query_status() and self._passthrough_mode == "off":
                    try:
                        self._worker.send_command(cmd_query_status(), silent=True)
                    except SerialError as error:
                        self._on_worker_error(f"状态确认失败: {error}")

    def _on_at_data(self, cmd: str, resp) -> None:
        if resp.status is not None:
            self._latest_status = resp.status
            self.status_changed.emit(resp.status)

    # ---- 握手 ----
    def _do_handshake(self) -> None:
        if not self._is_open or not self._connection_attempt_active:
            return
        try:
            resp = self._worker.send_and_wait(
                cmd_query_status(),
                timeout_ms=self._handshake_attempt_timeout_ms,
            )
            if not self._connection_attempt_active:
                return
            if resp.status is not None:
                self._complete_handshake()
            else:
                reason = (
                    resp.error.code
                    if resp.error is not None
                    else "INVALID_STATUS"
                )
                self._schedule_handshake_retry(reason)
        except SerialTimeout:
            if self._connection_attempt_active:
                self._schedule_handshake_retry("TIMEOUT")
        except SerialError as e:
            if self._connection_attempt_active and self._is_open:
                reason = (
                    "TIMEOUT"
                    if self._worker.is_resynchronizing()
                    else str(e)
                )
                self._schedule_handshake_retry(reason)

    def _schedule_handshake_retry(self, reason: str) -> None:
        if not self._connection_attempt_active or not self._is_open:
            return
        self._last_handshake_error = reason
        self._handshake_retry_timer.start(self._handshake_retry_ms)

    def _complete_handshake(self) -> None:
        if self._handshake_ok:
            return
        self._connection_attempt_active = False
        self._handshake_ok = True
        self._cancel_handshake_timers()
        self._start_polling()
        self.handshake_completed.emit()

    def _fail_connection_attempt(self) -> None:
        if not self._connection_attempt_active:
            return
        reason = self._last_handshake_error
        self._connection_attempt_active = False
        self._cancel_handshake_timers()
        if self._worker.is_open():
            self._worker.close()
        self.handshake_failed.emit(reason)

    def _cancel_handshake_timers(self) -> None:
        self._handshake_delay_timer.stop()
        self._handshake_retry_timer.stop()
        self._handshake_deadline_timer.stop()

    # ---- UI 拉取最新状态 ----
    def get_latest(self) -> dict:
        return {"status": self._latest_status}
