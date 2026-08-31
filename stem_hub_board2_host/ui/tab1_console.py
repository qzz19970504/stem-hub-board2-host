"""Tab 1: 控制台 — 电源 / NMOS / PWM / 状态 / AT 终端."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets.at_console import AtConsole
from .widgets.nmos_card import NmosCard
from .widgets.power_card import PowerCard
from .widgets.pwm_card import PwmCard
from .widgets.status_card import StatusCard


class ConsoleTab(QWidget):
    """Tab 1 — 控制台."""

    power12_changed = Signal(bool)
    power18_changed = Signal(bool)
    nmos_changed = Signal(int, bool)
    pwm_changed = Signal(int)
    pwm_time_changed = Signal(int)
    breath_changed = Signal(bool)
    at_send = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
        )
        outer.setSpacing(theme.GRID_GAP)

        self.grid = QGridLayout()
        self.grid.setSpacing(theme.GRID_GAP)
        outer.addLayout(self.grid, 1)

        self.power_card = PowerCard()
        self.nmos_card = NmosCard()
        self.pwm_card = PwmCard()
        self.status_card = StatusCard()
        self.at_console = AtConsole()

        # QGridLayout includes each widget's sizeHint before applying stretch.
        # Ignore horizontal hints so the column stretch ratios stay exact.
        for widget in (
            self.power_card,
            self.nmos_card,
            self.pwm_card,
            self.status_card,
            self.at_console,
        ):
            widget.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
            )

        # 第一行 3 卡
        self.grid.addWidget(self.power_card, 0, 0)
        self.grid.addWidget(self.nmos_card, 0, 1)
        self.grid.addWidget(self.pwm_card, 0, 2)
        # 第二行: 状态 + AT 终端
        self.grid.addWidget(self.status_card, 1, 0)
        self.grid.addWidget(self.at_console, 1, 1, 1, 2)

        self.grid.setColumnStretch(0, theme.COLUMN_STRETCH_LEFT)
        self.grid.setColumnStretch(1, theme.COLUMN_STRETCH_CENTER)
        self.grid.setColumnStretch(2, theme.COLUMN_STRETCH_RIGHT)
        self.grid.setRowStretch(0, theme.ROW_STRETCH_TOP)
        self.grid.setRowStretch(1, theme.ROW_STRETCH_BOTTOM)

        # 底部状态引导条 (主窗口按连接/透传状态更新文案与颜色)
        self.conn_hint = QLabel(
            "未连接：选择串口并点击 CONNECT (固定 9600 8N1)"
        )
        self.conn_hint.setObjectName("secondary")
        self.conn_hint.setFixedHeight(22)
        outer.addWidget(self.conn_hint)

        # 信号
        self.power_card.power12_changed.connect(self.power12_changed)
        self.power_card.power18_changed.connect(self.power18_changed)
        self.nmos_card.nmos_changed.connect(self.nmos_changed)
        self.pwm_card.pwm_changed.connect(self.pwm_changed)
        self.pwm_card.pwm_time_changed.connect(self.pwm_time_changed)
        self.pwm_card.breath_changed.connect(self.breath_changed)
        self.at_console.send_requested.connect(self.at_send)
