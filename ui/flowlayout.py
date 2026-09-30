"""流式布局：卡片按宽度自动换行，照 Qt 官方 FlowLayout 示例移植的。

Qt 没自带流式布局。关键在 hasHeightForWidth() 返回 True：
滚动区宽度变了会反过来问我们要多高，窗口一窄，卡片换行、高度自动跟着涨。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, margin: int = 0,
                 h_spacing: int = 12, v_spacing: int = 12):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_space = h_spacing
        self._v_space = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # ── QLayout 要求的接口：子项增删查 ──
    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    # ── 尺寸协商 ──
    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientation(0)  # 不主动扩张，由父布局决定

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """按顺序摆，一行放不下就换行。test_only=True 只算高度，不真的摆。"""
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_height = effective.x(), effective.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_space
            # 换行判定：next_x 减回间距才是真实右缘；line_height > 0 保证每行首项不换行
            if next_x - self._h_space > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_space
                next_x = x + hint.width() + self._h_space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + m.bottom()
