"""笔记读写：NOTE.md 优先，兼容旧版 00.txt。

笔记文件名约定与摘要提取的唯一权威来源，scanner / ui 都从这里拿。
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{name}"

NOTE_NAMES = ("NOTE.md", "00.txt")   # 按优先级排列
NOTE_PREVIEW_LEN = 300               # 摘要只读前 300 字节


def find_note(entry_path: Path) -> Path | None:
    """在条目目录里找笔记文件：NOTE.md 优先，00.txt 兜底。"""
    for name in NOTE_NAMES:
        p = entry_path / name
        if p.is_file():
            return p
    return None


def note_excerpt(note_path: Path | None) -> str:
    """取笔记第一行有效文本做摘要，失败返回空串。"""
    if not note_path:
        return ""
    try:
        with open(note_path, encoding="utf-8", errors="ignore") as f:
            text = f.read(NOTE_PREVIEW_LEN)
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not line.startswith("---"):
            return line[:40]
    return ""


def read_note(note_path: Path | None) -> str:
    if not note_path or not note_path.is_file():
        return ""
    try:
        return note_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        log.error("读取笔记失败 %s: %s", note_path, e)
        return ""


def read_note_head(note_path: Path | None, max_bytes: int = NOTE_PREVIEW_LEN) -> str:
    """按字节读笔记开头 max_bytes（搜索缓存用），避免大笔记每次全量读入。"""
    if not note_path or not note_path.is_file():
        return ""
    try:
        with open(note_path, "rb") as f:
            raw = f.read(max_bytes)
    except OSError as e:
        log.error("读取笔记失败 %s: %s", note_path, e)
        return ""
    # 截断可能落在多字节字符中间，errors=ignore 丢弃残字节即可
    return raw.decode("utf-8", errors="ignore")


def ensure_note(entry_path: Path, name: str) -> Path:
    """返回条目对应的笔记路径；不存在则按模板创建 NOTE.md。"""
    note_path = entry_path / "NOTE.md"
    legacy = entry_path / "00.txt"
    if legacy.is_file() and not note_path.is_file():
        return legacy  # 沿用旧文件，不重复创建
    if not note_path.is_file():
        content = DEFAULT_TEMPLATE.format(
            name=name, time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        try:
            note_path.write_text(content, encoding="utf-8")
        except OSError as e:
            log.error("创建笔记失败 %s: %s", note_path, e)
    return note_path


def save_note(note_path: Path, content: str) -> bool:
    try:
        note_path.write_text(content, encoding="utf-8")
        return True
    except OSError as e:
        log.error("保存笔记失败 %s: %s", note_path, e)
        return False
