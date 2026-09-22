"""Shape helpers: Apple's continuous-corner ("squircle") rectangle and smooth curves."""

from __future__ import annotations

import math
from typing import List, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTransform


def _corner_params(radius: float, smoothing: float, budget: float):
    """Bezier parameters for one continuous corner (after the figma-squircle construction)."""
    p = (1 + smoothing) * radius
    max_smoothing = budget / radius - 1
    smoothing = min(smoothing, max_smoothing)
    p = min(p, budget)
    arc_measure = 90 * (1 - smoothing)
    arc_len = math.sin(math.radians(arc_measure / 2)) * radius * math.sqrt(2)
    alpha = (90 - arc_measure) / 2
    p3p4 = radius * math.tan(math.radians(alpha / 2))
    beta = 45 * smoothing
    c = p3p4 * math.cos(math.radians(beta))
    d = c * math.tan(math.radians(beta))
    b = (p - arc_len - c - d) / 3
    a = 2 * b
    return a, b, c, d, p, arc_len, radius, arc_measure


def _top_right_corner(radius: float, smoothing: float, budget: float) -> QPainterPath:
    """Corner with its apex at (0, 0); the shape lies in x<0, y>0 (screen coordinates)."""
    a, b, c, d, p, arc_len, r, arc_measure = _corner_params(radius, smoothing, budget)
    path = QPainterPath(QPointF(-p, 0))
    path.cubicTo(QPointF(-p + a, 0), QPointF(-p + a + b, 0), QPointF(-p + a + b + c, d))
    # circular arc between the two Bezier sections
    s = QPointF(-arc_len - d, d)
    e = QPointF(-d, d + arc_len)
    theta = math.radians(arc_measure)
    mid = QPointF((s.x() + e.x()) / 2, (s.y() + e.y()) / 2)
    h = r * math.cos(theta / 2)
    inv = 1 / math.sqrt(2)
    center = QPointF(mid.x() - h * inv, mid.y() + h * inv)
    start_angle = math.degrees(math.atan2(-(s.y() - center.y()), s.x() - center.x()))
    path.arcTo(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r), start_angle, -arc_measure)
    path.cubicTo(QPointF(-d + d, d + arc_len + c), QPointF(-d + d, d + arc_len + b + c),
                 QPointF(0, d + arc_len + a + b + c))
    return path


def squircle_path(rect: QRectF, radius: float, smoothing: float = 0.6) -> QPainterPath:
    """iOS-style continuous rounded rectangle (smoothing 0.6 matches Apple's app icon curve)."""
    budget = min(rect.width(), rect.height()) / 2
    radius = min(radius, budget / (1 + smoothing) if smoothing > 0 else budget)
    if radius <= 0.5:
        p = QPainterPath()
        p.addRect(rect)
        return p
    corner = _top_right_corner(radius, smoothing, budget)
    out = QPainterPath()
    anchors = [
        (rect.right(), rect.top(), 0),
        (rect.right(), rect.bottom(), 90),
        (rect.left(), rect.bottom(), 180),
        (rect.left(), rect.top(), 270),
    ]
    for i, (x, y, angle) in enumerate(anchors):
        t = QTransform()
        t.translate(x, y)
        t.rotate(angle)
        placed = t.map(corner)
        if i == 0:
            out.addPath(placed)
        else:
            out.connectPath(placed)
    out.closeSubpath()
    return out


def smooth_path(points: Sequence[QPointF], tension: float = 0.5, floor_y: Optional[float] = None,
                ceil_y: Optional[float] = None) -> QPainterPath:
    """Catmull-Rom spline through ``points`` converted to cubic Beziers (overshoot clamped)."""
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0])
    n = len(points)
    for i in range(n - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < n else p2
        c1 = QPointF(p1.x() + (p2.x() - p0.x()) * tension / 3,
                     p1.y() + (p2.y() - p0.y()) * tension / 3)
        c2 = QPointF(p2.x() - (p3.x() - p1.x()) * tension / 3,
                     p2.y() - (p3.y() - p1.y()) * tension / 3)
        for c in (c1, c2):
            if ceil_y is not None:
                c.setY(max(ceil_y, c.y()))
            if floor_y is not None:
                c.setY(min(floor_y, c.y()))
        path.cubicTo(c1, c2, p2)
    return path
