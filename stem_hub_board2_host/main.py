"""程序入口.

运行:
    python -m stem_hub_board2_host.main            # 真串口
    python -m stem_hub_board2_host.main --fake     # 假固件, 无硬件时调试
"""
from __future__ import annotations

import argparse
import sys

from stem_hub_board2_host.app import get_app
from stem_hub_board2_host.controller import Controller
from stem_hub_board2_host.serial_worker import SerialWorker
from stem_hub_board2_host.transport import RealSerialTransport
from stem_hub_board2_host.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stem-hub-board2-host")
    parser.add_argument("--fake", action="store_true", help="用假固件 (无硬件时调试)")
    args = parser.parse_args(argv)

    app = get_app()

    # 构建 worker + controller
    if args.fake:
        from stem_hub_board2_host.fake_firmware import FakeFirmware
        from stem_hub_board2_host.transport import FakeSerialTransport

        # worker 与 firmware 共享 transport
        transport = FakeSerialTransport()
        worker = SerialWorker(transport=transport)
        _fw = FakeFirmware(worker)  # noqa: F841 — 需要保持引用, 否则 timer 会被 GC
        controller = Controller(worker)
        # 自动打开假串口
        worker.open("FAKE0", 9600)
    else:
        worker = SerialWorker(transport=RealSerialTransport())
        controller = Controller(worker)

    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
