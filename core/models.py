"""数据模型：分类与条目。core 层不依赖任何 UI 库。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 分类目录前缀：A- 或 A-01- 形式，显示时剥离
PREFIX_RE = re.compile(r"^[A-Za-z]-(?:\d+-)?")

# 条目类型
TYPE_TOOL = "tool"        # 工具目录（含可执行程序）
TYPE_DIR = "dir"          # 纯目录（资料/字典等）
TYPE_FILE = "file"        # 单文件

DEFAULT_SHELL = "cmd"     # 自定义命令的默认运行方式，全局唯一出处


def strip_prefix(dirname: str) -> str:
    """剥离分类目录名前缀：'B-01-资产发现' -> '资产发现'"""
    stripped = PREFIX_RE.sub("", dirname)
    return stripped or dirname


@dataclass
class Entry:
    """一个条目：工具目录 / 资料目录 / 单文件"""
    name: str               # 显示名（目录名/文件名）
    path: Path              # 绝对路径
    cat_id: str             # 所属分类目录原始名
    cat_name: str           # 所属分类显示名
    is_dir: bool
    entry_type: str = TYPE_TOOL
    desc: str = ""          # 摘要（笔记首行 或 相对路径）
    note_path: Path | None = None   # 实际使用的笔记文件路径

    # 运行时附加数据（来自 db，不进扫描逻辑）
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    command: str | None = None    # 自定义启动命令（None = 默认启发式）
    shell_type: str = DEFAULT_SHELL  # 自定义命令的运行方式：cmd | powershell
    last_args: str = ""           # 上次「带参数启动」用的参数，弹框回填用
    admin: bool = False           # 总是以管理员身份启动
    runs: int = 0
    last_run: str = ""


@dataclass
class Category:
    """一个分类：根目录下的一级目录"""
    cat_id: str             # 原始目录名（如 B-01-资产发现）
    name: str               # 显示名（如 资产发现）
    path: Path
    entries: list[Entry] = field(default_factory=list)
