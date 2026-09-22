"""Apple-style glass widgets (iOS / macOS widget look).

Geometry follows iOS: a *small* widget is 158 x 158 pt, *medium* is 2 units wide (332 pt), 16 pt
gap, 16 pt inner padding, continuous ("squircle") corners, translucent glass surface, system
typography, SF-Symbols-like icons and Apple's system colours. Each widget widget uses one accent
colour while everything is fine and switches to system orange / red when a value needs attention.

Every widget implements ``update_data(snapshot, history)`` and ``set_theme(theme)``.
"""

from __future__ import annotations

import math
import sys
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFontMetricsF, QLinearGradient, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..collectors import Snapshot, fmt_bytes, split_bytes, split_rate, uptime_parts
from ..history import History
from ..layout import WidgetConfig
from ..metrics import CRIT, METRICS, NA, OK, WARN, Metric, metric_fraction
from ..temperature import MAC_HINT
from .fonts import CAPTION, HERO, HERO_UNIT, TITLE, W_MEDIUM, W_SEMIBOLD, ui_font
from .glass import RADIUS, paint_glass_card
from .icons import bolt_path, draw_icon
from .shapes import smooth_path
from .theme import LIGHT, Theme

UNIT = 158            # visible size of a small widget (pt)
GAP = 16              # visible gap between widgets
MARGIN = 8            # transparent margin around each card, room for the shadow
PAD = 16              # inner padding
HISTORY_SLOTS = 60    # samples shown in charts

Parts = Sequence[Tuple[str, str]]


# ------------------------------------------------------------------ drawing
def draw_hero(p: QPainter, rect: QRectF, parts: Parts, color: QColor, unit_color: QColor,
              hero_px: float = HERO, unit_px: float = HERO_UNIT,
              align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft) -> float:
    """Big rounded number(s) with smaller units, baseline aligned: ``3 d 5 h``. Returns text width."""
    gap, ugap = 4.0, 2.0
    scale = 1.0
    while True:    # shrink until the text fits the box (long numbers, wide fallback fonts)
        big = ui_font(hero_px * scale, W_SEMIBOLD, rounded=True, tracking=-0.4)
        small = ui_font(unit_px * scale, W_SEMIBOLD, rounded=True)
        fb, fs = QFontMetricsF(big), QFontMetricsF(small)
        segs = [(num, unit, fb.horizontalAdvance(num), fs.horizontalAdvance(unit) if unit else 0.0)
                for num, unit in parts]
        total = sum(wn + (wu + ugap if unit else 0.0) for _n, unit, wn, wu in segs) + gap * (len(segs) - 1)
        if total <= rect.width() or scale <= 0.6:
            break
        scale -= 0.04
    if align & Qt.AlignmentFlag.AlignHCenter:
        x = rect.center().x() - total / 2
    elif align & Qt.AlignmentFlag.AlignRight:
        x = rect.right() - total
    else:
        x = rect.left()
    base = rect.center().y() + (fb.ascent() - fb.descent()) / 2
    for num, unit, wn, wu in segs:
        p.setFont(big)
        p.setPen(color)
        p.drawText(QPointF(x, base), num)
        x += wn
        if unit:
            x += ugap
            p.setFont(small)
            p.setPen(unit_color)
            p.drawText(QPointF(x, base), unit)
            x += wu
        x += gap
    return total


def draw_caption(p: QPainter, rect: QRectF, text: str, color: QColor, px: float = CAPTION,
                 align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, weight=W_MEDIUM) -> None:
    p.setFont(ui_font(px, weight))
    p.setPen(color)
    p.drawText(rect, align, text)


