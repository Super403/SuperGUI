"""目录扫描器：把工作区根目录扫描成 分类 -> 条目 的结构。

约定：
- 根目录下每个一级子目录 = 一个分类（排除隐藏目录）
- 分类目录下的每个子目录/文件 = 一个条目
- 笔记文件名与摘要逻辑统一在 core/notes.py
"""
from __future__ import annotations

import logging
from pathlib import Path

from .models import TYPE_DIR, TYPE_FILE, TYPE_TOOL, Category, Entry, strip_prefix
from .notes import find_note, note_excerpt

log = logging.getLogger(__name__)

# 分类目录直属的笔记/系统文件不作为条目
SKIP_FILE_NAMES = {"00.txt", "note.md", "desktop.ini", "thumbs.db", ".ds_store"}


def _entry_type(path: Path, is_dir: bool) -> str:
    if not is_dir:
        return TYPE_FILE
    # 目录里含 exe/bat/lnk 视为工具，否则为资料目录
    try:
        for child in path.iterdir():
            if child.suffix.lower() in (".exe", ".bat", ".cmd", ".lnk", ".ps1"):
                return TYPE_TOOL
    except OSError:
        pass
    return TYPE_DIR


def scan(root: Path) -> list[Category]:
    """扫描根目录，返回分类列表（按目录名排序，条目按名称排序）。"""
    root = Path(root)
    if not root.is_dir():
        log.error("工作区根目录不存在: %s", root)
        return []

    categories: list[Category] = []
    try:
        cat_dirs = sorted(
            (p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: p.name.lower(),
        )
    except OSError as e:
        log.error("扫描根目录失败: %s", e)
        return []

    for cat_dir in cat_dirs:
        cat = Category(cat_id=cat_dir.name, name=strip_prefix(cat_dir.name), path=cat_dir)
        try:
            children = sorted(
                (p for p in cat_dir.iterdir() if not p.name.startswith(".")),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            children = []

        for child in children:
            is_dir = child.is_dir()
            if not is_dir and child.name.lower() in SKIP_FILE_NAMES:
                continue
            note_path = find_note(child) if is_dir else None
            entry = Entry(
                name=child.name,
                path=child,
                cat_id=cat.cat_id,
                cat_name=cat.name,
                is_dir=is_dir,
                entry_type=_entry_type(child, is_dir),
                note_path=note_path,
            )
            entry.desc = note_excerpt(note_path) or f"{cat.name} / {child.name}"
            cat.entries.append(entry)

        categories.append(cat)

    log.info("扫描完成: %d 个分类, %d 个条目",
             len(categories), sum(len(c.entries) for c in categories))
    return categories
