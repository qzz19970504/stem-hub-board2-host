"""Controller + FakeFirmware 连接流程测试 (Qt 事件驱动).

覆盖:
- 握手 (AT+STATUS=? 回包)
- 周期状态轮询与 status_changed 信号
- 联锁: 18V 关 → PWM 拒绝 (18V_DISABLED); 12V 开 → NMOS 可用
- 透传进入/发送/退出 (+++ 保护)
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def spin_until(condition, timeout_ms: int = 3000) -> bool:
    """处理事件循环直到 condition 成立或超时."""
    waited = 0
    while not condition() and waited < timeout_ms:
        wait(20)
        waited += 20
    return bool(condition())


@pytest.fixture()
def rig(qapp):
    from stem_hub_board2_host.controller import Controller
    from stem_hub_board2_host.fake_firmware import FakeFirmware
    from stem_hub_board2_host.serial_worker import SerialWorker
    from stem_hub_board2_host.transport import FakeSerialTransport

    transport = FakeSerialTransport()
    worker = SerialWorker(transport=transport)
    firmware = FakeFirmware(worker)
    controller = Controller(
        worker,
        handshake_initial_delay_ms=10,
        handshake_retry_ms=20,
        handshake_attempt_timeout_ms=200,
        handshake_deadline_ms=3000,
        poll_interval_ms=100,
    )
    assert worker.open("FAKE0", 9600)
    yield controller, worker, firmware, transport
    worker.close()


class TestHandshake:
    def test_handshake_completes(self, rig):
        controller, *_ = rig
        assert spin_until(lambda: controller.is_handshake_ok)
        assert controller.worker.is_open()

    def test_status_polling_arrives(self, rig):
        controller, *_ = rig
        assert spin_until(lambda: controller.is_handshake_ok)
        assert spin_until(lambda: controller.latest_status is not None)
        status = controller.latest_status
        assert status is not None
        assert not status.power_12v
        assert status.pwm == 0

    def test_status_changed_signal(self, rig):
        controller, *_ = rig
        received = []
        controller.status_changed.connect(lambda s: received.append(s))
        assert spin_until(lambda: controller.is_handshake_ok)
        assert spin_until(lambda: received)


class TestInterlocks:
    def test_pwm_blocked_when_18v_off(self, rig):
        controller, worker, _fw, _transport = rig
        assert spin_until(lambda: controller.is_handshake_ok)
        failures = []
        controller.command_failed.connect(lambda c, r: failures.append((c, r)))
        controller.set_pwm(50)
        assert spin_until(lambda: failures, timeout_ms=1500)
        assert failures[0] == ("PWM", "18V_DISABLED")

    def test_nmos_blocked_then_allowed(self, rig):
        controller, worker, _fw, _transport = rig
        assert spin_until(lambda: controller.is_handshake_ok)
        failures = []
        controller.command_failed.connect(lambda c, r: failures.append((c, r)))
        controller.set_nmos(1, True)
        assert spin_until(lambda: any(c == "NMOS1" for c, _ in failures), timeout_ms=1500)
        assert any(r == "12V_DISABLED" for _, r in failures)

        controller.set_power_12v(True)
        assert spin_until(
            lambda: controller.latest_status is not None
            and controller.latest_status.power_12v
        )
        # 12V 开启后重新发起 NMOS1 请求
        controller.set_nmos(1, True)
        assert spin_until(
            lambda: controller.latest_status is not None
            and controller.latest_status.nmos1
        )


class TestTransparent:
    def test_enter_send_exit(self, rig):
        controller, worker, _fw, _transport = rig
        assert spin_until(lambda: controller.is_handshake_ok)

        modes = []
        controller.passthrough_mode_changed.connect(modes.append)
        controller.enter_transparent("1")
        assert spin_until(lambda: controller.passthrough_mode == "1")

        # 透传发送 → 假固件回 +UART2RX 事件
        rx_payloads = []
        controller.worker.uart_rx_received.connect(
            lambda idx, data: rx_payloads.append((idx, data))
        )
        assert controller.send_transparent_bytes(b"\x01\x02hello")
        assert spin_until(lambda: rx_payloads, timeout_ms=2000)
        assert rx_payloads[0] == (2, b"\x01\x02hello")

        # 退出透传 (+++)
        controller.exit_transparent()
        assert spin_until(lambda: controller.passthrough_mode == "off", timeout_ms=4000)
        assert modes[-1] == "off"

    def test_at_uarttx_disabled_in_at_mode(self, rig):
        controller, worker, _fw, _transport = rig
        assert spin_until(lambda: controller.is_handshake_ok)
        errors = []
        controller.worker.response_received.connect(
            lambda cmd, resp: errors.append(resp) if resp.error is not None else None
        )
        controller.send_raw("AT+UARTTX=00FF\r\n")
        assert spin_until(lambda: errors, timeout_ms=1500)
        assert errors[0].error.code == "UART_DISABLED"
