"""Tab 2: UART 透传."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets.passthrough_panel import PassthroughPanel


class PassthroughTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
        )
        lay.setSpacing(theme.GRID_GAP)

        self.panel = PassthroughPanel()
        lay.addWidget(self.panel, 1)