def draw_activity_ring(p: QPainter, rect: QRectF, fraction: float, color: QColor, width: float = 11,
                       show_progress: bool = True) -> None:
    """Activity ring: track, gradient progress arc with round caps (starts at 12 o'clock).

    The track is neutral grey like Apple's Batteries widget; only the "Colorful" palette tints it.
    """
    from .theme import get_palette

    fraction = max(0.0, min(1.0, fraction))
    r = rect.adjusted(width / 2, width / 2, -width / 2, -width / 2)
    if get_palette() == "colorful":
        track = QColor(color)
        track.setAlpha(58)
    else:
        track = QColor(142, 142, 147, 72)        # systemGray at low alpha: reads on light and dark glass
    pen = QPen(track, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(r)
    if not show_progress:
        return
    if fraction < 0.006:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(r.center().x(), r.top()), width / 2, width / 2)
        return
    grad = QConicalGradient(r.center(), 90)
    light, dark = QColor(color).lighter(122), QColor(color).darker(112)
    grad.setColorAt(0.0, dark)
    grad.setColorAt(max(0.001, 1.0 - fraction), light)
    grad.setColorAt(1.0, dark)
    pen = QPen(QBrush(grad), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawArc(r, 90 * 16, int(-fraction * 360 * 16))


def draw_capsule_bar(p: QPainter, rect: QRectF, fraction: float, color: QColor, track: QColor) -> None:
    fraction = max(0.0, min(1.0, fraction))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(track)
    rad = rect.height() / 2
    p.drawRoundedRect(rect, rad, rad)
    if fraction > 0:
        w = max(rect.height(), rect.width() * fraction)
        grad = QLinearGradient(rect.topLeft(), rect.topRight())
        grad.setColorAt(0, QColor(color).lighter(112))
        grad.setColorAt(1, color)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(rect.left(), rect.top(), w, rect.height()), rad, rad)


