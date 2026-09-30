"""标题栏两种风格：macOS 左侧红黄绿交通灯 / Windows 右侧 — □ ✕，可拖动、双击切最大化。

配合无边框窗口用（MainWindow 设了 FramelessWindowHint）。
关闭走 window().close()，最终是藏托盘还是真退由 MainWindow.closeEvent 决定。
风格选择存 settings["titlebar"]（macos | windows），MainWindow 按 TITLEBARS 取类。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

LIGHT_SIZE = 14   # 交通灯圆点直径
WIN_BTN_W = 46    # Windows 风格按钮宽度（原生约 46px，高度撑满标题栏）


class _BaseTitleBar(QWidget):
    """两种风格共用的：固定高度、拖动、双击切最大化。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)
        self._drag_pos: QPoint | None = None

    def _toggle_max(self) -> None:
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos is not None and not self.window().isMaximized():
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()


class TitleBar(_BaseTitleBar):
    """macOS 风格：左侧红黄绿交通灯 + 居中标题。"""

    def __init__(self, title: str, parent: QWidget):
        super().__init__(parent)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(0)

        lights = QWidget()
        lights_lay = QHBoxLayout(lights)
        lights_lay.setContentsMargins(0, 0, 0, 0)
        lights_lay.setSpacing(8)
        close_btn = self._light("close", "✕", "关闭（最小化到托盘）")
        min_btn = self._light("min", "–", "最小化")
        max_btn = self._light("max", "＋", "最大化 / 还原")
        close_btn.clicked.connect(lambda: self.window().close())
        min_btn.clicked.connect(lambda: self.window().showMinimized())
        max_btn.clicked.connect(self._toggle_max)
        for b in (close_btn, min_btn, max_btn):
            lights_lay.addWidget(b)
        # 右边补一个同宽的占位，标题才能相对整个窗口居中
        lights.setFixedWidth(3 * LIGHT_SIZE + 2 * 8)

        self._title = QLabel(title)
        self._title.setObjectName("TitleText")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 标题不抢鼠标事件，按住标题也能拖窗口
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        spacer = QWidget()
        spacer.setFixedWidth(3 * LIGHT_SIZE + 2 * 8)

        lay.addWidget(lights)
        lay.addWidget(self._title, 1)
        lay.addWidget(spacer)

    def _light(self, kind: str, glyph: str, tooltip: str) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setObjectName("MacBtn")
        btn.setProperty("kind", kind)
        btn.setToolTip(tooltip)
        btn.setFixedSize(LIGHT_SIZE, LIGHT_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn


class WinTitleBar(_BaseTitleBar):
    """Windows 风格：右侧 — □ ✕（悬停变灰，关闭悬停变红），标题居中。"""

    def __init__(self, title: str, parent: QWidget):
        super().__init__(parent)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 0, 0)  # 右不留边，按钮贴到窗口边缘才像原生
        lay.setSpacing(0)

        # 左边补一个占位让标题相对整个窗口居中：左边距 14 + 占位 = 按钮组宽度
        spacer = QWidget()
        spacer.setFixedWidth(3 * WIN_BTN_W - 14)
        lay.addWidget(spacer)

        self._title = QLabel(title)
        self._title.setObjectName("TitleText")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 标题不抢鼠标事件，按住标题也能拖窗口
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._title, 1)

        min_btn = self._win_btn("min", "–", "最小化")
        max_btn = self._win_btn("max", "□", "最大化 / 还原")
        close_btn = self._win_btn("close", "✕", "关闭（最小化到托盘）")
        min_btn.clicked.connect(lambda: self.window().showMinimized())
        max_btn.clicked.connect(self._toggle_max)
        close_btn.clicked.connect(lambda: self.window().close())
        for b in (min_btn, max_btn, close_btn):
            lay.addWidget(b)

    def _win_btn(self, kind: str, glyph: str, tooltip: str) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setObjectName("WinBtn")
        btn.setProperty("kind", kind)
        btn.setToolTip(tooltip)
        btn.setFixedSize(WIN_BTN_W, 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn


# settings["titlebar"] 的值 → 标题栏类，MainWindow 按这个取
TITLEBARS = {"macos": TitleBar, "windows": WinTitleBar}
