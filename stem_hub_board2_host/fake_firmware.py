"""假固件 — 模拟 stem-hub-board2 固件行为, 用于无硬件联调.

用 FakeSerialTransport + SerialWorker 跑:
1. SerialWorker 用 FakeSerialTransport
2. 假固件轮询 transport 已写字节: AT 模式按行解析; 透传模式按原字节转发
3. 响应通过 transport.feed() 喂回 worker

模拟行为与固件 docs/board2-at-uart-pwm.md 对齐:
- 联锁: 12V 关 → NMOS 拒绝 (12V_DISABLED); 18V 关 → PWM>0 拒绝 (18V_DISABLED)
- 关 12V 自动关三路 NMOS; 关 18V 自动清 PWM 并停呼吸灯
- PWM 以 10ms 步进从当前值渐变到目标值
- AT+TRANS=x → OK 后进入透明模式; 收到 '+++' 退出并回 OK
- 透传 payload 会模拟下游设备回包 (+UARTxRX 事件)
- AT+UARTTX= 在 AT 模式下固定返回 +ERROR:UART_DISABLED
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from .at_protocol import CRLF, EXIT_TRANSPARENT_BYTES, LineSplitter
from .serial_worker import SerialWorker
from .transport import FakeSerialTransport


class FakeFirmware(QObject):
    """模拟板2固件行为."""

    def __init__(self, worker: SerialWorker, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._splitter = LineSplitter()

        # 固件状态
        self._p12v = False
        self._p18v = False
        self._nmos = {1: False, 2: False, 3: False}
        self._pwm = 0
        self._pwm_target = 0
        self._pwm_time = 500
        self._breath = False
        self._breath_phase = 0.0
        self._trans_mode: str | None = None  # None / '1' / '2' / '1&2'

        # 轮询 host 写出的字节
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(5)

        # PWM 渐变 (固件每 10ms 推进一次)
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)
        self._fade_timer.start(10)

        # 呼吸灯演示
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._breath_step)
        self._breath_timer.start(20)

    # ---- transport 访问 ----
    def _transport(self) -> FakeSerialTransport | None:
        transport = self._worker._transport  # type: ignore[attr-defined]
        return transport if isinstance(transport, FakeSerialTransport) else None

    def _poll(self) -> None:
        transport = self._transport()
        if transport is None:
            return
        written = transport.take_written()
        if not written:
            return
        if self._trans_mode is not None:
            self._handle_transparent_bytes(written)
            return
        for line in self._splitter.feed(written):
            self._handle_cmd(line)

    def _reply(self, text: str) -> None:
        transport = self._transport()
        if transport is not None:
            transport.feed(text.encode("utf-8"))

    # ---- AT 命令处理 ----
    def _handle_cmd(self, cmd: str) -> None:
        cmd = cmd.strip()

        if cmd == "AT+STATUS=?":
            self._reply(self._status_line() + CRLF + "OK" + CRLF)
        elif cmd == "AT+12V=ON":
            self._p12v = True
            self._reply("OK" + CRLF)
        elif cmd == "AT+12V=OFF":
            self._p12v = False
            self._nmos = {1: False, 2: False, 3: False}
            self._reply("OK" + CRLF)
        elif cmd == "AT+18V=ON":
            self._p18v = True
            self._reply("OK" + CRLF)
        elif cmd == "AT+18V=OFF":
            self._p18v = False
            self._pwm_target = 0
            self._pwm = 0
            self._breath = False
            self._reply("OK" + CRLF)
        elif cmd.startswith("AT+NMOS"):
            self._handle_nmos(cmd)
        elif cmd.startswith("AT+PWM="):
            self._handle_pwm(cmd)
        elif cmd.startswith("AT+PWM_TIME="):
            self._handle_pwm_time(cmd)
        elif cmd == "AT+BREATH_TEST=ON":
            if not self._p18v:
                self._reply("+ERROR:18V_DISABLED" + CRLF)
            else:
                self._breath = True
                self._reply("OK" + CRLF)
        elif cmd == "AT+BREATH_TEST=OFF":
            self._breath = False
            self._reply("OK" + CRLF)
        elif cmd.startswith("AT+TRANS="):
            target = cmd[len("AT+TRANS="):]
            if target in ("1", "2", "1&2"):
                self._trans_mode = target
                self._reply("OK" + CRLF)
            else:
                self._reply("+ERROR:PARSE" + CRLF)
        elif cmd.startswith("AT+UARTTX="):
            value = cmd[len("AT+UARTTX="):]
            if (
                not value
                or len(value) % 2
                or len(value) > 64
                or any(c not in "0123456789ABCDEF" for c in value)
            ):
                self._reply("+ERROR:RANGE" + CRLF)
            else:
                self._reply("+ERROR:UART_DISABLED" + CRLF)
        else:
            self._reply("+ERROR:PARSE" + CRLF)

    def _handle_nmos(self, cmd: str) -> None:
        for idx in (1, 2, 3):
            if cmd == f"AT+NMOS{idx}=ON":
                if not self._p12v:
                    self._reply("+ERROR:12V_DISABLED" + CRLF)
                    return
                self._nmos[idx] = True
                self._reply("OK" + CRLF)
                return
            if cmd == f"AT+NMOS{idx}=OFF":
                self._nmos[idx] = False
                self._reply("OK" + CRLF)
                return
        self._reply("+ERROR:PARSE" + CRLF)

    def _handle_pwm(self, cmd: str) -> None:
        value_text = cmd[len("AT+PWM="):]
        try:
            value = int(value_text)
        except ValueError:
            self._reply("+ERROR:PARSE" + CRLF)
            return
        if not 0 <= value <= 100:
            self._reply("+ERROR:RANGE" + CRLF)
            return
        if self._breath:
            self._reply("+ERROR:BREATH_ACTIVE" + CRLF)
            return
        if value != 0 and not self._p18v:
            self._reply("+ERROR:18V_DISABLED" + CRLF)
            return
        self._pwm_target = value
        self._reply("OK" + CRLF)

    def _handle_pwm_time(self, cmd: str) -> None:
        value_text = cmd[len("AT+PWM_TIME="):]
        try:
            value = int(value_text)
        except ValueError:
            self._reply("+ERROR:PARSE" + CRLF)
            return
        if not 0 <= value <= 10000:
            self._reply("+ERROR:RANGE" + CRLF)
            return
        self._pwm_time = value
        self._reply("OK" + CRLF)

    def _status_line(self) -> str:
        return (
            f"+STATUS:12V={'ON' if self._p12v else 'OFF'},"
            f"18V={'ON' if self._p18v else 'OFF'},"
            f"NMOS1={'ON' if self._nmos[1] else 'OFF'},"
            f"NMOS2={'ON' if self._nmos[2] else 'OFF'},"
            f"NMOS3={'ON' if self._nmos[3] else 'OFF'},"
            f"PWM={round(self._pwm)},"
            f"PWM_TARGET={self._pwm_target},"
            f"PWM_TIME={self._pwm_time},"
            f"BREATH={'ON' if self._breath else 'OFF'}"
        )

    # ---- 透传 ----
    def _handle_transparent_bytes(self, data: bytes) -> None:
        if data == EXIT_TRANSPARENT_BYTES:
            self._trans_mode = None
            self._reply("OK" + CRLF)
            return
        # 模拟下游设备: 稍后以 +UARTxRX 事件回显 payload
        targets: list[int] = []
        if self._trans_mode in ("1", "1&2"):
            targets.append(2)
        if self._trans_mode in ("2", "1&2"):
            targets.append(3)
        if not targets:
            return
        hex_text = data.hex().upper()
        reply = "".join(
            f"+UART{idx}RX:{hex_text}{CRLF}" for idx in targets
        )
        QTimer.singleShot(60, lambda: self._reply(reply))

    # ---- PWM 渐变 / 呼吸灯 ----
    def _fade_step(self) -> None:
        if self._breath:
            return
        if self._pwm == self._pwm_target:
            return
        step = max(1.0, self._pwm_time / 200.0)
        if self._pwm < self._pwm_target:
            self._pwm = min(float(self._pwm_target), self._pwm + step)
        else:
            self._pwm = max(float(self._pwm_target), self._pwm - step)

    def _breath_step(self) -> None:
        if not self._breath:
            return
        import math

        self._breath_phase += 0.02
        self._pwm = 50.0 + 50.0 * math.sin(self._breath_phase)
