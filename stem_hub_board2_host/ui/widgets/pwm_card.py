"""PWM 控制卡片 — 占空比 / 渐变时间 / 呼吸灯, 受 18V 联锁."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QPushButton,
    QVBoxLayout,
)

from .. import theme
from .toggle_switch import ToggleSwitch


class PwmCard(QFrame):
    """PB9 / TIM4_CH4 25kHz PWM 控制."""

    pwm_changed = Signal(int)
    pwm_time_changed = Signal(int)
    breath_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        col = QVBoxLayout(self)
        col.setContentsMargins(
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
        )
        col.setSpacing(theme.LAYOUT_GAP_CONTROL)

        title_row = QHBoxLayout()
        title = QLabel("PWM OUTPUT")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.rail_hint = QLabel("18V OFF")
        self.rail_hint.setObjectName("secondary")
        title_row.addWidget(self.rail_hint)
        col.addLayout(title_row)

        # 当前值 / 目标值 + 渐变进度
        value_row = QHBoxLayout()
        self.value_label = QLabel("PWM 0%")
        f = self.value_label.font()
        f.setPointSize(22)
        f.setBold(True)
        self.value_label.setFont(f)
        value_row.addWidget(self.value_label)
        value_row.addStretch(1)
        self.target_label = QLabel("TARGET 0%")
        self.target_label.setObjectName("secondary")
        value_row.addWidget(self.target_label)
        col.addLayout(value_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        col.addWidget(self.progress)

        # 占空比设置行
        pwm_row = QHBoxLayout()
        self.pwm_slider = QSlider(Qt.Orientation.Horizontal)
        self.pwm_slider.setRange(0, 100)
        self.pwm_slider.valueChanged.connect(self._on_slider_moved)
        pwm_row.addWidget(self.pwm_slider, 1)
        self.pwm_spin = QSpinBox()
        self.pwm_spin.setRange(0, 100)
        self.pwm_spin.setSuffix(" %")
        self.pwm_spin.setFixedWidth(108)
        self.pwm_slider.valueChanged.connect(self.pwm_spin.setValue)
        self.pwm_spin.valueChanged.connect(self.pwm_slider.setValue)
        pwm_row.addWidget(self.pwm_spin)
        self.pwm_apply = QPushButton("SET")
        self.pwm_apply.setObjectName("primary")
        self.pwm_apply.clicked.connect(self._on_pwm_apply)
        pwm_row.addWidget(self.pwm_apply)
        col.addLayout(pwm_row)

        # 滑条/输入框是待提交设置值 (纯输入件): 回读不覆盖,
        # 仅在首次回读或重连后同步一次; 回读目标由 TARGET 标签与芯片呈现.
        self._input_initialized = False

        # 渐变时间设置行
        time_row = QHBoxLayout()
        time_caption = QLabel("FADE TIME")
        time_caption.setObjectName("toolbarLabel")
        time_row.addWidget(time_caption)
        time_row.addStretch(1)
        self.time_spin = QSpinBox()
        self.time_spin.setRange(0, 10000)
        self.time_spin.setSingleStep(100)
        self.time_spin.setSuffix(" ms")
        self.time_spin.setFixedWidth(144)
        time_row.addWidget(self.time_spin)
        self.time_apply = QPushButton("SET")
        self.time_apply.setObjectName("secondaryAction")
        self.time_apply.clicked.connect(self._on_time_apply)
        time_row.addWidget(self.time_apply)
        col.addLayout(time_row)

        # 呼吸灯演示
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(theme.DIVIDER_HEIGHT)
        col.addWidget(divider)
        breath_row = QHBoxLayout()
        breath_text = QVBoxLayout()
        breath_text.setSpacing(2)
        breath_title = QLabel("BREATH DEMO")
        breath_title.setObjectName("toolbarLabel")
        breath_text.addWidget(breath_title)
        breath_sub = QLabel("需先开启 18V；演示期间普通 PWM 命令被拒")
        breath_sub.setObjectName("secondary")
        breath_text.addWidget(breath_sub)
        breath_row.addLayout(breath_text, 1)
        self.breath_switch = ToggleSwitch()
        self.breath_switch.toggled.connect(self.breath_changed)
        breath_row.addWidget(self.breath_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        col.addLayout(breath_row)

        col.addStretch(1)

        self._refresh_progress_style()

    # ---- 公开 API ----
    def update_state(
        self,
        *,
        pwm: int,
        pwm_target: int,
        pwm_time_ms: int,
        breath: bool,
    ) -> None:
        """由 +STATUS 回读驱动; 不回发信号.

        大数值/进度条是显示件, 始终跟随回读;
        滑条/输入框是待提交设置值, 仅首次(或重连后)同步, 之后不被覆盖.
        """
        self.value_label.setText(f"PWM {pwm}%")
        self.target_label.setText(f"TARGET {pwm_target}%")
        self.progress.setValue(pwm)
        if not self._input_initialized:
            self._sync_input_from_read(pwm_target, pwm_time_ms)
            self._input_initialized = True
        self.breath_switch.set_on(breath, animate=False)

    def reset_input(self) -> None:
        """断开连接后重置输入件, 下次回读重新同步."""
        self._input_initialized = False
        self._sync_input_from_read(0, 500)

    def _sync_input_from_read(self, target: int, time_ms: int) -> None:
        self.pwm_spin.blockSignals(True)
        self.pwm_slider.blockSignals(True)
        self.time_spin.blockSignals(True)
        self.pwm_spin.setValue(target)
        self.pwm_slider.setValue(target)
        self.time_spin.setValue(time_ms)
        self.pwm_spin.blockSignals(False)
        self.pwm_slider.blockSignals(False)
        self.time_spin.blockSignals(False)

    def set_rail_available(self, available: bool) -> None:
        """18V 联锁: 关闭时 PWM 只能保持 0%."""
        self._rail_available = available
        controls = (
            self.pwm_slider, self.pwm_spin, self.pwm_apply,
            self.time_spin, self.time_apply, self.breath_switch,
        )
        for control in controls:
            control.setEnabled(available and self._base_enabled)
        self.rail_hint.setText("18V ON" if available else "18V OFF")
        self._apply_rail_style(available)

    def _apply_rail_style(self, available: bool) -> None:
        color = theme.STATUS_OK if available else theme.STATUS_WARN
        self.rail_hint.setStyleSheet(
            f"color: {color}; font-weight: 700; background: transparent;"
        )

    def set_controls_enabled(self, enabled: bool) -> None:
        self._base_enabled = enabled
        available = self._rail_available and enabled
        for control in (
            self.pwm_slider, self.pwm_spin, self.pwm_apply,
            self.time_spin, self.time_apply, self.breath_switch,
        ):
            control.setEnabled(available)
        self.rail_hint.setVisible(enabled)

    _rail_available = False
    _base_enabled = False

    def refresh_theme(self) -> None:
        self._refresh_progress_style()
        self._apply_rail_style(self._rail_available)

    # ---- 内部 ----
    def _refresh_progress_style(self) -> None:
        self.progress.setStyleSheet(
            "QProgressBar {"
            f"  background: {theme.BG_INPUT};"
            f"  border: 1px solid {theme.BORDER};"
            "  border-radius: 4px;"
            "}"
            "QProgressBar::chunk {"
            f"  background: {theme.ACCENT};"
            "  border-radius: 3px;"
            "}"
        )

    def _on_slider_moved(self, value: int) -> None:
        self.value_label.setText(f"PWM {value}%")

    def _on_pwm_apply(self) -> None:
        self.pwm_changed.emit(self.pwm_spin.value())

    def _on_time_apply(self) -> None:
        self.pwm_time_changed.emit(self.time_spin.value())
