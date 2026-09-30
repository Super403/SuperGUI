"""SuperGUI 入口：单实例锁、第二实例唤起、全局热键（默认 Alt+Space）、主题加载、主窗口。"""
from __future__ import annotations

import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QLockFile, QStandardPaths
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from config.settings import Settings
from core.hotkey import parse_hotkey
from core.version import __version__
from ui.main_window import IPC_NAME, MSG, MainWindow, apply_theme

APP_DIR = Path(__file__).resolve().parent
LOCK_FILE_NAME = "supergui.lock"

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    """日志落盘到应用根目录 app.log：1MB 一卷留 3 卷，不再无限涨。"""
    handler = RotatingFileHandler(
        APP_DIR / "app.log", maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[handler],
    )


# ── 全局热键：Win32 RegisterHotKey + Qt 原生事件过滤 ──────────────────────

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1  # 本进程内唯一的热键标识
# 热键字符串解析在 core.hotkey（ui 设置对话框也用它校验输入）


class HotkeyFilter(QAbstractNativeEventFilter):
    """拦截 WM_HOTKEY 并触发回调；注意实例必须存活到 app 退出，不能交给 GC。"""

    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message) -> tuple[bool, int]:
        if event_type != b"windows_generic_MSG":
            return False, 0
        try:
            msg = MSG.from_address(int(message))
        except (ValueError, TypeError):
            return False, 0
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            self._callback()
            return True, 0
        return False, 0


# ── 启动流程 ──────────────────────────────────────────────────────────────

def _acquire_instance_lock() -> QLockFile | None:
    """抢单实例锁（temp 目录），已被占用则返回 None。锁对象须由调用方持有到退出。"""
    temp_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    lock = QLockFile(temp_dir + "/" + LOCK_FILE_NAME)
    return lock if lock.tryLock(100) else None


def _notify_running_instance() -> bool:
    """已有实例在跑：通过本地 socket 让它唤起主窗口。成功送达返回 True。"""
    sock = QLocalSocket()
    sock.connectToServer(IPC_NAME)
    if not sock.waitForConnected(300):
        return False
    sock.write(b"raise")
    sock.flush()
    sock.waitForBytesWritten(300)
    return True


def _register_hotkey(app: QApplication, win: MainWindow, text: str) -> bool:
    """按 settings 里的热键描述注册全局热键；失败返回 False，由调用方提示用户。"""
    parsed = parse_hotkey(text)
    if not parsed:
        log.warning("全局热键 %s 解析失败", text)
        return False
    if not ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, parsed[0] | MOD_NOREPEAT, parsed[1]):
        log.warning("全局热键 %s 注册失败（已被其他程序占用？）", text)
        return False

    hotkey_filter = HotkeyFilter(win.toggle_visibility)
    app.installNativeEventFilter(hotkey_filter)
    # 挂到 app 上防 GC：installNativeEventFilter 不持有 Python 引用
    app._hotkey_filter = hotkey_filter
    app.aboutToQuit.connect(lambda: ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID))
    log.info("全局热键 %s 已注册", text)
    return True


def main() -> int:
    _setup_logging()
    log.info("SuperGUI v%s 启动", __version__)

    app = QApplication(sys.argv)
    app.setApplicationName("SuperGUI")
    app.setQuitOnLastWindowClosed(False)  # 关窗不退出，走托盘

    lock = _acquire_instance_lock()
    if lock is None:
        if _notify_running_instance():
            print("SuperGUI 已在运行，已唤起主窗口")
        else:
            print("SuperGUI 已在运行，但唤起失败")
            QMessageBox.warning(
                None, "SuperGUI 已在运行",
                "检测到 SuperGUI 已在运行，但无法唤起它的主窗口。\n"
                "请查看任务栏 / 系统托盘；若程序已无响应，可先在任务管理器中"
                "结束 SuperGUI，再重新启动。")
        return 0

    settings = Settings(APP_DIR / "config" / "config.yaml")
    apply_theme(app, APP_DIR, settings.get("theme", "light"))

    win = MainWindow(APP_DIR, settings)
    win.show()

    hotkey = settings.get("hotkey", "Alt+Space")
    if not _register_hotkey(app, win, hotkey):
        QMessageBox.warning(
            win, "全局热键不可用",
            f"热键「{hotkey}」注册失败：可能已被其他程序占用，或格式不受支持。\n"
            "可在 设置 → 全局热键 中更换（重启后生效）。")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
