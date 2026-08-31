"""数据模型 — 解析后的板2固件响应.

字段名贴近固件 docs/board2-at-uart-pwm.md 协议文档.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---- 错误响应 ----
@dataclass(frozen=True)
class AtError:
    """板2 错误响应, 例如 '+ERROR:PARSE'.

    注意: 板2 的错误行带 '+ERROR:' 前缀, 与常见 'ERROR:' 不同.
    这里同时兼容两种前缀, 方便手工测试.
    """

    code: str  # 去掉 '+ERROR:' 前缀, 例 'PARSE', '12V_DISABLED'

    @classmethod
    def parse(cls, line: str) -> "AtError | None":
        """从 '[+]ERROR[:xxx]' 一行构造, 不匹配返回 None."""
        line = line.strip()
        if line.startswith("+ERROR:"):
            return cls(code=line[len("+ERROR:") :])
        if line == "+ERROR":
            return cls(code="")
        if line.startswith("ERROR:"):
            return cls(code=line[len("ERROR:") :])
        if line == "ERROR":
            return cls(code="")
        return None

    def __str__(self) -> str:
        return f"+ERROR:{self.code}" if self.code else "+ERROR"


# ---- 状态查询 ----
@dataclass(frozen=True)
class StatusState:
    """`AT+STATUS=?` → `+STATUS:12V=OFF,18V=OFF,...` 响应."""

    power_12v: bool
    power_18v: bool
    nmos1: bool
    nmos2: bool
    nmos3: bool
    pwm: int          # 当前感知亮度 0..100
    pwm_target: int   # 目标亮度 0..100
    pwm_time_ms: int  # 渐变时间 0..10000
    breath: bool

    REQUIRED_KEYS = (
        "12V", "18V", "NMOS1", "NMOS2", "NMOS3",
        "PWM", "PWM_TARGET", "PWM_TIME", "BREATH",
    )

    @classmethod
    def parse(cls, line: str) -> "StatusState | None":
        line = line.strip()
        prefix = "+STATUS:"
        if not line.startswith(prefix):
            return None
        fields: dict[str, str] = {}
        for item in line[len(prefix):].split(","):
            if item.count("=") != 1:
                return None
            key, value = item.split("=", 1)
            key = key.strip()
            if key in fields:
                return None
            fields[key] = value.strip()
        if tuple(fields.keys()) != cls.REQUIRED_KEYS:
            return None
        for key in ("12V", "18V", "NMOS1", "NMOS2", "NMOS3", "BREATH"):
            if fields[key] not in {"ON", "OFF"}:
                return None
        try:
            pwm = int(fields["PWM"])
            pwm_target = int(fields["PWM_TARGET"])
            pwm_time = int(fields["PWM_TIME"])
        except ValueError:
            return None
        if not all(0 <= v <= 100 for v in (pwm, pwm_target)):
            return None
        if not 0 <= pwm_time <= 10000:
            return None
        return cls(
            power_12v=fields["12V"] == "ON",
            power_18v=fields["18V"] == "ON",
            nmos1=fields["NMOS1"] == "ON",
            nmos2=fields["NMOS2"] == "ON",
            nmos3=fields["NMOS3"] == "ON",
            pwm=pwm,
            pwm_target=pwm_target,
            pwm_time_ms=pwm_time,
            breath=fields["BREATH"] == "ON",
        )


# ---- 下行事件 ----
@dataclass(frozen=True)
class UartRxFrame:
    """`+UART2RX:<HEX>` / `+UART3RX:<HEX>` — 透传目标串口收到的字节."""

    uart_index: int
    payload: bytes

    @classmethod
    def parse(cls, line: str) -> "UartRxFrame | None":
        line = line.strip()
        for uart_index in (2, 3):
            prefix = f"+UART{uart_index}RX:"
            if not line.startswith(prefix):
                continue
            value = line[len(prefix):]
            if (
                not value
                or len(value) % 2
                or len(value) > 64
                or any(char not in "0123456789ABCDEF" for char in value)
            ):
                return None
            return cls(uart_index=uart_index, payload=bytes.fromhex(value))
        return None