def draw_area_chart(p: QPainter, rect: QRectF, values: List[Optional[float]], color: QColor,
                    vmax: float, vmin: float = 0.0, slots: int = HISTORY_SLOTS, marker: bool = True,
                    fill: bool = True, line_w: float = 2.4) -> None:
    """Smooth line with soft gradient fill, newest value on the right, end marker like Apple charts."""
    idx = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(idx) < 2:
        return
    n = len(values)
    span = max(vmax - vmin, 1e-9)
    step = rect.width() / max(slots - 1, 1)
    offset = slots - n

    def pt(i: int, v: float) -> QPointF:
        y = rect.bottom() - (max(vmin, min(vmax, v)) - vmin) / span * rect.height()
        return QPointF(rect.left() + (offset + i) * step, y)

    pts = [pt(i, v) for i, v in idx]
    path = smooth_path(pts, 0.5, floor_y=rect.bottom(), ceil_y=rect.top())
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if fill:
        area = QPainterPath(path)
        area.lineTo(pts[-1].x(), rect.bottom() + 2)
        area.lineTo(pts[0].x(), rect.bottom() + 2)
        area.closeSubpath()
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        top, bot = QColor(color), QColor(color)
        top.setAlpha(96)
        bot.setAlpha(0)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bot)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(area)
    pen = QPen(color, line_w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    if marker:
        last = pts[-1]
        halo = QColor(color)
        halo.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(last, 6.5, 6.5)
        p.setBrush(color)
        p.drawEllipse(last, 3.6, 3.6)
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawEllipse(last, 1.4, 1.4)
    p.restore()


def draw_arrow_badge(p: QPainter, center: QPointF, color: QColor, up: bool, r: float = 8.0) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(center, r, r)
    pen = QPen(QColor(255, 255, 255), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    tip_y = center.y() - 3.6 if up else center.y() + 3.6
    tail_y = center.y() + 3.6 if up else center.y() - 3.6
    back = 2.7 if up else -2.7           # arrow-head lines run back towards the tail
    p.drawLine(QPointF(center.x(), tail_y), QPointF(center.x(), tip_y))
    p.drawLine(QPointF(center.x() - 2.7, tip_y + back), QPointF(center.x(), tip_y))
    p.drawLine(QPointF(center.x() + 2.7, tip_y + back), QPointF(center.x(), tip_y))
    p.restore()


# -------------------------------------------------------------------- cards
class BaseCard(QWidget):
    """Glass card with icon + title header. Subclasses implement ``paint_body``."""

    icon = ""
    accent = "blue"

    def __init__(self, metric_id: str, title: str, cols: int = 1, rows: int = 1, parent=None):
        super().__init__(parent)
        self.metric_id = metric_id
        self.title = title
        self.cols, self.rows = cols, rows
        self.theme: Theme = LIGHT
        self.snap: Optional[Snapshot] = None
        self.hist: Optional[History] = None
        self.vis_w = cols * UNIT + (cols - 1) * GAP
        self.vis_h = rows * UNIT + (rows - 1) * GAP
        self.setFixedSize(self.vis_w + 2 * MARGIN, self.vis_h + 2 * MARGIN)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setObjectName(f"widget_{metric_id}")

    # public API ---------------------------------------------------------
    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.update()

    def update_data(self, snap: Snapshot, hist: History) -> None:
        self.snap, self.hist = snap, hist
        self.update()

    context_requested = None      # set by the dashboard: callable(global_pos)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.context_requested:
            self.context_requested(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)

    def level(self) -> str:
        m = METRICS.get(self.metric_id)
        return m.level(self.snap) if (m and self.snap) else NA

    def color(self) -> QColor:
        """Accent while fine, orange / red when the value needs attention."""
        return self.theme.level_color(self.level(), self.accent) if self.level() != NA else self.theme.accent(self.accent)

    # painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.translate(MARGIN, MARGIN)
        vis = QRectF(0, 0, self.vis_w, self.vis_h)
        paint_glass_card(p, vis, self.theme, RADIUS)
        # header: icon + title (iOS widget style)
        draw_icon(p, self.icon, QRectF(PAD, 12.5, 15, 15), self.theme.accent(self.accent))
        draw_caption(p, QRectF(PAD + 21, 11, self.vis_w - 2 * PAD - 21, 18), self.title, self.theme.label2,
                     px=TITLE, weight=W_SEMIBOLD)
        if self.snap is not None:
            self.paint_body(p, QRectF(PAD, 38, self.vis_w - 2 * PAD, self.vis_h - 38 - PAD))
        p.end()

    def paint_body(self, p: QPainter, area: QRectF) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def caption(self, p: QPainter, rect: QRectF, text: str, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                color: Optional[QColor] = None) -> None:
        draw_caption(p, rect, text, color or self.theme.label2, align=align)


class RingCard(BaseCard):
    """Activity ring with the value in the middle (CPU, Memory)."""

    def subtitle(self) -> str:
        return ""

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        m = METRICS[self.metric_id]
        sub = self.subtitle()
        ring_area = QRectF(area.left(), area.top() - 2, area.width(), area.height() - (17 if sub else 0) + 2)
        side = min(ring_area.width(), ring_area.height())
        ring = QRectF(ring_area.center().x() - side / 2, ring_area.top(), side, side)
        color = self.color()
        draw_activity_ring(p, ring, (m.value(self.snap) or 0.0) / 100.0, color, width=11)
        draw_hero(p, ring, [(f"{m.value(self.snap) or 0:.0f}", "%")], self.theme.label, self.theme.label2,
                  hero_px=25, unit_px=13, align=Qt.AlignmentFlag.AlignHCenter)
        if sub:
            self.caption(p, QRectF(area.left(), area.bottom() - 14, area.width(), 14), sub, Qt.AlignmentFlag.AlignCenter)


class CpuCard(RingCard):
    icon, accent = "cpu", "blue"

    def subtitle(self) -> str:
        n = len(self.snap.cpu_per_core) or 1
        return f"{n} cores"


class RamCard(RingCard):
    icon, accent = "memory", "purple"

    def subtitle(self) -> str:
        return f"{fmt_bytes(self.snap.ram_used)} of {fmt_bytes(self.snap.ram_total)}"


class TempCard(BaseCard):
    """Weather-style gauge: green-to-red arc with a white indicator dot."""

    icon, accent = "thermometer", "orange"
    T_MIN, T_MAX = 30.0, 100.0
    START, SWEEP = 215.0, 250.0        # degrees, Qt convention (counter-clockwise from 3 o'clock)
    STOPS = ((0.00, "green"), (0.38, "green"), (0.55, "yellow"), (0.72, "orange"), (1.00, "red"))

    @staticmethod
    def status(t: float) -> str:
        return "Cool" if t < 50 else "Normal" if t < 75 else "Warm" if t < 90 else "Hot"

    def _gauge_gradient(self, center: QPointF) -> QConicalGradient:
        grad = QConicalGradient(center, self.START - self.SWEEP)   # t=0 at the red (end) side
        span = self.SWEEP / 360.0
        for u, name in self.STOPS:
            grad.setColorAt((1.0 - u) * span, self.theme.color(name))
        return grad

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        m = METRICS["temp"]
        t = self.snap.cpu_temp_c
        side = min(area.width(), area.height() + 2) - 2
        box = QRectF(area.center().x() - side / 2, area.top() - 1, side, side)
        width = 9.0
        r = box.adjusted(width / 2 + 2, width / 2 + 2, -width / 2 - 2, -width / 2 - 2)
        pen = QPen(QBrush(self._gauge_gradient(r.center())), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.save()
        p.setOpacity(1.0 if t is not None else 0.35)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(r, int(self.START * 16), int(-self.SWEEP * 16))
        p.restore()
        if t is None:
            draw_hero(p, box, [("--", "")], self.theme.label2, self.theme.label2, hero_px=28,
                      align=Qt.AlignmentFlag.AlignHCenter)
            hint = "brew install macmon" if sys.platform == "darwin" else "No sensor"
            self.caption(p, QRectF(area.left(), area.bottom() - 14, area.width(), 14), hint, Qt.AlignmentFlag.AlignCenter)
            return
        frac = max(0.0, min(1.0, (t - self.T_MIN) / (self.T_MAX - self.T_MIN)))
        ang = math.radians(self.START - frac * self.SWEEP)
        rad = r.width() / 2
        dot = QPointF(r.center().x() + rad * math.cos(ang), r.center().y() - rad * math.sin(ang))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 55))
        p.drawEllipse(dot + QPointF(0, 1.2), 7.2, 7.2)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(dot, 6.2, 6.2)
        p.setBrush(self.theme.level_color(m.level(self.snap), "green"))
        p.drawEllipse(dot, 3.0, 3.0)
        draw_hero(p, box.adjusted(0, -4, 0, -4), [(f"{t:.0f}", "°")], self.theme.label, self.theme.label2,
                  hero_px=30, unit_px=22, align=Qt.AlignmentFlag.AlignHCenter)
        self.caption(p, QRectF(box.left(), box.bottom() - 26, box.width(), 14), self.status(t), Qt.AlignmentFlag.AlignCenter,
                     self.theme.label2)


class DiskCard(BaseCard):
    """iOS Storage style: free space as hero, capsule bar for the used share."""

    icon, accent = "disk", "teal"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        s = self.snap
        free = max(0, s.disk_total - s.disk_used)
        num, unit = split_bytes(free)
        draw_hero(p, QRectF(area.left(), area.top() + 2, area.width(), 40), [(num, unit)], self.theme.label,
                  self.theme.label2, hero_px=34, unit_px=17)
        self.caption(p, QRectF(area.left(), area.top() + 44, area.width(), 15),
                     f"free of {fmt_bytes(s.disk_total)}")
        bar = QRectF(area.left(), area.bottom() - 26, area.width(), 9)
        draw_capsule_bar(p, bar, s.disk_percent / 100.0, self.color(), self.theme.fill)
        self.caption(p, QRectF(area.left(), area.bottom() - 14, area.width(), 14), f"{s.disk_percent:.0f}% used")


class UptimeCard(BaseCard):
    icon, accent = "clock", "indigo"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        draw_hero(p, QRectF(area.left(), area.top() + 2, area.width(), 40), uptime_parts(self.snap.uptime_s),
                  self.theme.label, self.theme.label2, hero_px=34, unit_px=17)
        self.caption(p, QRectF(area.left(), area.top() + 44, area.width(), 15), "since last restart")


class BatteryCard(BaseCard):
    icon, accent = "battery", "green"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        s = self.snap
        m = METRICS["battery"]
        if s.battery_percent is None:
            draw_hero(p, QRectF(area.left(), area.top() + 2, area.width(), 40), [("AC", "")], self.theme.label,
                      self.theme.label2, hero_px=34)
            self.caption(p, QRectF(area.left(), area.top() + 44, area.width(), 15), "No battery")
            return
        draw_hero(p, QRectF(area.left(), area.top() + 2, area.width(), 40), [(f"{s.battery_percent:.0f}", "%")],
                  self.theme.label, self.theme.label2, hero_px=34, unit_px=17)
        # battery glyph
        body = QRectF(area.left(), area.top() + 52, 52, 24)
        p.setPen(QPen(self.theme.label3, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body, 7, 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.theme.label3)
        p.drawRoundedRect(QRectF(body.right() + 2.5, body.center().y() - 4.5, 3.2, 9), 1.6, 1.6)
        level = self.theme.level_color(m.level(s), "green")
        fill = QRectF(body.left() + 3, body.top() + 3, max(8.0, (body.width() - 6) * s.battery_percent / 100.0),
                      body.height() - 6)
        p.setBrush(level)
        p.drawRoundedRect(fill, 4.5, 4.5)
        if s.battery_charging:
            p.setBrush(QColor(255, 255, 255, 235))
            p.setPen(QPen(QColor(0, 0, 0, 60), 0.6))
            p.drawPath(bolt_path(body.center().x(), body.center().y(), 15))
        self.caption(p, QRectF(area.left(), area.bottom() - 14, area.width(), 14),
                     "Charging" if s.battery_charging else "On battery")


class NetworkCard(BaseCard):
    """Medium: download and upload, each with rate and smooth history."""

    icon, accent = "network", "blue"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        col_w = (area.width() - GAP) / 2
        for i, (key, label, color, val, up) in enumerate((
            ("net_down", "Download", self.theme.color("blue"), self.snap.net_down_bps, False),
            ("net_up", "Upload", self.theme.color("green"), self.snap.net_up_bps, True),
        )):
            x = area.left() + i * (col_w + GAP)
            draw_arrow_badge(p, QPointF(x + 8, area.top() + 8), color, up)
            self.caption(p, QRectF(x + 21, area.top(), col_w - 21, 16), label)
            num, unit = split_rate(val)
            draw_hero(p, QRectF(x, area.top() + 20, col_w, 30), [(num, unit)], self.theme.label, self.theme.label2,
                      hero_px=24, unit_px=13)
            series = self.hist.series(key) if self.hist else []
            vmax = max([v for v in series if v is not None] + [0.0]) * 1.25
            draw_area_chart(p, QRectF(x, area.top() + 58, col_w - 4, area.height() - 62), series, color,
                            vmax=max(vmax, 50 * 1024.0))


class PingCard(BaseCard):
    """Medium: latency hero, status line and smooth history."""

    icon, accent = "ping", "green"
    host_label = "1.1.1.1"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        s = self.snap
        m = METRICS["ping"]
        lv = m.level(s)
        color = self.theme.level_color(lv, "green")
        if s.ping_pending:
            parts, status = [("--", "")], "Checking…"
        elif s.ping_ms is None:
            parts, status = [("Offline", "")], "No connection"
        else:
            parts = [(f"{s.ping_ms:.0f}", "ms")]
            status = {OK: "Connected", WARN: "Slow connection", CRIT: "Very slow"}.get(lv, "Connected")
        draw_hero(p, QRectF(area.left(), area.top() + 2, area.width() * 0.5, 40), parts,
                  self.theme.label if s.ping_ms is not None else color, self.theme.label2, hero_px=34, unit_px=17)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(area.left() + 4.5, area.top() + 52), 4, 4)
        self.caption(p, QRectF(area.left() + 14, area.top() + 44, area.width() * 0.6, 16), f"{status} · {self.host_label}")
        series = self.hist.series("ping") if self.hist else []
        vals = [v for v in series if v is not None]
        if vals:
            stats = f"avg {sum(vals) / len(vals):.0f} ms   max {max(vals):.0f} ms"
            self.caption(p, QRectF(area.right() - 170, area.top() + 2, 170, 16), stats,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        draw_area_chart(p, QRectF(area.left(), area.top() + 68, area.width() - 4, area.height() - 72), series, color,
                        vmax=max(max(vals + [0.0]) * 1.3, 60.0))


class CoresCard(BaseCard):
    """Medium: one capsule per CPU core."""

    icon, accent = "cores", "blue"

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        cores = list(self.snap.cpu_per_core)[:32] or [self.snap.cpu_percent]
        n = len(cores)
        gap = 6 if n <= 12 else 3
        bar_w = min(20.0, max(4.0, (area.width() - gap * (n - 1)) / n))
        chart = QRectF(area.left(), area.top() + 2, area.width(), area.height() - 26)
        x0 = chart.left() + (chart.width() - (n * bar_w + (n - 1) * gap)) / 2
        for i, v in enumerate(cores):
            x = x0 + i * (bar_w + gap)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.theme.fill)
            p.drawRoundedRect(QRectF(x, chart.top(), bar_w, chart.height()), bar_w / 2, bar_w / 2)
            h = max(bar_w, chart.height() * v / 100.0)
            lvl = CRIT if v >= 90 else WARN if v >= 70 else OK
            grad = QLinearGradient(QPointF(x, chart.bottom() - h), QPointF(x, chart.bottom()))
            c = self.theme.level_color(lvl, self.accent)
            grad.setColorAt(0, QColor(c).lighter(115))
            grad.setColorAt(1, c)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x, chart.bottom() - h, bar_w, h), bar_w / 2, bar_w / 2)
        self.caption(p, QRectF(area.left(), area.bottom() - 15, area.width(), 15),
                     f"{n} cores · avg {sum(cores) / n:.0f}%", Qt.AlignmentFlag.AlignCenter)


