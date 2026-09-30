"""设置读写：config/config.yaml，人类可读、可手改。"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

DEFAULTS = {
    "workspace_root": "",      # 空则启动时探测/询问
    "workspace_presets": [],   # 顶栏两个快捷按钮 [{name, path}]，空则用默认（工具/桌面）
    "theme": "light",          # light | dark
    "titlebar": "macos",       # macos（左侧交通灯）| windows（右侧 — □ ✕）
    "view": "grid",            # grid | list
    "show_tags": False,        # 侧栏标签云默认隐藏
    "hotkey": "Alt+Space",
    "window": {"w": 1440, "h": 860, "x": None, "y": None, "maximized": False},  # x/y 为空则交给系统摆放
}

def _desktop() -> Path:
    return Path.home() / "Desktop"

def _candidate_workspaces() -> list[Path]:
    """通用候选：用户目录和各盘符根下的 Tools / Toolbox，谁存在用谁。

    个人路径别写在这里（会进仓库），固定工作区直接配 config.yaml。
    """
    cands = [Path.home() / "Tools"]
    for drive in "CDEF":
        for name in ("Tools", "Toolbox"):
            cands.append(Path(f"{drive}:/{name}"))
    return cands


def default_workspace_presets() -> list[dict]:
    """顶栏两个工作区按钮的默认预设：工具=探测到的 Tools 目录，桌面=桌面。"""
    desktop = _desktop()
    tools = next((p for p in _candidate_workspaces() if p.is_dir()), desktop)
    return [{"name": "工具", "path": str(tools)},
            {"name": "桌面", "path": str(desktop)}]


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self._data = dict(DEFAULTS)
        if path.is_file():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                # 深合并一层（window 这种嵌套 dict）
                for k, v in loaded.items():
                    if isinstance(v, dict) and isinstance(self._data.get(k), dict):
                        self._data[k].update(v)
                    else:
                        self._data[k] = v
            except (yaml.YAMLError, OSError) as e:
                log.error("读取设置失败，使用默认值: %s", e)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                yaml.safe_dump(self._data, allow_unicode=True, sort_keys=False),
                encoding="utf-8")
        except OSError as e:
            log.error("保存设置失败: %s", e)

    def get_presets(self) -> list[dict]:
        """顶栏工作区按钮预设（固定两条）。未配置或字段缺失时用默认值补齐。"""
        presets = default_workspace_presets()
        raw = self.get("workspace_presets") or []
        for i, p in enumerate(raw[:2]):
            if isinstance(p, dict):
                name, path = str(p.get("name") or ""), str(p.get("path") or "")
                presets[i] = {"name": name or presets[i]["name"],
                              "path": path or presets[i]["path"]}
        return presets

    def set_presets(self, presets: list[dict]) -> None:
        self.set("workspace_presets", presets[:2])

    def detect_workspace(self) -> str:
        """返回已配置的工作区；未配置则探测常见位置，最后兜底桌面。"""
        root = self.get("workspace_root")
        if root and Path(root).is_dir():
            return root
        for candidate in _candidate_workspaces():
            if candidate.is_dir():
                self.set("workspace_root", str(candidate))
                return str(candidate)
        desktop = _desktop()
        if desktop.is_dir():
            self.set("workspace_root", str(desktop))
            return str(desktop)
        return ""
