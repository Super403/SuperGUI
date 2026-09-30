"""条目卡片：网格 / 列表两种形态，支持选中态、双击和右键菜单。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QFontMetrics, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.models import Entry

GRID_W, GRID_H = 176, 106  # 网格卡片固定尺寸
LIST_H = 52                # 列表行固定高度
ICON_GRID, ICON_LIST = 42, 32
LIST_ELIDE_W = 560         # 列表模式名称/摘要的省略宽度（px）


class EntryCard(QFrame):
    clicked = Signal(object)                   # Entry
    doubleClicked = Signal(object)             # Entry
    contextRequested = Signal(object, QPoint)  # Entry, globalPos

    def __init__(self, entry: Entry, icon: QIcon, list_mode: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.entry = entry
        self.list_mode = list_mode
        self.setObjectName("EntryCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._icon = self._make_icon(icon)
        text_box = self._make_text_box(entry)

        if list_mode:
            self._build_list_layout(text_box, entry.pinned)
        else:
            self._build_grid_layout(text_box, entry.pinned)

    # ── 搭建 ──
    def _make_icon(self, icon: QIcon) -> QLabel:
        size = ICON_LIST if self.list_mode else ICON_GRID
        lbl = QLabel()
        lbl.setObjectName("CardIcon")
        lbl.setFixedSize(size, size)
        lbl.setPixmap(icon.pixmap(size, size))
        return lbl

    def _make_text_box(self, entry: Entry) -> QVBoxLayout:
        """名称 + 摘要两行，太长就省略号截断，全文放 tooltip。"""
        self._name = QLabel()
        self._name.setObjectName("CardName")
        self._desc = QLabel()
        self._desc.setObjectName("CardDesc")

        fm = QFontMetrics(self._name.font())
        elide_w = LIST_ELIDE_W if self.list_mode else GRID_W - 28
        for lbl, text in ((self._name, entry.name), (self._desc, entry.desc)):
            lbl.setText(fm.elidedText(text, Qt.TextElideMode.ElideRight, elide_w))
            lbl.setToolTip(text)

        box = QVBoxLayout()
        box.setSpacing(2)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self._name)
        box.addWidget(self._desc)
        return box

    def set_desc(self, text: str) -> None:
        """更新摘要文字（笔记保存后同步卡片用）。"""
        fm = QFontMetrics(self._desc.font())
        elide_w = LIST_ELIDE_W if self.list_mode else GRID_W - 28
        self._desc.setText(fm.elidedText(text, Qt.TextElideMode.ElideRight, elide_w))
        self._desc.setToolTip(text)

    def _build_list_layout(self, text_box: QVBoxLayout, pinned: bool) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(13)
        lay.addWidget(self._icon)
        lay.addLayout(text_box, 1)
        if pinned:
            lay.addWidget(self._star())
        self.setFixedHeight(LIST_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _build_grid_layout(self, text_box: QVBoxLayout, pinned: bool) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 13, 13, 11)
        lay.setSpacing(9)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._icon)
        head.addStretch(1)
        if pinned:
            head.addWidget(self._star(), alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)
        lay.addLayout(text_box)
        self.setFixedSize(GRID_W, GRID_H)

    @staticmethod
    def _star() -> QLabel:
        star = QLabel("★")
        star.setObjectName("CardStar")
        return star

    # ── 选中态 ──
    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        # 改了动态属性得重刷一遍样式，QSS 选择器才生效
        self.style().unpolish(self)
        self.style().polish(self)

    # ── 事件 ──
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.entry)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.entry)
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e: QContextMenuEvent) -> None:
        self.contextRequested.emit(self.entry, e.globalPos())
