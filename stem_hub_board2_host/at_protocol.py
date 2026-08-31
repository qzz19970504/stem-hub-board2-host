"""AT 命令协议 — 构造命令 + 解析响应.

板2 包模型:
- 控制命令 (e.g. AT+NMOS1=ON): 响应 = 'OK' 或 '+ERROR:code'
- 查询命令 (AT+STATUS=?): 响应 = '+STATUS:...' + 'OK' (两行)
- 事件: '+UART2RX:<HEX>' / '+UART3RX:<HEX>' (透传期间由 bridgeTask 上报)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import AtError, StatusState, UartRxFrame


# AT 命令结尾必须 CRLF
CRLF = "\r\n"

# 退出透传的守护序列 (前后各需 >=1ms 静默, 由发送时机保证)
EXIT_TRANSPARENT_BYTES = b"+++"


# ---- 命令构造 ----
def cmd_query_status() -> str:
    return f"AT+STATUS=?{CRLF}"


def cmd_set_power_12v(on: bool) -> str:
    return f"AT+12V={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_power_18v(on: bool) -> str:
    return f"AT+18V={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_nmos(idx: int, on: bool) -> str:
    """idx: 1..3."""
    if idx not in (1, 2, 3):
        raise ValueError(f"nmos idx must be 1..3, got {idx}")
    return f"AT+NMOS{idx}={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_pwm(percent: int) -> str:
    """percent: 0..100."""
    if not 0 <= percent <= 100:
        raise ValueError(f"pwm percent must be 0..100, got {percent}")
    return f"AT+PWM={percent}{CRLF}"


def cmd_set_pwm_time(ms: int) -> str:
    """ms: 0..10000, 掉电保存."""
    if not 0 <= ms <= 10000:
        raise ValueError(f"pwm time must be 0..10000, got {ms}")
    return f"AT+PWM_TIME={ms}{CRLF}"


def cmd_set_breath(on: bool) -> str:
    return f"AT+BREATH_TEST={'ON' if on else 'OFF'}{CRLF}"


def cmd_trans(target: str) -> str:
    """target: '1' / '2' / '1&2'."""
    if target not in ("1", "2", "1&2"):
        raise ValueError(f"trans target must be 1/2/1&2, got {target}")
    return f"AT+TRANS={target}{CRLF}"


def cmd_raw(text: str) -> str:
    """用户从 AT 输入框发送的任意命令, 自动补 CRLF 结尾.

    不会 trim 内部空格, 因为固件 AT 解析器不允许中间空格, 留原样让用户/固件自己报错.
    """
    if CRLF in text:
        return text if text.endswith(CRLF) else text + CRLF
    return text + CRLF


# ---- 响应解析 ----
@dataclass
class ParsedResponse:
    """单条响应. 可能是 OK / ERROR / 数据行 / 透传行."""

    raw_line: str  # 去掉 CRLF 之后的原文

    # 下面几个里最多一个有值
    ok: bool = False
    error: Optional[AtError] = None
    status: Optional[StatusState] = None
    uart_rx: Optional[UartRxFrame] = None
    is_passthrough: bool = False  # 透传行 (非 AT 数据)

    @classmethod
    def parse(cls, line: str) -> "ParsedResponse":
        """从一行响应 (无 CRLF) 构造."""
        s = line.strip()
        if s == "OK":
            return cls(raw_line=line, ok=True)
        err = AtError.parse(s)
        if err is not None:
            return cls(raw_line=line, error=err)
        if s.startswith("+STATUS:"):
            d = StatusState.parse(s)
            if d is not None:
                return cls(raw_line=line, status=d)
        if s.startswith(("+UART2RX:", "+UART3RX:")):
            frame = UartRxFrame.parse(s)
            if frame is not None:
                return cls(raw_line=line, uart_rx=frame)
        # 既不是 OK / ERROR 也不是 +XXX:  → 透传数据
        return cls(raw_line=line, is_passthrough=True)


# ---- 行切分器 ----
class LineSplitter:
    """从字节流中切出完整行 (以 CRLF 结尾).

    透传数据本身不回传到 UART1 (只有 +UARTxRX 事件带 CRLF),
    所以这里始终按 CRLF 切行是安全的.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[str]:
        """把新数据塞进来, 返回所有切出的完整行 (不包含 CRLF)."""
        lines: list[str] = []
        for line_bytes in self.feed_raw(data):
            try:
                line = line_bytes.decode("utf-8")
            except UnicodeDecodeError:
                line = line_bytes.decode("latin-1")
            lines.append(line)
        return lines

    def feed_raw(self, data: bytes) -> list[bytes]:
        """Return complete CRLF-delimited lines without decoding their bytes."""
        if not data:
            return []
        self._buf.extend(data)
        lines: list[bytes] = []
        while True:
            i = self._buf.find(b"\r\n")
            if i < 0:
                break
            line_bytes = bytes(self._buf[:i])
            del self._buf[: i + 2]
            lines.append(line_bytes)
        return lines

    def reset(self) -> None:
        self._buf.clear()
