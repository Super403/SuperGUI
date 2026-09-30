"""左侧导航：快捷区（全部/已固定/最近）+ 分类树 + 标签云 + 底部占用卡。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.models import Category
from ui.flowlayout import FlowLayout
from ui.misc import ICON_COLOR, SVG_CLOCK, SVG_FOLDER, SVG_GRID, SVG_STAR, svg_icon

ICON_COLOR_ACTIVE = "#2f9d5d"

# 快捷区写死三项：(nav key, 显示文本, 图标)，数量在 rebuild 时传进来
QUICK_NAVS = (
    ("all", "全部条目", SVG_GRID),
    ("star", "已固定", SVG_STAR),
    ("recent", "最近使用", SVG_CLOCK),
)

TAG_CLOUD_MAX_H = 120  # 标签云限高，避免挤占分类区


class SideBar(QWidget):
    navChanged = Signal(str)        # "all" | "star" | "recent" | cat_id
    tagChanged = Signal(object)     # str | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SideBar")
        self.setFixedWidth(200)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(10, 14, 10, 10)
        self._lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._tag_buttons: dict[str, QPushButton] = {}
        self._current_nav = "all"
        self._current_tag: str | None = None

    # ── 重建 ──
    def rebuild(self, categories: list[Category], total: int,
                star_count: int, recent_count: int, tags: list[str]) -> None:
        """全量重建。选中状态存在 _current_nav/_current_tag，重建完 _sync_state 恢复。"""
        self._clear_layout(self._lay)
        for btn in list(self._group.buttons()):  # 清掉上一轮按钮，复用同一个按钮组避免累积
            self._group.removeButton(btn)
        self._nav_buttons.clear()
        self._tag_buttons.clear()

        self._build_quick_nav(total, star_count, recent_count)
        self._build_category_tree(categories)
        if tags:
            self._build_tag_cloud(tags)
        self._build_usage_card(categories, total)

        self._sync_state()
        self._cat_scroll.verticalScrollBar().setValue(0)  # 重建后分类区滚回顶部

    def _build_quick_nav(self, total: int, star_count: int, recent_count: int) -> None:
        counts = {"all": total, "star": star_count, "recent": recent_count}
        for key, text, svg in QUICK_NAVS:
            self._lay.addWidget(self._nav_btn(key, text, counts[key], svg))

    def _build_category_tree(self, categories: list[Category]) -> None:
        """分类列表，放滚动区里，吃掉剩余空间。"""
        self._lay.addSpacing(10)
        self._lay.addWidget(self._section_title("分 类"))
        scroll, box = self._make_scroll()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        for cat in categories:
            lay.addWidget(self._nav_btn(cat.cat_id, cat.name, len(cat.entries), SVG_FOLDER))
        lay.addStretch(1)
        scroll.setWidget(box)
        self._lay.addWidget(scroll, 1)
        self._cat_scroll = scroll

    def _build_tag_cloud(self, tags: list[str]) -> None:
        """标签云：流式布局 + 限高滚动。标签和导航互斥，高亮逻辑在 _sync_state。"""
        self._lay.addSpacing(6)
        self._lay.addWidget(self._section_title("标 签"))
        scroll, cloud = self._make_scroll(max_height=TAG_CLOUD_MAX_H)
        flow = FlowLayout(cloud, margin=2, h_spacing=6, v_spacing=6)
        for tag in tags:
            btn = QPushButton(tag)
            btn.setObjectName("TagBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=tag: self._on_tag(t))
            self._tag_buttons[tag] = btn
            flow.addWidget(btn)
        scroll.setWidget(cloud)
        self._lay.addWidget(scroll)

    def _build_usage_card(self, categories: list[Category], total: int) -> None:
        """底部占用卡：分类/条目数 + 进度条（条目数按 100 封顶，纯装饰）。"""
        card = QWidget()
        card.setObjectName("UsageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(13, 11, 13, 11)
        lay.setSpacing(7)

        top = QHBoxLayout()
        top.addWidget(QLabel("分类 / 条目"))
        top.addStretch(1)
        num = QLabel(f"{len(categories)} / {total}")
        num.setObjectName("UsageNum")
        top.addWidget(num)

        bar = QProgressBar()
        bar.setObjectName("UsageBar")
        bar.setRange(0, 100)
        bar.setValue(min(100, total))
        bar.setTextVisible(False)
        bar.setFixedHeight(5)

        lay.addLayout(top)
        lay.addWidget(bar)
        self._lay.addWidget(card)

    # ── 小组件 ──
    @staticmethod
    def _make_scroll(max_height: int | None = None) -> tuple[QScrollArea, QWidget]:
        """侧边栏通用滚动区：无边框、禁横向、视口透明（不然深色主题下有白块）。"""
        scroll = QScrollArea()
        scroll.setObjectName("SideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        if max_height is not None:
            scroll.setMaximumHeight(max_height)
        box = QWidget()
        box.setObjectName("SideContent")  # objectName 给 QSS 用
        return scroll, box

    @staticmethod
    def _clear_layout(layout) -> None:
        """递归清空布局。"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                SideBar._clear_layout(item.layout())

    def _nav_btn(self, key: str, text: str, count: int, svg: str) -> QPushButton:
        btn = QPushButton(f"  {text}")
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setMinimumHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(svg_icon(svg, ICON_COLOR))
        btn.setProperty("navKey", key)
        btn.setProperty("svg", svg)  # svg 存属性里，换色时直接取
        if count:
            btn.setText(f"  {text}   {count}")
        btn.clicked.connect(lambda _=False, k=key: self._on_nav(k))
        self._group.addButton(btn)
        self._nav_buttons[key] = btn
        return btn

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("NavTitle")
        return lbl

    # ── 选中状态 ──
    def _on_nav(self, key: str) -> None:
        self._current_nav = key
        self._current_tag = None  # 导航和标签互斥
        self._sync_state()
        self.navChanged.emit(key)

    def _on_tag(self, tag: str) -> None:
        # 同一个标签再点一次就是取消筛选
        self._current_tag = None if self._current_tag == tag else tag
        if self._current_tag is not None:
            self._current_nav = "all"  # 标签和导航互斥
        self._sync_state()
        self.tagChanged.emit(self._current_tag)

    def _sync_state(self) -> None:
        """把当前选中落到按钮勾选态和图标颜色上。"""
        for key, btn in self._nav_buttons.items():
            active = key == self._current_nav and self._current_tag is None
            btn.setChecked(active)
            color = ICON_COLOR_ACTIVE if active else ICON_COLOR
            btn.setIcon(svg_icon(btn.property("svg"), color))
        for tag, btn in self._tag_buttons.items():
            btn.setChecked(tag == self._current_tag)

    def set_current(self, key: str) -> None:
        """给主窗口强制切导航用，不发信号，调用方自己会重建。"""
        self._current_nav = key
        self._current_tag = None
        self._sync_state()
