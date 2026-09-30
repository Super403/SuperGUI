"""统计卡片行：大数字 + 底部彩条，仅在「全部条目」无筛选时展示。"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

# (标题, 底部彩条颜色)，顺序就是卡片顺序，和 set_stats 参数一一对应
CARDS = [
    ("工  具", "#3cb56f"),
    ("项目 / 目录", "#4a9cf5"),
    ("已 固 定", "#f7b73c"),
]


class StatsRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatsRow")
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)
        self._values: list[QLabel] = []  # 与 CARDS 同序，set_stats 按下标回写
        for title, color in CARDS:
            self._lay.addWidget(self._card(title, color))

    def _card(self, title: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("StatCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 13, 16, 12)
        lay.setSpacing(5)

        key = QLabel(title)
        key.setObjectName("StatKey")
        value = QLabel("0")
        value.setObjectName("StatValue")
        bar = QFrame()
        bar.setObjectName("StatBar")
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px;")

        lay.addWidget(key)
        lay.addWidget(value)
        lay.addWidget(bar)
        self._values.append(value)
        return frame

    def set_stats(self, tools: int, projects: int, pinned: int) -> None:
        """按 CARDS 顺序回写三个数字。"""
        for label, val in zip(self._values, (tools, projects, pinned), strict=True):
            label.setText(str(val))
