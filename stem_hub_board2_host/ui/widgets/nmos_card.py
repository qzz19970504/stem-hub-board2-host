"""NMOS 输出卡片 — 三路高有效开关, 受 12V 联锁."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from .. import theme
from .toggle_switch import ToggleSwitch


class NmosCard(QFrame):
    """NMOS1/2/3 三路开关."""

    nmos_changed = Signal(int, bool)  # (idx 1..3, on)

    ROWS = ("NMOS1 · PB4", "NMOS2 · PB15", "NMOS3 · PB6")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._switches: dict[int, ToggleSwitch] = {}
        self._rows: dict[int, QWidget] = {}

        col = QVBoxLayout(self)
        col.setContentsMargins(
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
        )
        col.setSpacing(theme.LAYOUT_GAP_CONTROL)

        title_row = QHBoxLayout()
        title = QLabel("NMOS OUTPUTS")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.rail_hint = QLabel("12V OFF")
        self.rail_hint.setObjectName("secondary")
        title_row.addWidget(self.rail_hint)
        col.addLayout(title_row)

        for idx, label in enumerate(self.ROWS, start=1):
            # 每行一张内嵌子面板, 与卡片底色拉开层次但使用同一套令牌,
            # 避免裸布局行与卡片底色产生无意识的色差分层.
            row_frame = QFrame()
            row_frame.setObjectName("nmosRow")
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(12, 8, 12, 8)
            name = QLabel(label)
            name.setObjectName("toolbarLabel")
            row.addWidget(name, 1)
            switch = ToggleSwitch()
            switch.toggled.connect(
                lambda on, i=idx: self.nmos_changed.emit(i, on)
            )
            self._switches[idx] = switch
            row.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)
            self._rows[idx] = row_frame
            col.addWidget(row_frame)

        self.hint = QLabel("12V 关闭时 NMOS 无法开启")
        self.hint.setObjectName("secondary")
        col.addWidget(self.hint)
        col.addStretch(1)

    # ---- 公开 API ----
    def set_state(self, states: dict[int, bool]) -> None:
        for idx, switch in self._switches.items():
            switch.set_on(states.get(idx, False), animate=False)

    def set_rail_available(self, available: bool) -> None:
        """12V 联锁: 不可用时三路开关整体禁用."""
        self._rail_available = available
        for switch in self._switches.values():
            switch.setEnabled(available and self._base_enabled)
        self.rail_hint.setText("12V ON" if available else "12V OFF")
        self._apply_rail_style(available)
        self.hint.setText(
            "12V 已开启，可控制三路 NMOS"
            if available
            else "12V 关闭时 NMOS 无法开启"
        )

    def _apply_rail_style(self, available: bool) -> None:
        color = theme.STATUS_OK if available else theme.STATUS_WARN
        self.rail_hint.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;"
        )

    def set_controls_enabled(self, enabled: bool) -> None:
        """总门禁 (连接/透传状态); 联锁仍由 set_rail_available 决定."""
        self._base_enabled = enabled
        for switch in self._switches.values():
            switch.setEnabled(enabled and self._rail_available)
        self.rail_hint.setVisible(enabled)
        self.hint.setVisible(enabled)

    _rail_available = False
    _base_enabled = False

    def refresh_theme(self) -> None:
        self._apply_rail_style(self._rail_available)
        self.update()
