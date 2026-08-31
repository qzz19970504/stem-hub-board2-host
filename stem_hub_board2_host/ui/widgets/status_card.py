"""状态卡片 — AT+STATUS=? 回读结果的芯片化展示."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from ...models import StatusState


# (key, 显示名, on 时颜色状态, off 时颜色状态)
_FIELDS = (
    ("12V", "12V", "on", "off"),
    ("18V", "18V", "on", "off"),
    ("NMOS1", "NMOS1", "on", "off"),
    ("NMOS2", "NMOS2", "on", "off"),
    ("NMOS3", "NMOS3", "on", "off"),
    ("PWM", "PWM", "info", "info"),
    ("PWM_TARGET", "TARGET", "info", "info"),
    ("PWM_TIME", "FADE", "info", "info"),
    ("BREATH", "BREATH", "warn", "off"),
)


def _field_values(status: StatusState | None) -> dict[str, str]:
    if status is None:
        return {}
    return {
        "12V": "ON" if status.power_12v else "OFF",
        "18V": "ON" if status.power_18v else "OFF",
        "NMOS1": "ON" if status.nmos1 else "OFF",
        "NMOS2": "ON" if status.nmos2 else "OFF",
        "NMOS3": "ON" if status.nmos3 else "OFF",
        "PWM": f"{status.pwm}%",
        "PWM_TARGET": f"{status.pwm_target}%",
        "PWM_TIME": f"{status.pwm_time_ms}ms",
        "BREATH": "ON" if status.breath else "OFF",
    }


class StatusCard(QFrame):
    """最近一次 +STATUS 回读的芯片墙."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        col = QVBoxLayout(self)
        col.setContentsMargins(
            14, 12, 14, 12,
        )
        col.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("DEVICE STATUS")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.source_label = QLabel("等待回读")
        self.source_label.setObjectName("secondary")
        title_row.addWidget(self.source_label)
        col.addLayout(title_row)

        grid = QGridLayout()
        grid.setSpacing(8)
        col.addLayout(grid, 1)

        self._chips: dict[str, QLabel] = {}
        for index, (key, label, _on_state, _off_state) in enumerate(_FIELDS):
            row, column = divmod(index, 3)
            chip = QLabel(f"{label} --")
            chip.setObjectName("statusChip")
            chip.setProperty("chipState", "off")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._chips[key] = chip
            grid.addWidget(chip, row, column)
        col.addStretch(1)

    # ---- 公开 API ----
    def update_from_status(self, status: StatusState | None) -> None:
        values = _field_values(status)
        for key, label, on_state, off_state in _FIELDS:
            chip = self._chips[key]
            if not values:
                chip.setText(f"{label} --")
                self._set_chip_state(chip, "off")
                continue
            value = values[key]
            chip.setText(f"{label} {value}")
            if value == "ON":
                self._set_chip_state(chip, on_state)
            elif value == "OFF":
                self._set_chip_state(chip, off_state)
            else:
                self._set_chip_state(chip, "info")
        self.source_label.setText(
            "来自 AT+STATUS=?" if status is not None else "等待回读"
        )

    def set_refreshing(self, refreshing: bool) -> None:
        self.source_label.setText(
            "等待回读" if not refreshing else "轮询中 (1 Hz)"
        )

    # ---- 内部 ----
    @staticmethod
    def _set_chip_state(chip: QLabel, state: str) -> None:
        chip.setProperty("chipState", state)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()
