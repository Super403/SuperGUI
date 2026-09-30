"""SQLite 元数据库：固定 / 标签 / 自定义命令 / 启动统计。

只存元数据，真实数据（工具、笔记）始终在文件系统里，保证便携性。
"""
from __future__ import annotations

import datetime
import logging
import sqlite3
from pathlib import Path

from core.models import DEFAULT_SHELL

log = logging.getLogger(__name__)

SCHEMA_VERSION = 3

# 版本号 → 升到该版本要执行的 SQL；以后改表结构就追加 4、5……，别动旧条目
MIGRATIONS = {
    # v1：初始表结构
    1: """
    CREATE TABLE IF NOT EXISTS meta(
        path        TEXT PRIMARY KEY,
        pinned      INTEGER DEFAULT 0,
        tags        TEXT    DEFAULT '',
        hidden      INTEGER DEFAULT 0,
        command     TEXT,
        shell_type  TEXT
    );
    CREATE TABLE IF NOT EXISTS stats(
        path        TEXT PRIMARY KEY,
        runs        INTEGER DEFAULT 0,
        last_run    TEXT
    );
    """,
    # v2：「移出面板」功能下线，删掉 hidden 列（需要 SQLite ≥ 3.35，Python 3.14 自带足够新）
    2: "ALTER TABLE meta DROP COLUMN hidden",
    # v3：「带参数启动」记住上次参数、「总是以管理员启动」记忆
    3: """
    ALTER TABLE meta ADD COLUMN last_args TEXT;
    ALTER TABLE meta ADD COLUMN admin INTEGER DEFAULT 0;
    """,
}


class DB:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        """按 user_version 逐级执行迁移脚本，新库从 0 升到最新。"""
        v = self._conn.execute("PRAGMA user_version").fetchone()[0]
        while v < SCHEMA_VERSION:
            v += 1
            self._conn.executescript(MIGRATIONS[v])
            self._conn.execute(f"PRAGMA user_version={v}")
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── meta ──────────────────────────────────────────────
    def _ensure_meta(self, path: Path) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(path) VALUES(?)", (str(path),))

    def _set(self, path: Path, sql: str, *params) -> None:
        """所有 meta 写操作的公共出口：确保行存在 → 更新列 → 提交。
        sql 片段只传内部常量（如 "pinned=?"），不拼接外部输入。"""
        self._ensure_meta(path)
        self._conn.execute(
            f"UPDATE meta SET {sql} WHERE path=?", (*params, str(path)))
        self._conn.commit()

    def set_pinned(self, path: Path, pinned: bool) -> None:
        self._set(path, "pinned=?", int(pinned))

    def set_tags(self, path: Path, tags: list[str]) -> None:
        self._set(path, "tags=?", ",".join(tags))

    def set_command(self, path: Path, command: str | None,
                    shell_type: str = DEFAULT_SHELL) -> None:
        self._set(path, "command=?, shell_type=?", command or None, shell_type)

    def set_last_args(self, path: Path, args: str) -> None:
        """记住「带参数启动」上次用的参数，下次弹框回填。"""
        self._set(path, "last_args=?", args)

    def set_admin(self, path: Path, admin: bool) -> None:
        self._set(path, "admin=?", int(admin))

    @staticmethod
    def _meta_dict(row: sqlite3.Row) -> dict:
        return {
            "pinned": bool(row["pinned"]),
            "tags": [t for t in row["tags"].split(",") if t],
            "command": row["command"],
            "shell_type": row["shell_type"] or DEFAULT_SHELL,
            "last_args": row["last_args"] or "",
            "admin": bool(row["admin"]),
        }

    def all_meta(self) -> dict[str, dict]:
        """一次性取出全部 meta，扫描后合并用。"""
        return {row["path"]: self._meta_dict(row)
                for row in self._conn.execute("SELECT * FROM meta")}

    def prune(self, root: Path, valid_paths: set[str]) -> int:
        """清理失效元数据：只删「在当前工作区内、父目录仍在、条目已不存在」的行。

        故意保守：工作区整体离线、或切换到别的工作区时都不动，避免临时不可达被误删。
        返回删除的 meta 行数（stats 同步删除）。
        """
        root = Path(root)
        victims: list[str] = []
        for row in self._conn.execute("SELECT path FROM meta"):
            p = row["path"]
            if p in valid_paths or not self._in_workspace(root, p):
                continue
            path = Path(p)
            if path.parent.is_dir() and not path.exists():
                victims.append(p)
        if not victims:
            return 0
        marks = [(v,) for v in victims]
        self._conn.executemany("DELETE FROM meta WHERE path=?", marks)
        self._conn.executemany("DELETE FROM stats WHERE path=?", marks)
        self._conn.commit()
        log.info("清理失效元数据 %d 条", len(victims))
        return len(victims)

    @staticmethod
    def _in_workspace(root: Path, path: str) -> bool:
        try:
            Path(path).relative_to(root)
            return True
        except ValueError:
            return False

    # ── stats ─────────────────────────────────────────────
    def record_run(self, path: Path) -> None:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._conn.execute(
            """INSERT INTO stats(path, runs, last_run) VALUES(?, 1, ?)
               ON CONFLICT(path) DO UPDATE SET runs=runs+1, last_run=?""",
            (str(path), now, now))
        self._conn.commit()

    def get_stats(self, path: Path) -> dict:
        """单条查询，供详情面板点击时调用。"""
        row = self._conn.execute(
            "SELECT * FROM stats WHERE path=?", (str(path),)).fetchone()
        if not row:
            return {"runs": 0, "last_run": ""}
        return {"runs": row["runs"], "last_run": row["last_run"] or ""}

    def all_stats(self) -> dict[str, dict]:
        out = {}
        for row in self._conn.execute("SELECT * FROM stats"):
            out[row["path"]] = {"runs": row["runs"], "last_run": row["last_run"] or ""}
        return out
