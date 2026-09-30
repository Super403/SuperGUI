"""UI 工具：内嵌 SVG 渲染为 QIcon（{c} 占位符替换颜色）、手绘 Logo。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_COLOR = "#8a93a3"   # 全局未选中图标色，深浅主题通用


def make_logo_icon(size: int = 64) -> QIcon:
    """应用 Logo：代码手绘，不依赖外部图片文件。"""
    return QIcon(_paint_logo(size))


def _paint_logo(size: int) -> QPixmap:
    """手绘 Logo：绿色圆角方块 + 白色「网」字。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#3cb56f"))
    p.setPen(Qt.PenStyle.NoPen)
    r = size * 0.22  # 圆角半径随尺寸等比缩放
    p.drawRoundedRect(QRectF(0, 0, size, size), r, r)
    p.setPen(QColor("#ffffff"))
    font = QFont("Microsoft YaHei UI", int(size * 0.42))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "网")
    p.end()
    return pix


# ── 16x16 线性图标，{c} 为描边色占位符 ──
SVG_GRID = '<svg viewBox="0 0 16 16" fill="none"><rect x="1.5" y="1.5" width="5" height="5" rx="1.2" stroke="{c}" stroke-width="1.4"/><rect x="9.5" y="1.5" width="5" height="5" rx="1.2" stroke="{c}" stroke-width="1.4"/><rect x="1.5" y="9.5" width="5" height="5" rx="1.2" stroke="{c}" stroke-width="1.4"/><rect x="9.5" y="9.5" width="5" height="5" rx="1.2" stroke="{c}" stroke-width="1.4"/></svg>'
SVG_LIST = '<svg viewBox="0 0 16 16" fill="none"><path d="M5.5 4h9M5.5 8h9M5.5 12h9" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/><circle cx="2.4" cy="4" r="1.1" fill="{c}"/><circle cx="2.4" cy="8" r="1.1" fill="{c}"/><circle cx="2.4" cy="12" r="1.1" fill="{c}"/></svg>'
SVG_MOON = '<svg viewBox="0 0 16 16" fill="none"><path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z" stroke="{c}" stroke-width="1.4" stroke-linejoin="round"/></svg>'
SVG_SUN = '<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3.2" stroke="{c}" stroke-width="1.4"/><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/></svg>'
SVG_PANEL = '<svg viewBox="0 0 16 16" fill="none"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="{c}" stroke-width="1.4"/><path d="M10 2.5v11" stroke="{c}" stroke-width="1.4"/></svg>'
SVG_SEARCH = '<svg viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="5" stroke="{c}" stroke-width="1.5"/><path d="m11 11 3.2 3.2" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/></svg>'
SVG_STAR = '<svg viewBox="0 0 16 16" fill="none"><path d="m8 2 1.8 3.7 4.1.6-3 2.9.7 4.1L8 11.4l-3.6 1.9.7-4.1-3-2.9 4.1-.6L8 2Z" stroke="{c}" stroke-width="1.3" stroke-linejoin="round"/></svg>'
SVG_CLOCK = '<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.2" stroke="{c}" stroke-width="1.4"/><path d="M8 4.5V8l2.4 1.6" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/></svg>'
SVG_FOLDER = '<svg viewBox="0 0 16 16" fill="none"><path d="M1.5 4.5A1.5 1.5 0 0 1 3 3h3l1.5 2H13a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 13 13H3a1.5 1.5 0 0 1-1.5-1.5v-7Z" stroke="{c}" stroke-width="1.3"/></svg>'
SVG_SETTINGS = '<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2.2" stroke="{c}" stroke-width="1.4"/><path d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.6 3.6l1.2 1.2M11.2 11.2l1.2 1.2M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/></svg>'
SVG_REFRESH = '<svg viewBox="0 0 16 16" fill="none"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v2.6h-2.6" stroke="{c}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'

# 渲染结果缓存：同一图标只画一次
_cache: dict[tuple[str, str, int], QIcon] = {}

RENDER_DPR = 2  # 固定 2 倍渲染，高分屏下图标不发虚


def svg_icon(svg: str, color: str, size: int = 16) -> QIcon:
    """SVG 字符串渲染成 QIcon，结果按 (svg, color, size) 缓存。"""
    key = (svg, color, size)
    if key in _cache:
        return _cache[key]
    data = svg.replace("{c}", color).encode("utf-8")
    pix = QPixmap(size * RENDER_DPR, size * RENDER_DPR)
    pix.setDevicePixelRatio(RENDER_DPR)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(data).render(painter, QRectF(0, 0, size, size))
    painter.end()
    icon = QIcon(pix)
    _cache[key] = icon
    return icon