# ------------------------------------------------- configurable widgets
def chart_bounds(m: Metric, series: List[Optional[float]]) -> Tuple[float, float]:
    lo, hi = m.chart_range
    if hi is None:
        vals = [v for v in series if v is not None]
        floor = 50 * 1024.0 if m.adaptive else 60.0
        hi = max(max(vals + [0.0]) * 1.25, floor)
    return (lo or 0.0), hi


class MultiCard(BaseCard):
    """Any mix of values as rings, bars or plain numbers - what the user picked in the menu."""

    def __init__(self, cfg: WidgetConfig, parent=None):
        self.cfg = cfg
        first = METRICS[cfg.metrics[0]]
        title = first.label if len(cfg.metrics) == 1 else "System"
        super().__init__(first.id, title, cols=cfg.cols, parent=parent)
        self.icon, self.accent = first.icon, first.accent
        self.metric_ids = list(cfg.metrics)

    # colours -------------------------------------------------------------
    def metric_color(self, m: Metric) -> QColor:
        lv = m.level(self.snap)
        return self.theme.accent(m.accent) if lv == NA else self.theme.level_color(lv, m.accent)

    def value_color(self, m: Metric) -> QColor:
        lv = m.level(self.snap)
        return self.theme.level_color(lv, m.accent) if lv in (WARN, CRIT) else self.theme.label

    def fraction(self, m: Metric) -> Optional[float]:
        series = self.hist.series(m.series) if (self.hist and m.series) else None
        return metric_fraction(m, self.snap, series)

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        ms = [METRICS[i] for i in self.cfg.metrics]
        {"rings": self._rings, "bars": self._bars, "numbers": self._numbers}.get(self.cfg.style, self._numbers)(p, area, ms)

    # rings ---------------------------------------------------------------
    def _rings(self, p: QPainter, area: QRectF, ms: List[Metric]) -> None:
        n = len(ms)
        label_h = 15.0
        slot_w = area.width() / n
        d = max(30.0, min(slot_w - 6, area.height() - label_h - 2, 96.0))
        top = area.top() + (area.height() - label_h - d) / 2
        for i, m in enumerate(ms):
            cx = area.left() + slot_w * (i + 0.5)
            ring = QRectF(cx - d / 2, top, d, d)
            width = max(5.5, d * 0.125)
            frac = self.fraction(m)
            draw_activity_ring(p, ring, frac or 0.0, self.metric_color(m), width, show_progress=frac is not None)
            inner = ring.adjusted(width, width, -width, -width)
            draw_hero(p, inner, m.display_parts(self.snap), self.value_color(m), self.theme.label2,
                      hero_px=max(11.0, d * 0.27), unit_px=max(8.0, d * 0.15), align=Qt.AlignmentFlag.AlignHCenter)
            self.caption(p, QRectF(cx - slot_w / 2, area.bottom() - label_h, slot_w, label_h), m.label_short(),
                         Qt.AlignmentFlag.AlignCenter)

    # bars ----------------------------------------------------------------
    def _bars(self, p: QPainter, area: QRectF, ms: List[Metric]) -> None:
        n = len(ms)
        if n == 1:
            m = ms[0]
            draw_hero(p, QRectF(area.left(), area.top() + 6, area.width(), 40), m.display_parts(self.snap),
                      self.value_color(m), self.theme.label2, hero_px=34, unit_px=17)
            frac = self.fraction(m)
            draw_capsule_bar(p, QRectF(area.left(), area.top() + 58, area.width(), 10), frac or 0.0,
                             self.metric_color(m), self.theme.fill)
            return
        row_h = min(34.0, area.height() / n)
        y0 = area.top() + (area.height() - row_h * n) / 2
        text_h = row_h * 0.52
        bar_h = 7.0 if n <= 3 else 6.0
        for i, m in enumerate(ms):
            y = y0 + i * row_h
            self.caption(p, QRectF(area.left(), y, area.width() * 0.55, text_h), m.label_short())
            draw_hero(p, QRectF(area.left() + area.width() * 0.4, y, area.width() * 0.6, text_h),
                      m.display_parts(self.snap), self.value_color(m), self.theme.label2,
                      hero_px=min(15.0, text_h * 1.05), unit_px=min(11.0, text_h * 0.8),
                      align=Qt.AlignmentFlag.AlignRight)
            frac = self.fraction(m)
            draw_capsule_bar(p, QRectF(area.left(), y + text_h + 2, area.width(), bar_h), frac or 0.0,
                             self.metric_color(m), self.theme.fill)

    # numbers -------------------------------------------------------------
    def _numbers(self, p: QPainter, area: QRectF, ms: List[Metric]) -> None:
        n = len(ms)
        if n == 1:
            m = ms[0]
            draw_hero(p, QRectF(area.left(), area.top() + 4, area.width(), 46), m.display_parts(self.snap),
                      self.value_color(m), self.theme.label2, hero_px=40, unit_px=20)
            self.caption(p, QRectF(area.left(), area.top() + 54, area.width(), 16), m.label)
            return
        if self.cfg.size == "small":                       # stacked rows, label left / number right
            row_h = area.height() / n
            for i, m in enumerate(ms):
                row = QRectF(area.left(), area.top() + i * row_h, area.width(), row_h)
                if i:
                    p.setPen(QPen(self.theme.label3, 0.5))
                    p.drawLine(QPointF(row.left(), row.top()), QPointF(row.right(), row.top()))
                self.caption(p, QRectF(row.left(), row.top(), row.width() * 0.45, row.height()), m.label_short())
                draw_hero(p, QRectF(row.left() + row.width() * 0.3, row.top(), row.width() * 0.7, row.height()),
                          m.display_parts(self.snap), self.value_color(m), self.theme.label2,
                          hero_px=min(24.0, row_h * 0.72), unit_px=min(13.0, row_h * 0.42),
                          align=Qt.AlignmentFlag.AlignRight)
            return
        cols = 2 if n == 2 or n == 4 else 3
        rows = (n + cols - 1) // cols
        cw, ch = area.width() / cols, area.height() / rows
        for i, m in enumerate(ms):
            r, c = divmod(i, cols)
            cell = QRectF(area.left() + c * cw, area.top() + r * ch, cw - 6, ch)
            self.caption(p, QRectF(cell.left(), cell.top() + 2, cell.width(), 15), m.label_short())
            draw_hero(p, QRectF(cell.left(), cell.top() + 17, cell.width(), ch - 19), m.display_parts(self.snap),
                      self.value_color(m), self.theme.label2, hero_px=min(30.0, (ch - 19) * 0.8),
                      unit_px=min(15.0, (ch - 19) * 0.4))


