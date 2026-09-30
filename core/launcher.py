"""启动器：按优先级执行条目。

优先级：db 自定义命令 > 目录内主程序启发式 > 打开目录。
支持 cmd / powershell / 直接运行 / 管理员提权 / 追加参数。
"""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
from pathlib import Path

from .models import DEFAULT_SHELL, Entry

log = logging.getLogger(__name__)

EXCLUDE_EXE_HINTS = ("uninstall", "unins", "卸载", "setup", "update")


def find_main_exe(folder: Path) -> Path | None:
    """在目录里找主程序：同名 exe > 唯一候选 exe > None（交给打开目录）。"""
    try:
        exes = [p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() == ".exe"
                and not any(h in p.name.lower() for h in EXCLUDE_EXE_HINTS)]
    except OSError:
        return None
    if not exes:
        return None
    same_name = [e for e in exes if e.stem.lower() == folder.name.lower()]
    if same_name:
        return same_name[0]
    if len(exes) == 1:
        return exes[0]
    return None


def _run_custom(shell_type: str, command: str, cwd: Path) -> None:
    # CREATE_NEW_CONSOLE 自己就能开新窗口，不用套 start（start 跟引号会打架）
    if shell_type == "powershell":
        subprocess.Popen(f"powershell -NoExit -Command {command}",
                         cwd=str(cwd),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:  # cmd /k 后面的内容原样交给 cmd 解析，命令里带引号也没事
        subprocess.Popen(f"cmd /k {command}",
                         cwd=str(cwd),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)


def _shell_execute_w(verb: str, file: str, args: str | None, cwd: Path) -> None:
    """ShellExecuteW 启动；返回值 ≤32 就是错误码，不抛异常。"""
    ret = ctypes.windll.shell32.ShellExecuteW(None, verb, file, args, str(cwd), 1)
    if ret <= 32:
        raise RuntimeError(f"启动失败（错误码 {ret}）")


def _run_as_admin(file: str, args: str | None, cwd: Path) -> None:
    """runas 提权启动。"""
    _shell_execute_w("runas", file, args, cwd)


def _shell_execute(path: Path, admin: bool, cwd: Path, args: str | None = None) -> None:
    if admin:
        _run_as_admin(str(path), args, cwd)
    else:
        # 统一走 ShellExecuteW：无参/带参启动共用同一个工作目录与错误码
        _shell_execute_w("open", str(path), args, cwd)


def launch(entry: Entry, command: str | None = None,
           shell_type: str = DEFAULT_SHELL, admin: bool = False, args: str = "") -> str:
    """启动条目，返回用于状态栏展示的动作描述。抛 RuntimeError 表示失败。

    args：追加参数，对自定义命令和主程序/文件都生效；纯目录直开忽略。
    """
    path = entry.path
    if not path.exists():
        raise RuntimeError(f"路径不存在: {path}")

    cwd = path if entry.is_dir else path.parent
    arg_text = args.strip()
    suffix = f" {arg_text}" if arg_text else ""

    if command:
        full = command + suffix
        if admin:
            # 提权也要按配置的运行方式走，别把 PowerShell 命令塞给 cmd
            if shell_type == "powershell":
                _run_as_admin("powershell.exe", f"-NoExit -Command {full}", cwd)
            else:
                _run_as_admin("cmd.exe", f"/k {full}", cwd)
        else:
            _run_custom(shell_type, full, cwd)
        log.info("自定义命令启动 %s: %s", entry.name, full)
        return f"已执行命令: {entry.name}{suffix}"

    if entry.is_dir:
        exe = find_main_exe(path)
        if exe:
            _shell_execute(exe, admin, cwd, arg_text or None)
            log.info("启动主程序 %s -> %s%s", entry.name, exe.name, suffix)
            return f"已启动: {exe.name}{suffix}"
        _shell_execute(path, False, cwd)
        return f"已打开目录: {entry.name}"

    _shell_execute(path, admin, cwd, arg_text or None)
    return f"已打开: {entry.name}{suffix}"


def open_in_explorer(path: Path) -> None:
    """在资源管理器中打开（文件则定位到它）。"""
    if path.is_dir():
        os.startfile(str(path))
    else:
        subprocess.Popen(f'explorer /select,"{path}"')
