"""设置对话框：外观 / 界面尺寸 / 工作区 / 全局热键 / 数据位置，分区卡片式布局。

按项目约定只发信号，落地动作（应用主题、重建视图、换工作区、写 settings）
由 MainWindow 接线处理。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings, default_workspace_presets
from core.hotkey import parse_hotkey
from core.version import __version__

THEMES = (("light", "浅色"), ("dark", "深色"))
TITLEBARS = (("macos", "苹果风格（左侧 ●●●）"), ("windows", "Windows 风格（右侧 — □ ✕）"))
VIEWS = (("grid", "网格"), ("list", "列表"))
TAG_CLOUD = ((False, "隐藏"), (True, "显示"))

HOTKEY_SYNTAX = ("支持 Alt / Ctrl / Shift / Win 组合 + 字母 / 数字 / F1-F12 / Space / Tab；"
                 "字母、数字、Space、Tab 需搭配修饰键，F1-F12 可单独使用")

# 推荐窗口尺寸：(显示名, (宽, 高))，None 表示自定义
WINDOW_PRESETS = (
    ("笔记本 · 1280×760（13 寸小屏）", (1280, 760)),
    ("笔记本 · 1440×860（14/15 寸，默认）", (1440, 860)),
    ("笔记本 · 1600×950（15.6 寸）", (1600, 950)),
    ("台式 · 1920×1080（1080P 显示器）", (1920, 1080)),
    ("台式 · 2560×1440（2K 显示器）", (2560, 1440)),
    ("自定义", None),
)
WINDOW_MIN_W, WINDOW_MIN_H = 1100, 680   # 与 MainWindow.setMinimumSize 保持一致


class SettingsDialog(QDialog):
    themeChanged = Signal(str)               # "light" | "dark"
    titleBarChanged = Signal(str)            # "macos" | "windows"
    viewChanged = Signal(str)                # "grid" | "list"
    tagCloudChanged = Signal(bool)           # 侧栏标签云显隐
    hotkeyChanged = Signal(str)              # 校验通过的新热键
    windowSizeChanged = Signal(int, int)     # 校验通过的窗口尺寸 (宽, 高)
    workspaceChangeRequested = Signal()      # 让 MainWindow 弹目录选择
    presetsChanged = Signal(list)            # 工作区快捷按钮预设 [{name, path}] ×2

    def __init__(self, app_dir: Path, settings: Settings,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.app_dir = app_dir
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(14)

        lay.addWidget(self._build_appearance())
        lay.addWidget(self._build_window_size())
        lay.addWidget(self._build_workspace())
        lay.addWidget(self._build_hotkey())
        lay.addWidget(self._build_data())

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)

    # ── 布局工具 ──
    def _card(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        """分区标题 + 圆角卡片，返回 (容器, 卡片内布局)。"""
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        head = QLabel(title)
        head.setObjectName("SettingsSection")
        outer.addWidget(head)
        card = QFrame()
        card.setObjectName("SettingsCard")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(8)
        outer.addWidget(card)
        return box, inner

    def _row(self, key: str) -> tuple[QWidget, QHBoxLayout]:
        """卡片里的一行：左侧固定宽度的键名 + 右侧控件区。"""
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        k = QLabel(key)
        k.setObjectName("SettingsKey")
        k.setFixedWidth(64)
        lay.addWidget(k)
        return row, lay

    def _path_label(self, text: str) -> QLabel:
        """长路径中间省略，完整路径放 tooltip，文本可选中复制。"""
        lab = QLabel()
        lab.setObjectName("SettingsValue")
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._set_path(lab, text)
        return lab

    @staticmethod
    def _set_path(lab: QLabel, text: str) -> None:
        lab.setText(lab.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideMiddle, 360))
        lab.setToolTip(text)

    @staticmethod
    def _hint(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("SettingsHint")
        lab.setWordWrap(True)
        return lab

    # ── 各分区 ──
    def _build_appearance(self) -> QWidget:
        box, inner = self._card("外观")

        row, lay = self._row("主题")
        self._theme_combo = self._make_combo(THEMES, self.settings.get("theme", "light"))
        self._theme_combo.currentIndexChanged.connect(
            lambda i: self.themeChanged.emit(self._theme_combo.itemData(i)))
        lay.addWidget(self._theme_combo, 1)
        inner.addWidget(row)

        row, lay = self._row("标题栏")
        self._tb_combo = self._make_combo(
            TITLEBARS, self.settings.get("titlebar", "macos"))
        self._tb_combo.currentIndexChanged.connect(
            lambda i: self.titleBarChanged.emit(self._tb_combo.itemData(i)))
        lay.addWidget(self._tb_combo, 1)
        inner.addWidget(row)

        row, lay = self._row("默认视图")
        self._view_combo = self._make_combo(VIEWS, self.settings.get("view", "grid"))
        self._view_combo.currentIndexChanged.connect(
            lambda i: self.viewChanged.emit(self._view_combo.itemData(i)))
        lay.addWidget(self._view_combo, 1)
        inner.addWidget(row)

        row, lay = self._row("标签云")
        self._tags_combo = self._make_combo(
            TAG_CLOUD, self.settings.get("show_tags", False))
        self._tags_combo.currentIndexChanged.connect(
            lambda i: self.tagCloudChanged.emit(self._tags_combo.itemData(i)))
        lay.addWidget(self._tags_combo, 1)
        inner.addWidget(row)
        return box

    @staticmethod
    def _make_combo(items: tuple[tuple[object, str], ...], current) -> QComboBox:
        combo = QComboBox()
        for key, label in items:
            combo.addItem(label, key)
        idx = combo.findData(current)
        if idx >= 0:  # 先定位再连信号，初始化不会误触发
            combo.setCurrentIndex(idx)
        return combo

    def _build_window_size(self) -> QWidget:
        """界面尺寸：推荐预设下拉框选中即生效；「自定义」展开宽高手动输入。"""
        box, inner = self._card("界面尺寸")
        cur = self.settings.get("window", {"w": 1440, "h": 860})
        cur_size = (int(cur.get("w", 1440)), int(cur.get("h", 860)))

        row, lay = self._row("推荐尺寸")
        self._size_combo = QComboBox()
        for label, size in WINDOW_PRESETS:
            self._size_combo.addItem(label, size)
        idx = self._size_combo.findData(cur_size)
        # 当前尺寸不在预设里 → 停在「自定义」并回填当前值
        self._size_combo.setCurrentIndex(idx if idx >= 0 else len(WINDOW_PRESETS) - 1)
        lay.addWidget(self._size_combo, 1)
        inner.addWidget(row)

        custom_row, clay = self._row("自定义")
        self._w_edit = QLineEdit(str(cur_size[0]))
        self._h_edit = QLineEdit(str(cur_size[1]))
        self._w_edit.setFixedWidth(72)
        self._h_edit.setFixedWidth(72)
        clay.addWidget(self._w_edit)
        clay.addWidget(QLabel("×"))
        clay.addWidget(self._h_edit)
        apply_btn = QPushButton("应用")
        apply_btn.setObjectName("MiniBtn")
        apply_btn.clicked.connect(self._apply_custom_size)
        clay.addWidget(apply_btn)
        clay.addStretch(1)
        inner.addWidget(custom_row)
        self._custom_row = custom_row

        self._size_hint = self._hint(
            f"推荐尺寸选中立即生效；自定义宽 ≥ {WINDOW_MIN_W}、高 ≥ {WINDOW_MIN_H}")
        inner.addWidget(self._size_hint)

        self._size_combo.currentIndexChanged.connect(self._on_size_preset)
        self._sync_custom_row()
        return box

    def _sync_custom_row(self) -> None:
        """只有选中「自定义」才显示宽高输入行。"""
        self._custom_row.setVisible(self._size_combo.currentData() is None)

    def _on_size_preset(self, i: int) -> None:
        self._sync_custom_row()
        size = self._size_combo.itemData(i)
        if size is not None:
            self.windowSizeChanged.emit(*size)

    def _apply_custom_size(self) -> None:
        """校验自定义宽高，非法输入标红提示，不写 settings。"""
        try:
            w, h = int(self._w_edit.text()), int(self._h_edit.text())
        except ValueError:
            self._set_size_state(False, "宽和高必须是整数，未保存")
            return
        if w < WINDOW_MIN_W or h < WINDOW_MIN_H:
            self._set_size_state(
                False, f"尺寸太小，宽 ≥ {WINDOW_MIN_W}、高 ≥ {WINDOW_MIN_H}，未保存")
            return
        self._set_size_state(True, "已应用")
        self.windowSizeChanged.emit(w, h)

    def _set_size_state(self, valid: bool, hint: str) -> None:
        self._w_edit.setProperty("invalid", "" if valid else "true")
        self._h_edit.setProperty("invalid", "" if valid else "true")
        self._size_hint.setProperty("invalid", "" if valid else "true")
        self._size_hint.setText(hint)
        for w in (self._w_edit, self._h_edit, self._size_hint):  # 动态属性要刷新样式
            w.style().unpolish(w)
            w.style().polish(w)

    def _build_workspace(self) -> QWidget:
        box, inner = self._card("工作区")
        row, lay = self._row("根目录")
        self._ws_label = self._path_label("")
        self.refresh_workspace()
        lay.addWidget(self._ws_label, 1)
        btn = QPushButton("更改…")
        btn.setObjectName("MiniBtn")
        btn.clicked.connect(self.workspaceChangeRequested)
        lay.addWidget(btn)
        inner.addWidget(row)
        inner.addWidget(self._hint("分类与条目直接读取该目录，更换后立即重新扫描"))

        # 顶栏两个快捷按钮：名称 + 路径，失焦即校验保存
        self._preset_rows: list[tuple[QLineEdit, QLineEdit]] = []
        for i, preset in enumerate(self.settings.get_presets()):
            prow, play = self._row(f"按钮 {'一二'[i]}")
            name_edit = QLineEdit(preset["name"])
            name_edit.setFixedWidth(72)
            path_edit = QLineEdit(preset["path"])
            browse = QPushButton("浏览…")
            browse.setObjectName("MiniBtn")
            browse.clicked.connect(lambda _=False, e=path_edit: self._browse_preset(e))
            name_edit.editingFinished.connect(self._save_presets)
            path_edit.editingFinished.connect(self._save_presets)
            play.addWidget(name_edit)
            play.addWidget(path_edit, 1)
            play.addWidget(browse)
            self._preset_rows.append((name_edit, path_edit))
            inner.addWidget(prow)
        self._preset_hint = self._hint(self._PRESET_HINT_OK)
        inner.addWidget(self._preset_hint)
        return box

    _PRESET_HINT_OK = "顶栏两个按钮显示这里的名称，点击直达对应目录"

    def _browse_preset(self, path_edit: QLineEdit) -> None:
        root = QFileDialog.getExistingDirectory(self, "选择目录", path_edit.text())
        if root:
            path_edit.setText(root)
            self._save_presets()

    def _save_presets(self) -> None:
        """失焦时校验两条预设并保存：名称为空回退默认名，路径非法则标红、保留旧值。"""
        defaults = default_workspace_presets()
        prev = self.settings.get_presets()
        presets, bad = [], []
        for i, (name_edit, path_edit) in enumerate(self._preset_rows):
            name = name_edit.text().strip() or defaults[i]["name"]
            path = path_edit.text().strip()
            name_edit.setText(name)
            if path and Path(path).is_dir():
                presets.append({"name": name, "path": path})
                path_edit.setProperty("invalid", "false")
            else:
                bad.append(i)
                presets.append(prev[i])  # 非法路径不落盘
                path_edit.setProperty("invalid", "true")
            path_edit.style().unpolish(path_edit)
            path_edit.style().polish(path_edit)
        self._preset_hint.setProperty("invalid", "true" if bad else "false")
        self._preset_hint.setText(
            f"按钮{'、'.join('一二'[i] for i in bad)}的路径不是有效目录，未保存该项"
            if bad else self._PRESET_HINT_OK)
        self._preset_hint.style().unpolish(self._preset_hint)
        self._preset_hint.style().polish(self._preset_hint)
        self.presetsChanged.emit(presets)

    def refresh_workspace(self) -> None:
        """换工作区后由 MainWindow 回调，刷新路径显示。"""
        root = self.settings.get("workspace_root", "") or "（未设置）"
        self._set_path(self._ws_label, root)

    def _build_hotkey(self) -> QWidget:
        box, inner = self._card("全局热键")
        row, lay = self._row("唤起窗口")
        self._hk_edit = QLineEdit(self.settings.get("hotkey", "Alt+Space"))
        self._hk_edit.setPlaceholderText("例如 Ctrl+Alt+K")
        self._hk_edit.editingFinished.connect(self._save_hotkey)
        lay.addWidget(self._hk_edit, 1)
        inner.addWidget(row)
        self._hk_hint = self._hint(f"修改后重启生效；{HOTKEY_SYNTAX}")
        inner.addWidget(self._hk_hint)
        return box

    def _save_hotkey(self) -> None:
        """失焦时校验并保存；非法输入标红提示，不写 settings。"""
        text = self._hk_edit.text().strip()
        old = self.settings.get("hotkey", "Alt+Space")
        if not text or text.lower() == old.lower():
            self._hk_edit.setText(old)
            return
        if parse_hotkey(text) is None:
            self._set_hotkey_state(False, f"格式无效，未保存。{HOTKEY_SYNTAX}")
        else:
            self._set_hotkey_state(True, "已保存，重启后生效")
            self.hotkeyChanged.emit(text)

    def _set_hotkey_state(self, valid: bool, hint: str) -> None:
        self._hk_edit.setProperty("invalid", "" if valid else "true")
        self._hk_hint.setProperty("invalid", "" if valid else "true")
        self._hk_hint.setText(hint)
        for w in (self._hk_edit, self._hk_hint):  # 动态属性要刷新样式
            w.style().unpolish(w)
            w.style().polish(w)

    def _build_data(self) -> QWidget:
        box, inner = self._card("数据")
        row, lay = self._row("版本")
        ver = QLabel(f"SuperGUI v{__version__}")
        ver.setObjectName("SettingsValue")
        lay.addWidget(ver)
        lay.addStretch(1)
        inner.addWidget(row)
        for key, path in (("配置文件", self.app_dir / "config" / "config.yaml"),
                          ("元数据库", self.app_dir / "config" / "data.db")):
            row, lay = self._row(key)
            lay.addWidget(self._path_label(str(path)), 1)
            btn = QPushButton("打开位置")
            btn.setObjectName("MiniBtn")
            btn.clicked.connect(lambda _=False, p=path: self._open_in_explorer(p))
            lay.addWidget(btn)
            inner.addWidget(row)
        return box

    @staticmethod
    def _open_in_explorer(path: Path) -> None:
        """资源管理器定位文件；文件还没生成则打开所在目录。"""
        try:
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif path.parent.is_dir():
                os.startfile(path.parent)
        except OSError:
            pass
