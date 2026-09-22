"""Tiny SF-Symbols-like vector icons drawn with QPainter (stroke based, round caps)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


def _pen(color: QColor, w: float) -> QPen:
    pen = QPen(color, w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def draw_icon(p: QPainter, name: str, rect: QRectF, color: QColor) -> None:
    """Draw icon ``name`` into a square ``rect`` (about 14-16 px)."""
    fn = ICONS.get(name)
    if fn is None:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(rect.topLeft())
    s = min(rect.width(), rect.height())
    p.scale(s / 16.0, s / 16.0)      # icons are designed on a 16x16 grid
    fn(p, color)
    p.restore()


def _cpu(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 3.5, 9, 9), 2, 2)
    p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(6.3, 6.3, 3.4, 3.4), 0.8, 0.8)
    p.setPen(_pen(c, 1.3))
    for t in (6, 10):
        p.drawLine(QPointF(t, 1.2), QPointF(t, 3.5)); p.drawLine(QPointF(t, 12.5), QPointF(t, 14.8))
        p.drawLine(QPointF(1.2, t), QPointF(3.5, t)); p.drawLine(QPointF(12.5, t), QPointF(14.8, t))


def _memory(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(1.5, 4.5, 13, 7), 1.6, 1.6)
    p.setPen(_pen(c, 1.3))
    for x in (5, 8, 11):
        p.drawLine(QPointF(x, 7), QPointF(x, 9))
    for x in (4, 7, 10, 13):
        p.drawLine(QPointF(x, 11.6), QPointF(x, 13.4))


def _thermo(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(6.4, 9.2); path.lineTo(6.4, 3.4)
    path.arcTo(QRectF(6.4, 1.4, 3.2, 4.0), 180, -180)
    path.lineTo(9.6, 9.2)
    path.arcTo(QRectF(4.6, 8.6, 6.8, 6.4), 60, 300)
    p.drawPath(path)
    p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(8, 11.8), 1.6, 1.6)
    p.setPen(_pen(c, 1.5)); p.drawLine(QPointF(8, 5), QPointF(8, 11))


def _disk(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(1.8, 5, 12.4, 6.6), 2.2, 2.2)
    p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(11.4, 8.3), 0.9, 0.9)
    p.setPen(_pen(c, 1.4)); p.drawLine(QPointF(4.4, 8.3), QPointF(8, 8.3))


def _network(p, c):
    p.setPen(_pen(c, 1.6)); p.setBrush(Qt.BrushStyle.NoBrush)
    for x, up in ((5, False), (11, True)):
        y0, y1 = (3, 13) if not up else (13, 3)
        p.drawLine(QPointF(x, y0), QPointF(x, y1))
        d = 2.6 if up else -2.6
        p.drawLine(QPointF(x - 2.4, y1 + d), QPointF(x, y1)); p.drawLine(QPointF(x + 2.4, y1 + d), QPointF(x, y1))


def _ping(p, c):
    p.setPen(_pen(c, 1.6)); p.setBrush(Qt.BrushStyle.NoBrush)
    for r in (3.2, 6.2, 9.2):
        p.drawArc(QRectF(8 - r, 12.5 - r, 2 * r, 2 * r), 45 * 16, 90 * 16)
    p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(8, 12.5), 1.2, 1.2)


def _cores(p, c):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(c)
    for i, h in enumerate((5, 9, 7, 12)):
        p.drawRoundedRect(QRectF(2 + i * 3.4, 14 - h, 2.2, h), 1.1, 1.1)


def _clock(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(1.8, 1.8, 12.4, 12.4))
    p.drawLine(QPointF(8, 4.6), QPointF(8, 8)); p.drawLine(QPointF(8, 8), QPointF(10.4, 9.4))


def _battery(p, c):
    p.setPen(_pen(c, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(1.5, 4.5, 11.5, 7), 2.2, 2.2)
    p.setBrush(c); p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(14, 6.8, 1.4, 2.4), 0.7, 0.7)
    p.drawRoundedRect(QRectF(3.4, 6.4, 6, 3.2), 0.9, 0.9)


ICONS = {
    "cpu": _cpu, "memory": _memory, "thermometer": _thermo, "disk": _disk, "network": _network,
    "ping": _ping, "cores": _cores, "clock": _clock, "battery": _battery,
}


def bolt_path(cx: float, cy: float, h: float) -> QPainterPath:
    """Charging bolt centred at (cx, cy) with height h."""
    s = h / 10.0
    pts = [(0.9, -5), (-3.0, 0.6), (-0.4, 0.6), (-1.0, 5), (3.0, -0.8), (0.4, -0.8)]
    path = QPainterPath()
    for i, (x, y) in enumerate(pts):
        q = QPointF(cx + x * s, cy + y * s)
        path.moveTo(q) if i == 0 else path.lineTo(q)
    path.closeSubpath()
    return path
