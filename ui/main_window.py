"""主窗口：顶栏 + 侧边导航 + 卡片区 + 详情面板 + 状态栏 + 托盘。

widgets 只管发信号，数据怎么流（scanner → db 合并 → 重建 UI）
统一在 reload() 里处理。
"""
from __future__ import annotations

import ctypes
import datetime
import hashlib
import logging
import os
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QFileInfo, QFileSystemWatcher, QObject, QPoint, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from core import launcher, notes, scanner
from core.models import TYPE_TOOL, Category, Entry
from core.version import __version__
from config.db import DB
from config.settings import Settings
from ui.flowlayout import FlowLayout
from ui.misc import (
    ICON_COLOR,
    SVG_GRID,
    SVG_LIST,
    SVG_MOON,
    SVG_PANEL,
    SVG_REFRESH,
    SVG_SEARCH,
    SVG_SETTINGS,
    SVG_SUN,
    make_logo_icon,
    svg_icon,
)
from ui.widgets.card import EntryCard
from ui.widgets.detail import CommandDialog, DetailPanel
from ui.widgets.settings_dialog import SettingsDialog
from ui.widgets.sidebar import SideBar
from ui.widgets.stats_row import StatsRow
from ui.widgets.titlebar import TITLEBARS, TitleBar

log = logging.getLogger(__name__)

WINDOW_TITLE = f"SuperGUI v{__version__} - 适用于网络安全人员使用的工具箱"
NOTE_CACHE_BYTES = 8192          # 笔记搜索缓存只取前 8KB，够命中又不拖慢扫描
NAV_TITLES = {"all": "全部条目", "star": "已固定", "recent": "最近使用"}
DEFAULT_WINDOW_SIZE = {"w": 1440, "h": 860}
def _ipc_name() -> str:
    """单实例 IPC 名带上当前用户标识：命名管道是机器级的，多用户同机不能串台。"""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    return "supergui-ipc-" + hashlib.md5(user.encode("utf-8", "ignore")).hexdigest()[:8]


IPC_NAME = _ipc_name()           # 单实例唤起的本地 socket 名；main.py 的第二实例也连它

# ── 无边框窗口的原生边框缩放 ──
WM_NCHITTEST = 0x0084
RESIZE_MARGIN = 6   # 边框判定宽度（像素），视觉上不可见
# 命中码：左10 右11 上12 左上13 右上14 下15 左下16 右下17（Windows 固定值）
HT_LEFT, HT_RIGHT, HT_TOP, HT_BOTTOM = 10, 11, 12, 15
HT_TOPLEFT, HT_TOPRIGHT, HT_BOTTOMLEFT, HT_BOTTOMRIGHT = 13, 14, 16, 17


class MSG(ctypes.Structure):
    """Win32 MSG 结构，从原生事件指针还原消息。main.py 的热键过滤器也复用它。"""

    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", wintypes.POINT)]


class _ScanWorker(QObject):
    """后台扫描：目录遍历 + 笔记缓存读取，结果回主线程后再碰 DB / UI。

    系统图标必须在主线程创建（QPixmap 限制），所以不在这里做。
    """

    done = Signal(object, object)   # categories, note_cache
    failed = Signal(str)

    def __init__(self, workspace: Path):
        super().__init__()
        self._workspace = Path(workspace)

    def run(self) -> None:
        try:
            categories = scanner.scan(self._workspace)
            entries = [e for c in categories for e in c.entries]
            note_cache = {
                str(e.path): notes.read_note_head(e.note_path, NOTE_CACHE_BYTES).lower()
                for e in entries if e.note_path
            }
        except Exception as e:
            log.exception("后台扫描失败")
            self.failed.emit(str(e))
            return
        self.done.emit(categories, note_cache)


