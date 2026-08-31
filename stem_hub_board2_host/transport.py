"""串口传输抽象.

SerialWorker 不直接持有 QSerialPort, 而是通过 Transport 接口.
- RealSerialTransport: 真串口
- FakeSerialTransport: 内存模拟, 用于测试 / 假固件
"""
from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject, Signal
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo


class Transport(Protocol):
    """串口传输抽象接口. SerialWorker 用这个接口操作底层."""

    # 信号
    ready_read: Signal
    error_occurred: Signal

    def open(self, port_name: str, baudrate: int) -> bool: ...
    def close(self) -> None: ...
    def is_open(self) -> bool: ...
    def write(self, data: bytes) -> int: ...
    def read_all(self) -> bytes: ...
    def error_string(self) -> str: ...


class RealSerialTransport(QObject):
    """包装 QSerialPort."""

    ready_read = Signal()
    # 关键: 不能用 Signal(QSerialPort.SerialPortError) — PySide6 跨 QObject 边界
    # 连接 enum-typed signal 会 RuntimeError. 用无参 signal + 内部转发.
    error_occurred = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._port = QSerialPort(self)
        self._port.readyRead.connect(self.ready_read)
        self._port.errorOccurred.connect(self._on_port_error)

    def _on_port_error(self, err) -> None:
        # 忽略 NoError, 它只是初始化时的占位
        from PySide6.QtSerialPort import QSerialPort
        if err == QSerialPort.SerialPortError.NoError:
            return
        self.error_occurred.emit()

    def open(self, port_name: str, baudrate: int) -> bool:
        self._port.setPortName(port_name)
        self._port.setBaudRate(baudrate)
        self._port.setDataBits(QSerialPort.DataBits.Data8)
        self._port.setParity(QSerialPort.Parity.NoParity)
        self._port.setStopBits(QSerialPort.StopBits.OneStop)
        self._port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        return self._port.open(QSerialPort.OpenModeFlag.ReadWrite)

    def close(self) -> None:
        self._port.close()

    def is_open(self) -> bool:
        return self._port.isOpen()

    def write(self, data: bytes) -> int:
        return self._port.write(data)

    def read_all(self) -> bytes:
        return bytes(self._port.readAll())

    def error_string(self) -> str:
        return self._port.errorString()


class FakeSerialTransport(QObject):
    """内存模拟 transport.

    写入的字节在内部 buffer, 不会自己 emit ready_read —
    需要外部驱动 (e.g. 假固件 reply() 方法调用 _emit()).
    """

    ready_read = Signal()
    error_occurred = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._is_open = False
        self._name = "FAKE"
        self._written = bytearray()
        self._rx_buf = bytearray()

    def open(self, port_name: str, baudrate: int) -> bool:
        self._is_open = True
        self._name = port_name
        return True

    def close(self) -> None:
        self._is_open = False

    def is_open(self) -> bool:
        return self._is_open

    def write(self, data: bytes) -> int:
        # 存起来, 测试 / 假固件用
        self._written.extend(data)
        return len(data)

    def read_all(self) -> bytes:
        buf = self._rx_buf
        self._rx_buf = bytearray()
        return bytes(buf)

    def error_string(self) -> str:
        return ""

    def feed(self, data: bytes) -> None:
        """测试 / 假固件: 喂入数据模拟串口收到字节."""
        self._rx_buf.extend(data)
        self.ready_read.emit()

    def drain_rx(self) -> bytes:
        """测试用: 取走所有待处理 RX 字节."""
        buf = bytes(self._rx_buf)
        self._rx_buf = bytearray()
        return buf

    def take_written(self) -> bytes:
        """测试 / 假固件: 取走所有已写出的字节."""
        buf = bytes(self._written)
        self._written = bytearray()
        return buf

    def get_written(self) -> bytes:
        return bytes(self._written)


def list_serial_ports() -> list[QSerialPortInfo]:
    return QSerialPortInfo.availablePorts()