class MiniChartCard(BaseCard):
    """Small detailed widget for values without a dedicated design: big number plus history chart."""

    def __init__(self, metric_id: str, parent=None):
        m = METRICS[metric_id]
        super().__init__(metric_id, m.label, parent=parent)
        self.icon, self.accent = m.icon, m.accent

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        m = METRICS[self.metric_id]
        draw_hero(p, QRectF(area.left(), area.top() + 2, area.width(), 40), m.display_parts(self.snap),
                  self.value_color_for(m), self.theme.label2, hero_px=32, unit_px=16)
        series = self.hist.series(m.series) if (self.hist and m.series) else []
        lo, hi = chart_bounds(m, series)
        draw_area_chart(p, QRectF(area.left(), area.top() + 50, area.width() - 4, area.height() - 54), series,
                        self.theme.accent(m.accent) if m.level(self.snap) in (OK, NA) else self.color(), vmax=hi, vmin=lo)

    def value_color_for(self, m: Metric) -> QColor:
        lv = m.level(self.snap)
        return self.theme.level_color(lv, m.accent) if lv in (WARN, CRIT) else self.theme.label


class ChartCard(BaseCard):
    """Medium detailed widget for one or two values: each with number and history chart."""

    def __init__(self, metrics: Sequence[str], parent=None):
        ms = [METRICS[i] for i in metrics]
        super().__init__(ms[0].id, ms[0].label if len(ms) == 1 else "System", cols=2, parent=parent)
        self.ids = list(metrics)
        self.metric_ids = list(metrics)
        self.icon, self.accent = ms[0].icon, ms[0].accent

    def paint_body(self, p: QPainter, area: QRectF) -> None:
        n = len(self.ids)
        col_w = (area.width() - (GAP if n > 1 else 0)) / n
        for i, mid in enumerate(self.ids):
            m = METRICS[mid]
            x = area.left() + i * (col_w + GAP)
            color = self.theme.accent(m.accent)
            lv = m.level(self.snap)
            if lv in (WARN, CRIT):
                color = self.theme.level_color(lv, m.accent)
            if mid in ("net_down", "net_up"):
                draw_arrow_badge(p, QPointF(x + 8, area.top() + 8), color, mid == "net_up")
                self.caption(p, QRectF(x + 21, area.top(), col_w - 21, 16), m.label)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawEllipse(QPointF(x + 4.5, area.top() + 8), 4, 4)
                self.caption(p, QRectF(x + 14, area.top(), col_w - 14, 16), m.label)
            draw_hero(p, QRectF(x, area.top() + 20, col_w, 30), m.display_parts(self.snap),
                      color if lv in (WARN, CRIT) else self.theme.label, self.theme.label2, hero_px=24, unit_px=13)
            series = self.hist.series(m.series) if (self.hist and m.series) else []
            lo, hi = chart_bounds(m, series)
            draw_area_chart(p, QRectF(x, area.top() + 58, col_w - 4, area.height() - 62), series, color, vmax=hi, vmin=lo)