class MainWindow(QMainWindow):
    def __init__(self, app_dir: Path, settings: Settings):
        super().__init__()
        self.app_dir = Path(app_dir)
        self.settings = settings  # 全局唯一 Settings 实例，由 main.py 创建并共享
        self.db = DB(self.app_dir / "config" / "data.db")

        # ── 视图状态（reload/rebuild 都读这些） ──
        self.categories: list[Category] = []
        self.entries: list[Entry] = []
        self.nav = "all"
        self.tag: str | None = None
        self.query = ""
        self.view = self.settings.get("view", "grid")
        self.selected: Entry | None = None
        self._cards: dict[str, EntryCard] = {}   # path → 卡片，选中态同步用
        self._icons: dict[str, QIcon] = {}       # path → 系统图标，reload 时统一取
        self._note_cache: dict[str, str] = {}    # path → 笔记小写缓存，搜索用
        self._tray_quit = False                  # 托盘点了「退出」才置位，closeEvent 靠它放行
        self._reloading = False                  # reload 重入守卫，扫描中再按 F5 先记为 pending
        self._scans: list[tuple[QThread, _ScanWorker]] = []  # 持引用到线程结束，防 GC
        self._scan_workspace: Path | None = None  # 本次扫描对应的根目录（切工作区时判过期）
        self._reload_pending = False             # 扫描期间的请求，完成后补一次
        self._restore_path: str | None = None     # 自动重扫前记下选中项，扫完恢复

        self.workspace = self._resolve_workspace()

        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(make_logo_icon())
        # 无边框：原生「— □ X」换不掉，索性自绘 macOS 交通灯标题栏；
        # 边框缩放由下面的 nativeEvent 拦 WM_NCHITTEST 补回来
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        win = self.settings.get("window", DEFAULT_WINDOW_SIZE)
        self.resize(win.get("w", DEFAULT_WINDOW_SIZE["w"]),
                    win.get("h", DEFAULT_WINDOW_SIZE["h"]))
        self.setMinimumSize(1100, 680)
        self._restore_position(win)
        self._start_maximized = bool(win.get("maximized", False))  # 首次 show 时恢复

        self._build_topbar()
        self._build_central()
        self._build_statusbar()
        self._build_tray()
        self._build_shortcuts()
        self._build_ipc()
        self._build_watcher()

        QTimer.singleShot(0, self.reload)  # 先让窗口出来，扫描等事件循环跑起来再做

    def _restore_position(self, win: dict) -> None:
        """恢复上次窗口位置；显示器变化导致越界时忽略，交给系统摆放。"""
        x, y = win.get("x"), win.get("y")
        if x is None or y is None:
            return
        rect = QRect(int(x), int(y), self.width(), self.height())
        if any(s.availableGeometry().intersects(rect) for s in QGuiApplication.screens()):
            self.move(int(x), int(y))

    def _resolve_workspace(self) -> Path:
        """探测工作区根目录，探测不到就弹框问；用户取消就直接退出。"""
        root = self.settings.detect_workspace()
        if not root:
            root = QFileDialog.getExistingDirectory(
                self, "选择工作区根目录（工具/项目的父目录）")
            if not root:
                QMessageBox.critical(self, "无法启动", "未选择工作区目录")
                raise SystemExit(2)
            self.settings.set("workspace_root", root)
        return Path(root)

    # ── UI 搭建 ──
    def _build_topbar(self) -> None:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(54)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)

        brand = QLabel("SuperGUI")
        brand.setObjectName("Brand")
        lay.addWidget(brand)

        brand_sub = QLabel("网络安全工具箱")
        brand_sub.setObjectName("BrandSub")
        lay.addWidget(brand_sub)

        # 两个工作区快捷按钮：显示预设名（如「工具」），点击直达对应目录
        self._ws_btns: list[QPushButton] = []
        for i in range(len(self.settings.get_presets())):
            btn = QPushButton()
            btn.setObjectName("WorkspaceBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=i: self._switch_workspace_by_index(i))
            lay.addWidget(btn)
            self._ws_btns.append(btn)
        self._refresh_workspace_buttons()

        lay.addStretch(1)
        lay.addWidget(self._make_search_box(), 0)
        lay.addStretch(1)

        self._grid_btn = self._top_icon_btn(SVG_GRID, "网格视图", checkable=True)
        self._list_btn = self._top_icon_btn(SVG_LIST, "列表视图", checkable=True)
        self._grid_btn.setChecked(self.view == "grid")
        self._list_btn.setChecked(self.view == "list")
        self._grid_btn.clicked.connect(lambda: self._set_view("grid"))
        self._list_btn.clicked.connect(lambda: self._set_view("list"))
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_group.addButton(self._grid_btn)
        self._view_group.addButton(self._list_btn)
        lay.addWidget(self._grid_btn)
        lay.addWidget(self._list_btn)

        cur_theme = self.settings.get("theme", "light")
        self._theme_btn = self._top_icon_btn(
            SVG_SUN if cur_theme == "dark" else SVG_MOON, "切换主题")
        self._theme_btn.clicked.connect(self._toggle_theme)
        lay.addWidget(self._theme_btn)

        self._panel_btn = self._top_icon_btn(SVG_PANEL, "折叠/展开详情面板 (Ctrl+B)",
                                             checkable=True)
        self._panel_btn.setChecked(True)
        self._panel_btn.clicked.connect(self._toggle_panel)
        lay.addWidget(self._panel_btn)

        refresh_btn = self._top_icon_btn(SVG_REFRESH, "重新扫描 (F5)")
        refresh_btn.clicked.connect(self.reload)
        lay.addWidget(refresh_btn)

        set_btn = self._top_icon_btn(SVG_SETTINGS, "设置")
        set_btn.clicked.connect(self._show_settings)
        lay.addWidget(set_btn)

        self._topbar = bar  # 这个在 _build_central 里加到 central 顶部

    def _make_search_box(self) -> QWidget:
        """搜索框：150ms 防抖，停手了才触发重建。"""
        wrap = QWidget()
        wrap.setFixedWidth(430)
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        self._search = QLineEdit()
        self._search.setObjectName("SearchBar")
        self._search.setPlaceholderText("请输入关键词：工具 / 项目 / 标签 / 笔记        Ctrl+K")
        self._search.setClearButtonEnabled(True)
        self._search.addAction(svg_icon(SVG_SEARCH, ICON_COLOR),
                               QLineEdit.ActionPosition.LeadingPosition)
        self._search_timer = QTimer(self, singleShot=True, interval=150)
        self._search_timer.timeout.connect(self._apply_query)
        self._search.textChanged.connect(lambda _: self._search_timer.start())
        lay.addWidget(self._search)
        return wrap

    def _top_icon_btn(self, svg: str, tooltip: str, checkable: bool = False) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("TopIconBtn")
        btn.setIcon(svg_icon(svg, ICON_COLOR))
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(33, 33)
        return btn

    def _build_central(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._titlebar = self._make_titlebar(central)
        root.addWidget(self._titlebar)
        root.addWidget(self._topbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = SideBar()
        self._sidebar.navChanged.connect(self._on_nav)
        self._sidebar.tagChanged.connect(self._on_tag)
        body.addWidget(self._sidebar)

        body.addWidget(self._make_content(), 1)

        self._detail = DetailPanel()
        self._detail.launchRequested.connect(lambda e: self._launch(e, False))
        self._detail.openDirRequested.connect(lambda e: launcher.open_in_explorer(e.path))
        self._detail.pinToggled.connect(self._toggle_pin)
        self._detail.commandEdited.connect(self._edit_command)
        self._detail.tagsEdited.connect(self._edit_tags)
        self._detail.noteSaved.connect(self._on_note_saved)
        body.addWidget(self._detail)

        root.addLayout(body, 1)
        self.setCentralWidget(central)

    def _make_content(self) -> QFrame:
        """中间内容区：标题行 + 统计卡片 + 卡片滚动区。"""
        content = QFrame()
        content.setObjectName("Content")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(22, 16, 22, 10)
        lay.setSpacing(10)

        header = QHBoxLayout()
        self._title = QLabel("全部条目")
        self._title.setObjectName("ContentTitle")
        self._count_lbl = QLabel()
        self._count_lbl.setObjectName("ContentSub")
        header.addWidget(self._title)
        header.addWidget(self._count_lbl)
        header.addStretch(1)
        lay.addLayout(header)

        self._stats = StatsRow()
        lay.addWidget(self._stats)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("CardScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(self._scroll, 1)
        return content

    def _build_statusbar(self) -> None:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(16)

        self._status_ok = QLabel("● 就绪")
        self._status_ok.setObjectName("StatusOk")
        self._status_path = QLabel(str(self.workspace))
        self._status_path.setObjectName("StatusText")
        self._status_count = QLabel()
        self._status_count.setObjectName("StatusText")
        self._status_time = QLabel()
        self._status_time.setObjectName("StatusText")
        lay.addWidget(self._status_ok)
        lay.addWidget(self._status_path)
        lay.addStretch(1)
        lay.addWidget(self._status_count)
        lay.addWidget(self._status_time)

        self.centralWidget().layout().addWidget(bar)  # 加到 central 底部

        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)
        self._tick_clock()

    def _tick_clock(self) -> None:
        now = datetime.datetime.now()
        week = "一二三四五六日"[now.weekday()]
        self._status_time.setText(now.strftime(f"%Y-%m-%d %H:%M:%S 星期{week}"))

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(make_logo_icon(64))
        self._tray.setToolTip(f"SuperGUI v{__version__}")
        menu = QMenu()
        menu.addAction("显示主界面", self._show_from_tray)
        menu.addAction("重新扫描", self.reload)
        menu.addSeparator()
        menu.addAction("退出", self._quit_from_tray)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self._toggle_panel)
        QShortcut(QKeySequence("F5"), self, activated=self.reload)
        QShortcut(QKeySequence("Escape"), self, activated=self._clear_query)

    # ── 单实例唤起 & 目录监听 ──
    def _build_ipc(self) -> None:
        """单实例唤起通道：第二实例连进来 = 请求唤起主窗口。"""
        self._ipc = QLocalServer(self)
        self._ipc.newConnection.connect(self._on_ipc)
        if not self._ipc.listen(IPC_NAME):
            # 上次异常退出可能残留 socket 文件，清掉重听
            QLocalServer.removeServer(IPC_NAME)
            self._ipc.listen(IPC_NAME)

    def _on_ipc(self) -> None:
        """第二实例启动 = 用户明确要用：确保窗口显示并聚焦搜索框（不是 toggle，热键才是 toggle）。"""
        while self._ipc.hasPendingConnections():
            conn = self._ipc.nextPendingConnection()
            self._show_from_tray()
            self._focus_search()
            conn.disconnectFromServer()
            conn.deleteLater()

    def _build_watcher(self) -> None:
        """工作区目录监听：条目增删/改名后去抖 1s 自动重扫，免得解压工具包时刷爆。"""
        self._watcher = QFileSystemWatcher(self)
        self._watch_timer = QTimer(self, singleShot=True, interval=1000)
        self._watch_timer.timeout.connect(self._auto_reload)
        self._watcher.directoryChanged.connect(lambda _p: self._watch_timer.start())

    def _refresh_watcher(self) -> None:
        """重铺监听路径：根目录 + 当前所有分类目录（条目目录不监听，写笔记不会触发）。"""
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        self._watcher.addPaths(
            [str(self.workspace)] + [str(c.path) for c in self.categories])

    def _auto_reload(self) -> None:
        """目录变化触发的自动重扫：编辑笔记时跳过；重扫前记下选中项，扫完恢复。"""
        if self._detail.has_unsaved_note():
            self._set_status("有未保存的笔记，已跳过自动重扫", ok=False)
            return
        if self.selected:
            self._restore_path = str(self.selected.path)
        self.reload()

    # ── 数据流（扫描 → 合并 db → 重建） ──
    def reload(self) -> None:
        """后台重扫工作区，完成后合并 db 元数据并重建 UI（不阻塞主线程）。"""
        if self._reloading:
            self._reload_pending = True   # 扫描期间的请求，完成后补一次
            return
        if self._detail.has_unsaved_note() and not self._detail.confirm_leave():
            return
        self._reloading = True
        self._scan_workspace = self.workspace
        self._set_status("扫描中…", ok=False)

        worker = _ScanWorker(self.workspace)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_scan_done)
        worker.failed.connect(self._on_scan_failed)
        worker.done.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.done.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self._drop_scan(t))
        self._scans.append((thread, worker))
        thread.start()

    def _drop_scan(self, thread: QThread) -> None:
        self._scans = [pair for pair in self._scans if pair[0] is not thread]

    def _on_scan_done(self, categories: list[Category], note_cache: dict[str, str]) -> None:
        self._reloading = False
        if self._scan_workspace is not None \
                and not self._same_path(self._scan_workspace, self.workspace):
            # 扫描期间切了工作区：丢弃这次结果，按新工作区重扫
            self._scan_workspace = None
            self._reload_pending = False
            self.reload()
            return
        self._scan_workspace = None
        self.categories = categories
        self.entries = [e for c in categories for e in c.entries]
        self._note_cache = note_cache
        self._merge_db_meta()
        self._prune_stale_meta()
        self._build_icons()

        if self._detail.confirm_leave():
            self._detail.set_entry(None, None, {})
            self.selected = None
        else:
            # 扫描期间用户开始编辑笔记且选择继续编辑：保留选中项与编辑内容（卡片
            # 高亮按路径匹配不受影响）；pending 不再立即补扫，避免连环弹窗
            self._restore_path = None
            self._reload_pending = False

        self._rebuild_sidebar()
        self._rebuild_grid()
        self._set_status("就绪")
        self._status_path.setText(str(self.workspace))
        self._refresh_watcher()

        keep = self._restore_path
        self._restore_path = None
        if keep:
            entry = next((e for e in self.entries if str(e.path) == keep), None)
            if entry:
                self._on_select(entry)

        if self._reload_pending:
            self._reload_pending = False
            self.reload()

    def _on_scan_failed(self, msg: str) -> None:
        self._reloading = False
        self._scan_workspace = None
        log.error("重新扫描失败: %s", msg)
        self._set_status(f"扫描失败: {msg}", ok=False)
        if self._reload_pending:
            self._reload_pending = False
            QTimer.singleShot(0, self.reload)

    def _merge_db_meta(self) -> None:
        """把 db 里的元数据（固定/标签/自定义命令/参数记忆/统计）按路径合进扫描结果。"""
        metas = self.db.all_meta()
        stats = self.db.all_stats()
        for e in self.entries:
            key = str(e.path)
            if m := metas.get(key):
                e.pinned, e.tags = m["pinned"], m["tags"]
                e.command, e.shell_type = m["command"], m["shell_type"]
                e.last_args, e.admin = m["last_args"], m["admin"]
            if s := stats.get(key):
                e.runs, e.last_run = s["runs"], s["last_run"]

    def _prune_stale_meta(self) -> None:
        """清理已消失条目的元数据（仅在当前工作区内、父目录仍在时删）。"""
        try:
            removed = self.db.prune(self.workspace, {str(e.path) for e in self.entries})
        except Exception:
            log.exception("清理失效元数据失败")
            return
        if removed:
            log.info("已清理 %d 条失效元数据", removed)

    def _build_icons(self) -> None:
        """系统图标缓存：沿用上一轮的，只给新条目取图标（省 shell 查询）。"""
        old = self._icons
        provider = QFileIconProvider()
        self._icons = {
            str(e.path): old.get(str(e.path)) or provider.icon(QFileInfo(str(e.path)))
            for e in self.entries
        }

    def _rebuild_sidebar(self) -> None:
        entries = self.entries
        cats = [c for c in self.categories if c.entries]  # 空分类不显示
        self._sidebar.rebuild(
            cats, len(entries),
            star_count=sum(1 for e in entries if e.pinned),
            recent_count=sum(1 for e in entries if e.runs > 0),
            tags=sorted({t for e in entries for t in e.tags})
                 if self.settings.get("show_tags", False) else [])

    def _filtered(self) -> list[Entry]:
        """当前视图状态（nav/tag/query）下的条目列表。

        常规视图已固定优先、按名称排序；「最近使用」按时间倒序
        （固定项不特别置顶，否则就失去「最近」语义）。
        """
        items = self.entries
        if self.nav == "star":
            items = [e for e in items if e.pinned]
        elif self.nav == "recent":
            items = [e for e in items if e.runs > 0]
        elif self.nav != "all":
            items = [e for e in items if e.cat_id == self.nav]
        if self.tag:
            items = [e for e in items if self.tag in e.tags]
        if self.query:
            items = [e for e in items if self._matches(e, self.query.lower())]
        if self.nav == "recent":
            return sorted(items, key=lambda e: e.last_run, reverse=True)
        return sorted(items, key=lambda e: (not e.pinned, e.name.lower()))

    def _matches(self, e: Entry, q: str) -> bool:
        """搜索命中：名称 / 路径 / 标签 / 笔记缓存，都已转小写。"""
        return (q in e.name.lower()
                or q in str(e.path).lower()
                or any(q in t.lower() for t in e.tags)
                or q in self._note_cache.get(str(e.path), ""))

    def _current_title(self) -> str:
        if self.tag:
            return f"#{self.tag}"
        cat = next((c for c in self.categories if c.cat_id == self.nav), None)
        return cat.name if cat else NAV_TITLES.get(self.nav, "全部条目")

    def _rebuild_grid(self) -> None:
        items = self._filtered()
        self._title.setText(self._current_title())
        self._count_lbl.setText(f"{len(items)} 个条目")
        self._status_count.setText(
            f"共 {len(self.entries)} 项 · 显示 {len(items)} 项")

        # 统计卡片只在「全部条目」无筛选时出现
        show_stats = self.nav == "all" and not self.tag and not self.query
        self._stats.setVisible(show_stats)
        if show_stats:
            entries = self.entries
            self._stats.set_stats(
                sum(1 for e in entries if e.entry_type == TYPE_TOOL),
                sum(1 for e in entries if e.entry_type != TYPE_TOOL),
                sum(1 for e in entries if e.pinned))

        container = QWidget()
        container.setObjectName("CardContainer")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(18)
        self._cards = {}

        if not items:
            empty = QLabel("🔍  没有匹配的条目\n换个关键词或清除筛选试试")
            empty.setObjectName("EmptyTip")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(empty)
        elif self.view == "list":
            for e in items:
                outer.addWidget(self._make_card(e, list_mode=True))
        elif show_stats:
            # 默认主页：按分类分组的网格视图
            for cat in self.categories:
                group = [e for e in items if e.cat_id == cat.cat_id]
                if not group:
                    continue
                head = QLabel(f"{cat.name}   {len(group)}")
                head.setObjectName("CatHead")
                outer.addWidget(head)
                self._fill_flow(outer, group)
        else:
            self._fill_flow(outer, items)
        outer.addStretch(1)

        # 整体替换滚动区内容，旧容器延迟销毁
        old = self._scroll.takeWidget()
        if old:
            old.deleteLater()
        self._scroll.setWidget(container)

    def _fill_flow(self, outer: QVBoxLayout, entries: list[Entry]) -> None:
        """往 outer 里追加一段流式网格卡片区。"""
        wrap = QWidget()
        flow = FlowLayout(wrap, margin=0, h_spacing=12, v_spacing=12)
        for e in entries:
            flow.addWidget(self._make_card(e))
        outer.addWidget(wrap)

    def _make_card(self, entry: Entry, list_mode: bool = False) -> EntryCard:
        icon = self._icons.get(str(entry.path)) or self.style().standardIcon(
            QStyle.StandardPixmap.SP_FileIcon)
        card = EntryCard(entry, icon, list_mode=list_mode)
        card.set_selected(self.selected is not None and entry.path == self.selected.path)
        card.clicked.connect(self._on_select)
        card.doubleClicked.connect(lambda e: self._launch(e, False))
        card.contextRequested.connect(self._show_context)
        self._cards[str(entry.path)] = card
        return card

    # ── 交互 ──
    def _on_nav(self, key: str) -> None:
        self.nav = key
        self.tag = None  # 导航和标签互斥，切导航时清掉标签筛选
        self._rebuild_grid()

    def _on_tag(self, tag: str | None) -> None:
        self.tag = tag
        if tag:
            self.nav = "all"
        self._rebuild_grid()

    def _apply_query(self) -> None:
        self.query = self._search.text().strip()
        self._rebuild_grid()

    def _clear_query(self) -> None:
        self._search.clear()
        self.query = ""
        self._rebuild_grid()

    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def _on_select(self, entry: Entry) -> None:
        if self.selected is not None and entry is not self.selected \
                and not self._detail.confirm_leave():
            return  # 用户取消：保持原选中，不吃掉未保存的笔记
        prev = self.selected
        self.selected = entry
        # 只刷新新旧两张卡片，不全量 unpolish/polish
        if prev is not None and prev.path != entry.path:
            old_card = self._cards.get(str(prev.path))
            if old_card:
                old_card.set_selected(False)
        card = self._cards.get(str(entry.path))
        if card:
            card.set_selected(True)
        stats = self.db.get_stats(entry.path)
        self._detail.set_entry(entry, self._icons.get(str(entry.path)), stats)
        self._status_path.setText(str(entry.path))

    def _launch(self, entry: Entry, admin: bool, args: str = "") -> None:
        try:
            # admin 记忆生效：右键点了「启动」也会按记忆提权
            msg = launcher.launch(entry, command=entry.command,
                                  shell_type=entry.shell_type,
                                  admin=admin or entry.admin, args=args)
        except RuntimeError as e:
            self._set_status(f"启动失败: {e}", ok=False)
            QMessageBox.warning(self, "启动失败", str(e))
            return
        self.db.record_run(entry.path)
        entry.runs += 1
        entry.last_run = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._set_status(msg)
        self._status_path.setText(str(entry.path))
        self._on_select(entry)  # 顺便刷新详情面板的统计

    def _show_context(self, entry: Entry, pos: QPoint) -> None:
        self._on_select(entry)
        menu = QMenu(self)
        menu.addAction("▶  启动", lambda: self._launch(entry, False))
        menu.addAction("💬  带参数启动…", lambda: self._launch_with_args(entry))
        menu.addAction("🛡  以管理员启动", lambda: self._launch(entry, True))
        always_admin = menu.addAction("🛡  总是以管理员启动")
        always_admin.setCheckable(True)
        always_admin.setChecked(entry.admin)
        always_admin.triggered.connect(lambda checked: self._toggle_admin(entry, checked))
        menu.addAction("📂  打开目录", lambda: launcher.open_in_explorer(entry.path))
        menu.addSeparator()
        menu.addAction("📋  复制路径",
                       lambda: QGuiApplication.clipboard().setText(str(entry.path)))
        menu.addAction("★  取消固定" if entry.pinned else "★  固定到顶部",
                       lambda: self._toggle_pin(entry, not entry.pinned))
        menu.addAction("✏  编辑启动命令", lambda: self._popup_command(entry))
        menu.exec(pos)

    def _launch_with_args(self, entry: Entry) -> None:
        """弹框输入本次启动的追加参数；参数记住后下次回填。

        渗透工具换目标是最高频动作，参数对自定义命令和主程序都生效。
        """
        args, ok = QInputDialog.getText(
            self, f"带参数启动 · {entry.name}",
            "追加参数（自定义命令 / 主程序都会带上）：", text=entry.last_args)
        if not ok:
            return
        args = args.strip()
        self.db.set_last_args(entry.path, args)
        entry.last_args = args
        self._launch(entry, False, args=args)

    def _toggle_admin(self, entry: Entry, admin: bool) -> None:
        self.db.set_admin(entry.path, admin)
        entry.admin = admin
        self._set_status(
            ("已记住管理员启动: " if admin else "已取消管理员启动: ") + entry.name)

    def _popup_command(self, entry: Entry) -> None:
        dlg = CommandDialog(entry.command or "", entry.shell_type, self)
        if dlg.exec():
            cmd, shell = dlg.result()
            self._edit_command(entry, cmd, shell)

    def _toggle_pin(self, entry: Entry, pinned: bool) -> None:
        self.db.set_pinned(entry.path, pinned)
        entry.pinned = pinned
        self._rebuild_sidebar()
        self._rebuild_grid()
        self._on_select(entry)   # 详情面板的按钮文案要跟着变
        self._set_status(("已固定: " if pinned else "取消固定: ") + entry.name)

    def _edit_command(self, entry: Entry, command: str, shell_type: str) -> None:
        self.db.set_command(entry.path, command, shell_type)
        entry.command, entry.shell_type = command or None, shell_type
        self._set_status(f"已保存启动命令: {entry.name}")
        if self.selected and entry.path == self.selected.path:
            self._on_select(entry)

    def _edit_tags(self, entry: Entry, tags: list[str]) -> None:
        self.db.set_tags(entry.path, tags)
        entry.tags = tags
        self._rebuild_sidebar()
        self._on_select(entry)
        self._set_status(f"已更新标签: {entry.name}")

    def _on_note_saved(self, entry: Entry) -> None:
        # 笔记首行作为卡片摘要；同步刷新搜索缓存和卡片文字
        entry.desc = notes.note_excerpt(entry.note_path) or f"{entry.cat_name} / {entry.name}"
        if entry.note_path:
            self._note_cache[str(entry.path)] = \
                notes.read_note_head(entry.note_path, NOTE_CACHE_BYTES).lower()
        card = self._cards.get(str(entry.path))
        if card:
            card.set_desc(entry.desc)
        self._set_status(f"笔记已保存: {entry.name}")

    def _change_workspace(self) -> None:
        root = QFileDialog.getExistingDirectory(
            self, "选择工作区根目录", str(self.workspace))
        if root:
            self._switch_workspace(Path(root))

    @staticmethod
    def _same_path(a, b) -> bool:
        """Windows 路径比较：归一化分隔符并忽略大小写。"""
        return os.path.normcase(os.path.normpath(str(a))) == \
               os.path.normcase(os.path.normpath(str(b)))

    def _switch_workspace_by_index(self, i: int) -> None:
        """顶栏预设按钮点击直达：按序号取当前预设（设置里改过也能拿到最新值）。"""
        self._switch_workspace(Path(self.settings.get_presets()[i]["path"]))

    def _switch_workspace(self, root: Path) -> None:
        """切换到指定工作区；换工作区后筛选状态全部重置。"""
        if self._same_path(root, self.workspace):
            return
        if not root.is_dir():
            self._set_status(f"工作区不存在: {root}", ok=False)
            return
        if self._detail.has_unsaved_note() and not self._detail.confirm_leave():
            return  # 取消切换，别把编辑中的笔记带丢
        self.workspace = root
        self.settings.set("workspace_root", str(root))
        self.nav, self.tag, self.query = "all", None, ""
        self._search.clear()
        self._sidebar.set_current("all")
        self._refresh_workspace_buttons()
        self.reload()

    def _refresh_workspace_buttons(self) -> None:
        """按 settings 里的预设刷新顶栏按钮的名称/路径提示/当前激活态。"""
        for i, btn in enumerate(self._ws_btns):
            preset = self.settings.get_presets()[i]
            btn.setText(f"📁  {preset['name']}")
            btn.setToolTip(f"{preset['path']}\n点击切换到该工作区")
            active = self._same_path(preset["path"], self.workspace)
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)  # 动态属性要刷新样式
            btn.style().polish(btn)

    def _set_view(self, view: str) -> None:
        self.view = view
        self.settings.set("view", view)
        # 设置对话框也能改视图，顶栏切换按钮的选中态要同步
        self._grid_btn.setChecked(view == "grid")
        self._list_btn.setChecked(view == "list")
        self._rebuild_grid()

    def _set_show_tags(self, show: bool) -> None:
        """侧栏标签云显隐（设置对话框）。隐藏时清掉进行中的标签筛选。"""
        self.settings.set("show_tags", show)
        if not show and self.tag is not None:
            self.tag = None
            self._rebuild_grid()
        self._rebuild_sidebar()

    def _apply_theme(self, theme: str) -> None:
        self.settings.set("theme", theme)
        apply_theme(QApplication.instance(), self.app_dir, theme)
        self._theme_btn.setIcon(svg_icon(SVG_SUN if theme == "dark" else SVG_MOON, ICON_COLOR))

    def _toggle_theme(self) -> None:
        self._apply_theme("dark" if self.settings.get("theme") == "light" else "light")

    def _toggle_panel(self) -> None:
        visible = not self._detail.isVisible()
        self._detail.setVisible(visible)
        self._panel_btn.setChecked(visible)

    def _make_titlebar(self, central: QWidget) -> QWidget:
        """按 settings 的 titlebar 风格创建标题栏（macos | windows）。"""
        cls = TITLEBARS.get(self.settings.get("titlebar", "macos"), TitleBar)
        return cls("Super系列工具—BY:Super403开发", central)

    def _set_titlebar_style(self, style: str) -> None:
        """切换标题栏风格：热替换 central 顶部的旧标题栏，立即生效。"""
        self.settings.set("titlebar", style)
        lay = self.centralWidget().layout()
        lay.removeWidget(self._titlebar)
        self._titlebar.deleteLater()
        self._titlebar = self._make_titlebar(self.centralWidget())
        lay.insertWidget(0, self._titlebar)

    def _show_settings(self) -> None:
        """设置对话框：外观 / 工作区 / 热键 / 数据位置，widgets 只发信号。"""
        dlg = SettingsDialog(self.app_dir, self.settings, self)
        dlg.themeChanged.connect(self._apply_theme)
        dlg.titleBarChanged.connect(self._set_titlebar_style)
        dlg.viewChanged.connect(self._set_view)
        dlg.tagCloudChanged.connect(self._set_show_tags)
        dlg.hotkeyChanged.connect(lambda text: self.settings.set("hotkey", text))
        dlg.windowSizeChanged.connect(self._set_window_size)
        dlg.workspaceChangeRequested.connect(
            lambda: (self._change_workspace(), dlg.refresh_workspace()))
        dlg.presetsChanged.connect(self._on_presets_changed)
        dlg.exec()

    def _on_presets_changed(self, presets: list) -> None:
        """设置里改了工作区预设：落盘 + 立即刷新顶栏按钮。"""
        self.settings.set_presets(presets)
        self._refresh_workspace_buttons()

    def _set_window_size(self, w: int, h: int) -> None:
        """应用设置里的界面尺寸：写 settings + 立即 resize（受最小尺寸钳制）。"""
        win = dict(self.settings.get("window", DEFAULT_WINDOW_SIZE))
        win.update({"w": w, "h": h})   # 合并写入，别把已记住的 x/y 抹掉
        self.settings.set("window", win)
        self.resize(w, h)

    # ── 托盘与窗口 ──
    def _show_from_tray(self) -> None:
        # 最小化过才 showNormal；只是隐藏的窗口用 show()，保住最大化和尺寸状态
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_from_tray()

    def _quit_from_tray(self) -> None:
        self._tray_quit = True
        # 走 close() 而不是直接 quit()：保证 closeEvent 里的保存尺寸、关库、
        # 等后台扫描、笔记未保存询问都会执行；用户取消时不退出
        if self.close():
            QApplication.quit()
        else:
            self._tray_quit = False

    def _stop_scan(self) -> None:
        """退出前等后台扫描收尾，避免 QThread 运行中被销毁。"""
        for thread, _worker in list(self._scans):
            thread.quit()
        for thread, _worker in list(self._scans):
            thread.wait()

    def toggle_visibility(self) -> None:
        """全局热键 / 第二实例唤起：显示时顺便聚焦搜索框，直接打字即搜。"""
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._show_from_tray()
            self._focus_search()

    def nativeEvent(self, eventType, message) -> tuple[bool, int]:
        """无边框窗口没有边框缩放，拦 WM_NCHITTEST 把四边四角报给 Windows，
        缩放、阴影光标、Win11 贴靠布局就全回来了。最大化时跳过（边框在屏幕外）。"""
        if eventType == b"windows_generic_MSG" and not self.isMaximized():
            msg = MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                hit = self._border_hit(self.mapFromGlobal(QPoint(x, y)))
                if hit:
                    return True, hit
        return super().nativeEvent(eventType, message)

    def _border_hit(self, pos: QPoint) -> int:
        """窗口内坐标 → 边框命中码，不在边上返回 0。"""
        m, w, h = RESIZE_MARGIN, self.width(), self.height()
        left, right = 0 <= pos.x() < m, w - m <= pos.x() < w
        top, bottom = 0 <= pos.y() < m, h - m <= pos.y() < h
        if top and left:
            return HT_TOPLEFT
        if top and right:
            return HT_TOPRIGHT
        if bottom and left:
            return HT_BOTTOMLEFT
        if bottom and right:
            return HT_BOTTOMRIGHT
        if left:
            return HT_LEFT
        if right:
            return HT_RIGHT
        if top:
            return HT_TOP
        if bottom:
            return HT_BOTTOM
        return 0

    def showEvent(self, event) -> None:
        """首次显示时恢复上次的最大化状态（window.maximized）。"""
        super().showEvent(event)
        if self._start_maximized:
            self._start_maximized = False
            self.showMaximized()

    def closeEvent(self, e: QCloseEvent) -> None:
        # 托盘还开着的话，关窗只最小化到托盘；真正退出只能走托盘菜单「退出」
        if self._tray_quit or not self._tray.isVisible():
            if self._detail.has_unsaved_note() and not self._detail.confirm_leave():
                e.ignore()
                return
            self._stop_scan()
            geo = self.normalGeometry() if self.isMaximized() else self.geometry()
            self.settings.set("window", {"w": geo.width(), "h": geo.height(),
                                         "x": geo.x(), "y": geo.y(),
                                         "maximized": self.isMaximized()})
            self.db.close()
            super().closeEvent(e)
            return
        e.ignore()
        self.hide()
        hotkey = self.settings.get("hotkey", "Alt+Space")
        self._tray.showMessage("SuperGUI", f"已最小化到托盘，{hotkey} 可唤起",
                               QSystemTrayIcon.MessageIcon.Information, 2000)

    def _set_status(self, text: str, ok: bool = True) -> None:
        self._status_ok.setText(("● " if ok else "✕ ") + text)
        self._status_ok.setStyleSheet("" if ok else "color: #f0524f;")


def apply_theme(app: QApplication, app_dir: Path, theme: str) -> None:
    """加载 ui/themes/<theme>.qss；文件没了只记日志，不影响启动。"""
    qss_path = app_dir / "ui" / "themes" / f"{theme}.qss"
    try:
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    except OSError as e:
        log.error("加载主题失败 %s: %s", qss_path, e)
