"""at_protocol / models 纯解析层测试 (无 Qt 依赖)."""
from __future__ import annotations

import pytest

from stem_hub_board2_host.at_protocol import (
    CRLF,
    LineSplitter,
    ParsedResponse,
    cmd_query_status,
    cmd_set_breath,
    cmd_set_nmos,
    cmd_set_power_12v,
    cmd_set_pwm,
    cmd_set_pwm_time,
    cmd_raw,
    cmd_trans,
)
from stem_hub_board2_host.models import AtError, StatusState, UartRxFrame


class TestCommandBuilders:
    def test_query_status(self):
        assert cmd_query_status() == "AT+STATUS=?\r\n"

    def test_power(self):
        assert cmd_set_power_12v(True) == "AT+12V=ON\r\n"
        assert cmd_set_power_12v(False) == "AT+12V=OFF\r\n"

    def test_nmos(self):
        assert cmd_set_nmos(1, True) == "AT+NMOS1=ON\r\n"
        assert cmd_set_nmos(3, False) == "AT+NMOS3=OFF\r\n"
        with pytest.raises(ValueError):
            cmd_set_nmos(4, True)

    def test_pwm(self):
        assert cmd_set_pwm(0) == "AT+PWM=0\r\n"
        assert cmd_set_pwm(100) == "AT+PWM=100\r\n"
        with pytest.raises(ValueError):
            cmd_set_pwm(101)

    def test_pwm_time(self):
        assert cmd_set_pwm_time(500) == "AT+PWM_TIME=500\r\n"
        with pytest.raises(ValueError):
            cmd_set_pwm_time(10001)

    def test_breath(self):
        assert cmd_set_breath(True) == "AT+BREATH_TEST=ON\r\n"

    def test_trans(self):
        assert cmd_trans("1") == "AT+TRANS=1\r\n"
        assert cmd_trans("1&2") == "AT+TRANS=1&2\r\n"
        with pytest.raises(ValueError):
            cmd_trans("3")

    def test_raw_appends_crlf(self):
        assert cmd_raw("AT+PWM=1") == "AT+PWM=1\r\n"
        assert cmd_raw("AT+PWM=1\r\n") == "AT+PWM=1\r\n"


class TestParsedResponse:
    def test_ok(self):
        resp = ParsedResponse.parse("OK")
        assert resp.ok
        assert resp.error is None

    def test_error_with_plus_prefix(self):
        resp = ParsedResponse.parse("+ERROR:12V_DISABLED")
        assert resp.error is not None
        assert resp.error.code == "12V_DISABLED"
        assert str(resp.error) == "+ERROR:12V_DISABLED"

    def test_error_without_plus_prefix(self):
        resp = ParsedResponse.parse("ERROR:PARSE")
        assert resp.error is not None
        assert resp.error.code == "PARSE"

    def test_status_line(self):
        resp = ParsedResponse.parse(
            "+STATUS:12V=ON,18V=OFF,NMOS1=OFF,NMOS2=OFF,NMOS3=ON,"
            "PWM=42,PWM_TARGET=100,PWM_TIME=500,BREATH=OFF"
        )
        assert resp.status is not None
        assert resp.status.power_12v
        assert not resp.status.power_18v
        assert resp.status.nmos3
        assert resp.status.pwm == 42
        assert resp.status.pwm_target == 100
        assert resp.status.pwm_time_ms == 500
        assert not resp.status.breath

    def test_uart_rx(self):
        resp = ParsedResponse.parse("+UART2RX:00FF10")
        assert resp.uart_rx is not None
        assert resp.uart_rx.uart_index == 2
        assert resp.uart_rx.payload == b"\x00\xff\x10"

    def test_passthrough_fallback(self):
        resp = ParsedResponse.parse("hello world")
        assert resp.is_passthrough


class TestStatusStateValidation:
    def test_rejects_wrong_keys(self):
        assert StatusState.parse("+STATUS:12V=ON") is None

    def test_rejects_bad_bool(self):
        line = "+STATUS:12V=MAYBE,18V=OFF,NMOS1=OFF,NMOS2=OFF,NMOS3=OFF," \
               "PWM=0,PWM_TARGET=0,PWM_TIME=500,BREATH=OFF"
        assert StatusState.parse(line) is None

    def test_rejects_bad_pwm(self):
        line = "+STATUS:12V=ON,18V=OFF,NMOS1=OFF,NMOS2=OFF,NMOS3=OFF," \
               "PWM=101,PWM_TARGET=0,PWM_TIME=500,BREATH=OFF"
        assert StatusState.parse(line) is None

    def test_rejects_bad_time(self):
        line = "+STATUS:12V=ON,18V=OFF,NMOS1=OFF,NMOS2=OFF,NMOS3=OFF," \
               "PWM=0,PWM_TARGET=0,PWM_TIME=99999,BREATH=OFF"
        assert StatusState.parse(line) is None


class TestUartRxFrame:
    def test_rejects_odd_length(self):
        assert UartRxFrame.parse("+UART3RX:0FF") is None

    def test_rejects_lowercase(self):
        assert UartRxFrame.parse("+UART3RX:0ff") is None

    def test_rejects_too_long(self):
        assert UartRxFrame.parse("+UART3RX:" + "00" * 33) is None


class TestLineSplitter:
    def test_splits_crlf(self):
        splitter = LineSplitter()
        lines = splitter.feed(f"OK{CRLF}+ERROR:PARSE{CRLF}".encode())
        assert lines == ["OK", "+ERROR:PARSE"]

    def test_buffers_partial(self):
        splitter = LineSplitter()
        assert splitter.feed(b"OK\r") == []
        assert splitter.feed(b"\nAT") == ["OK"]
        assert splitter.feed(b"+X\r\n") == ["AT+X"]

    def test_reset(self):
        splitter = LineSplitter()
        splitter.feed(b"partial")
        splitter.reset()
        assert splitter.feed(b"OK\r\n") == ["OK"]


class TestAtError:
    def test_plain_error(self):
        assert AtError.parse("ERROR").code == ""
        assert AtError.parse("NOT_AN_ERROR") is None
