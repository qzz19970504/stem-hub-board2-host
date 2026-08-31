"""串口工作线程.

设计:
- 持有一个 Transport (RealSerialTransport 或 FakeSerialTransport)
- 用 LineSplitter 切出完整行
- 每行 parse 成 ParsedResponse
- 按发送顺序 FIFO 处理响应: +STATUS:... → data 行; OK / +ERROR → 完成 future
- +UARTxRX 事件 → 发 uart_rx_received signal, 不进 future 队列

高层 API:
- open(port_name, baudrate=9600) -> bool
- close()
- send_and_wait(cmd, timeout_ms) -> ParsedResponse  (throws on error / timeout)
- send_command(cmd, timeout_ms)  (异步排队, 响应经 response_received 信号回报)
- await_completion(label, timeout_ms) -> ParsedResponse
  (不发送任何字节, 只等待下一个 OK/ERROR 行 — 用于透传 `+++` 退出)
- send_bytes(data)  (原样写字节, 透传 payload / +++ 用)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal

from .at_protocol import LineSplitter, ParsedResponse
from .models import AtError
from .transport import RealSerialTransport, Transport


RESYNCHRONIZATION_QUIET_MS = 200


class SerialError(Exception):
    """串口/协议层错误."""


class SerialTimeout(SerialError):
    """等待响应超时."""


@dataclass
class _Pending:
    command: str
    timeout_ms: int = 0
    skip_send: bool = False
    silent: bool = False
    on_data: Optional[ParsedResponse] = None
    completion_callback: Optional[Callable[[ParsedResponse], None]] = None
    timeout_callback: Optional[Callable[[], None]] = None
    finished: bool = False
    has_been_sent: bool = False
    timeout_timer: Optional[QTimer] = None


class SerialWorker(QObject):
    """串口 worker, 必须在 QApplication 主事件循环里使用."""

    connected = Signal(str, int)  # (port_name, baudrate)
    disconnected = Signal()
    error_occurred = Signal(str)

    response_received = Signal(str, ParsedResponse)  # (command, response)
    uart_rx_received = Signal(int, bytes)
    at_data_received = Signal(str, ParsedResponse)  # (command, data response)
    # 静默查询 (轮询/状态确认) 的数据行: 驱动状态更新, 但不用于日志展示
    poll_data_received = Signal(str, ParsedResponse)

    def __init__(
        self,
        transport: Transport | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._transport: Transport = transport or RealSerialTransport(self)
        self._splitter = LineSplitter()
        self._pending: Deque[_Pending] = deque()
        self._is_open = False
        self._port_name = ""
        self._baudrate = 0
        self._is_resynchronizing = False
        self._resynchronization_timer = QTimer(self)
        self._resynchronization_timer.setObjectName(
            "serialResynchronizationTimer"
        )
        self._resynchronization_timer.setSingleShot(True)
        self._resynchronization_timer.timeout.connect(
            self._finish_resynchronization
        )

        # 连接信号
        self._transport.ready_read.connect(self._on_ready_read)
        self._transport.error_occurred.connect(self._on_port_error)

    # ---- 公开 API ----
    @staticmethod
    def list_ports():
        from .transport import list_serial_ports
        return list_serial_ports()

    def is_open(self) -> bool:
        return self._is_open

    def is_resynchronizing(self) -> bool:
        return self._is_resynchronizing

    def open(self, port_name: str, baudrate: int = 9600) -> bool:
        if self._is_open:
            self.close()
        if not self._transport.open(port_name, baudrate):
            self.error_occurred.emit(
                f"打开串口失败: {self._transport.error_string()}"
            )
            return False
        self._is_open = True
        self._port_name = port_name
        self._baudrate = baudrate
        self._splitter.reset()
        self._pending.clear()
        self._resynchronization_timer.stop()
        self._is_resynchronizing = False
        self.connected.emit(port_name, baudrate)
        return True

    def close(self) -> None:
        if self._is_open:
            for pending in self._pending:
                self._dispose_timeout_timer(pending)
            self._transport.close()
            self._is_open = False
            self._pending.clear()
            self._resynchronization_timer.stop()
            self._is_resynchronizing = False
            self._splitter.reset()
            self.disconnected.emit()

    def send_only(self, cmd: str) -> None:
        self.send_bytes(cmd.encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        """Write an exact byte sequence without text transcoding."""
        if not self._is_open:
            raise SerialError("串口未打开")
        n = self._transport.write(data)
        if n != len(data):
            raise SerialError(f"串口写入不完整: 写了 {n}/{len(data)}")

    def send_command(
        self,
        cmd: str,
        timeout_ms: int = 1000,
        *,
        silent: bool = False,
    ) -> None:
        """Queue an AT command so its eventual OK/ERROR keeps attribution.

        silent=True 用于周期轮询等后台查询: 响应仍会驱动状态更新,
        但不广播 response_received / at_data_received, 避免日志刷屏.
        """
        self._ensure_command_can_be_sent()
        pending = _Pending(command=cmd, timeout_ms=timeout_ms, silent=silent)
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            raise

    def await_completion(self, label: str, timeout_ms: int = 1000) -> ParsedResponse:
        """等待下一个 OK/ERROR 行, 不发送任何字节 (透传 `+++` 退出用)."""
        self._ensure_command_can_be_sent()

        loop = QEventLoop()
        captured: dict[str, ParsedResponse] = {}
        did_timeout = False

        def _on_completed(response: ParsedResponse) -> None:
            captured["response"] = response
            loop.quit()

        def _on_timeout() -> None:
            nonlocal did_timeout
            did_timeout = True
            loop.quit()

        pending = _Pending(
            command=label,
            timeout_ms=timeout_ms,
            skip_send=True,
            completion_callback=_on_completed,
            timeout_callback=_on_timeout,
        )
        self._pending.append(pending)
        self._start_timeout_timer(pending)

        if "response" not in captured and not did_timeout:
            loop.exec()

        if "response" in captured:
            return captured["response"]
        raise SerialTimeout(f"等待响应超时 ({timeout_ms}ms): {label!r}")

    def send_and_wait(self, cmd: str, timeout_ms: int = 1000) -> ParsedResponse:
        """发命令并等待回包.

        返回的 ParsedResponse 优先包含 data 行 (+STATUS:...) 的字段;
        如果只有 OK 行, 则只设 ok=True. 如果是 ERROR, error 不为 None.
        """
        self._ensure_command_can_be_sent()

        loop = QEventLoop()
        captured: dict[str, ParsedResponse] = {}
        did_timeout = False

        def _on_completed(response: ParsedResponse) -> None:
            captured["response"] = response
            loop.quit()

        def _on_timeout() -> None:
            nonlocal did_timeout
            did_timeout = True
            loop.quit()

        pending = _Pending(
            command=cmd,
            timeout_ms=timeout_ms,
            completion_callback=_on_completed,
            timeout_callback=_on_timeout,
        )
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            raise

        if "response" not in captured and not did_timeout:
            loop.exec()

        if "response" in captured:
            return captured["response"]
        raise SerialTimeout(f"等待响应超时 ({timeout_ms}ms): {cmd!r}")

    # ---- 内部 ----
    def _on_ready_read(self) -> None:
        data = self._transport.read_all()
        if not data:
            return
        if self._is_resynchronizing:
            self._splitter.reset()
            self._resynchronization_timer.start(
                RESYNCHRONIZATION_QUIET_MS
            )
            return
        for raw_line in self._splitter.feed_raw(data):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                self._report_protocol_warning(raw_line)
                continue
            self._handle_line(line, raw_line)

    def _on_port_error(self) -> None:
        # transport 端已经过滤 NoError, 这里只管发错误消息
        self.error_occurred.emit(f"串口错误: {self._transport.error_string()}")

    def _handle_line(self, line: str, raw_line: bytes | None = None) -> None:
        resp = ParsedResponse.parse(line)

        if resp.uart_rx is not None:
            self.uart_rx_received.emit(
                resp.uart_rx.uart_index,
                resp.uart_rx.payload,
            )
            return

        if resp.is_passthrough:
            unrecognized = (
                raw_line if raw_line is not None else line.encode("utf-8")
            )
            self._report_protocol_warning(unrecognized)
            return

        cur = None
        for p in self._pending:
            if not p.finished:
                cur = p
                break
        if cur is None:
            self.at_data_received.emit("", resp)
            return

        if resp.ok or resp.error is not None:
            self._dispose_timeout_timer(cur)
            if cur.on_data is not None and resp.ok:
                data = cur.on_data
                resp.status = data.status or resp.status
            cur.finished = True
            while self._pending and self._pending[0].finished:
                self._pending.popleft()
            if cur.completion_callback is not None:
                cur.completion_callback(resp)
            if not cur.silent:
                self.response_received.emit(cur.command, resp)
            try:
                self._start_next_pending()
            except SerialError as error:
                self.error_occurred.emit(f"串口发送队列失败: {error}")
                self.close()
        elif resp.status is not None:
            cur.on_data = resp
            if cur.silent:
                self.poll_data_received.emit(cur.command, resp)
            else:
                self.at_data_received.emit(cur.command, resp)

    def _ensure_command_can_be_sent(self) -> None:
        if not self._is_open:
            raise SerialError("串口未打开")
        if self._is_resynchronizing:
            raise SerialError("串口协议正在重新同步")

    def _start_next_pending(self) -> None:
        if not self._pending:
            return
        pending = self._pending[0]
        if pending.finished or pending.has_been_sent:
            return

        if not pending.skip_send:
            self.send_only(pending.command)
        pending.has_been_sent = True
        self._start_timeout_timer(pending)

    def _start_timeout_timer(self, pending: _Pending) -> None:
        if pending.timeout_ms <= 0 or pending.timeout_timer is not None:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_async_timeout(pending))
        pending.timeout_timer = timer
        timer.start(pending.timeout_ms)

    def _on_async_timeout(self, pending: _Pending) -> None:
        if pending.finished or pending not in self._pending:
            return
        self._begin_resynchronization(pending.command)

    @staticmethod
    def _dispose_timeout_timer(pending: _Pending) -> None:
        timer = pending.timeout_timer
        if timer is None:
            return
        pending.timeout_timer = None
        timer.stop()
        timer.timeout.disconnect()
        timer.setParent(None)
        timer.deleteLater()

    def _begin_resynchronization(self, timed_out_command: str) -> None:
        if not self._is_open:
            return

        abandoned = list(self._pending)
        self._pending.clear()
        self._is_resynchronizing = True
        self._splitter.reset()
        self._transport.read_all()
        self._resynchronization_timer.start(RESYNCHRONIZATION_QUIET_MS)

        for pending in abandoned:
            self._dispose_timeout_timer(pending)
            pending.finished = True
            if pending.timeout_callback is not None:
                pending.timeout_callback()

        self.error_occurred.emit(
            "命令响应超时，串口保持连接并等待重新同步: "
            f"{timed_out_command!r}"
        )
        for pending in abandoned:
            response = ParsedResponse(
                raw_line="",
                error=AtError(code="TIMEOUT"),
            )
            self.response_received.emit(pending.command, response)

    def _finish_resynchronization(self) -> None:
        self._splitter.reset()
        self._is_resynchronizing = False

    def _report_protocol_warning(self, raw_line: bytes) -> None:
        hexadecimal = raw_line.hex(" ").upper() or "<EMPTY>"
        self.error_occurred.emit(
            f"收到无法识别的串口数据，已丢弃: {hexadecimal}"
        )