_SMALL_DETAIL = {
    "cpu": lambda: CpuCard("cpu", "CPU"),
    "ram": lambda: RamCard("ram", "Memory"),
    "temp": lambda: TempCard("temp", "Temperature"),
    "disk": lambda: DiskCard("disk", "Disk"),
    "uptime": lambda: UptimeCard("uptime", "Uptime"),
    "battery": lambda: BatteryCard("battery", "Battery"),
}


def _make_card(cfg: WidgetConfig) -> BaseCard:
    ms = tuple(cfg.metrics)
    if cfg.style != "detail":
        return MultiCard(cfg)
    if cfg.size == "small":
        maker = _SMALL_DETAIL.get(ms[0])
        return maker() if maker else MiniChartCard(ms[0])
    if ms == ("cpu",):
        return CoresCard("cores", "CPU Cores", cols=2)
    if ms == ("ping",):
        return PingCard("ping", "Ping", cols=2)
    if set(ms) == {"net_down", "net_up"}:
        return NetworkCard("network", "Network", cols=2)
    return ChartCard(ms)


def create_card(cfg: WidgetConfig) -> BaseCard:
    """Build the widget for one layout entry; ``metric_ids`` always lists what it shows."""
    card = _make_card(cfg)
    card.metric_ids = list(cfg.metrics)
    card.config = cfg
    return card


def build_widgets(layout=None) -> List[BaseCard]:
    """Cards for ``layout`` (default: the standard detailed dashboard)."""
    from ..layout import DEFAULT_LAYOUT

    return [create_card(cfg) for cfg in (layout or DEFAULT_LAYOUT)]
