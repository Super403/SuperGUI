"""全局热键解析：把 "Ctrl+Alt+K" 这类字符串解析成 Win32 (修饰键掩码, 虚拟键码)。

纯逻辑，不做注册——Win32 RegisterHotKey 在 main.py；ui 层拿它做输入校验。
"""
from __future__ import annotations

# 修饰键名 → Win32 MOD_* 标志位
MOD_MAP = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
# 无法单字符表示的按键名 → 虚拟键码（单字符键直接取 ord，F1-F12 单独处理）
NAMED_VK = {"space": 0x20, "tab": 0x09}
VK_F1 = 0x70  # F1-F12 键码连续：VK_Fn = VK_F1 + n - 1


def parse_hotkey(text: str) -> tuple[int, int] | None:
    """把 "Ctrl+Alt+K" 这类字符串解析成 (修饰键位掩码, 虚拟键码)，非法输入返回 None。

    字母/数字/Space/Tab 必须搭配至少一个修饰键，避免裸绑单键全局抢键；
    F1-F12 允许单独使用。
    """
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        return None

    mods = 0
    for name in parts[:-1]:  # 最后一段是主键，前面全是修饰键
        mod = MOD_MAP.get(name)
        if mod is None:
            return None
        mods |= mod

    key = parts[-1]
    # F1-F12 允许单用（媒体键生态常见）；字母/数字/Space/Tab 裸绑会全局抢键，必须带修饰键
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        return mods, VK_F1 + int(key[1:]) - 1
    if not mods:
        return None
    if len(key) == 1 and key.isalnum():
        return mods, ord(key.upper())  # 字母/数字的 VK 码即大写 ASCII
    if key in NAMED_VK:
        return mods, NAMED_VK[key]
    return None
