"""Metric definitions shared by the dashboard widgets and the menu bar / tray readout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .collectors import Snapshot, fmt_rate, fmt_uptime, split_rate, uptime_parts

# Status levels drive the colours (green / orange / red like iOS system colours).
OK, WARN, CRIT, NA = "ok", "warn", "crit", "na"

Parts = List[Tuple[str, str]]


@dataclass(frozen=True)
class Metric:
    id: str
    label: str          # long label, e.g. "CPU Temperature"
    short: str          # tray prefix, e.g. "T"
    value: Callable[[Snapshot], Optional[float]]
    text: Callable[[Snapshot], str]      # compact text for the tray
    level: Callable[[Snapshot], str]
    # --- widget presentation -------------------------------------------------
    icon: str = "cpu"                    # icon name in ui/icons.py
    accent: str = "blue"                 # Apple system colour name
    parts: Optional[Callable[[Snapshot], Parts]] = None       # [(number, unit)] for big numbers
    fraction: Optional[Callable[[Snapshot], Optional[float]]] = None   # 0..1 for rings / bars
    adaptive: bool = False               # no natural maximum: scale against recent history
    series: Optional[str] = None         # history key for charts
    chart_range: Tuple[Optional[float], Optional[float]] = (0.0, None)   # (min, max) for charts; None = adaptive
    short_label: str = ""                # label under rings / next to bars ("CPU", "Temp", ...)

    def display_parts(self, snap: Snapshot) -> Parts:
        if self.parts:
            return self.parts(snap)
        return [(self.text(snap), "")]

    def label_short(self) -> str:
        return self.short_label or self.label


def _pct_level(v: Optional[float], warn: float, crit: float) -> str:
    if v is None:
        return NA
    return CRIT if v >= crit else WARN if v >= warn else OK


def _ping_text(s: Snapshot) -> str:
    if s.ping_pending:
        return "..."
    if s.ping_ms is None:
        return "offline"
    return f"{s.ping_ms:.0f} ms"


def _ping_parts(s: Snapshot) -> Parts:
    if s.ping_pending:
        return [("--", "")]
    if s.ping_ms is None:
        return [("Off", "")]
    return [(f"{s.ping_ms:.0f}", "ms")]


def _net_level(s: Snapshot) -> str:
    if s.ping_pending:
        return NA
    if s.ping_ms is None:
        return CRIT
    return CRIT if s.ping_ms >= 300 else WARN if s.ping_ms >= 100 else OK


def _temp_text(s: Snapshot) -> str:
    return "n/a" if s.cpu_temp_c is None else f"{s.cpu_temp_c:.0f}°C"


def _temp_parts(s: Snapshot) -> Parts:
    return [("--", "")] if s.cpu_temp_c is None else [(f"{s.cpu_temp_c:.0f}", "°")]


def _pct(v: Optional[float]) -> Optional[float]:
    return None if v is None else max(0.0, min(1.0, v / 100.0))


def _pct_parts(v: Optional[float]) -> Parts:
    return [("--", "")] if v is None else [(f"{v:.0f}", "%")]


_METRIC_LIST = [
    Metric("cpu", "CPU", "CPU", lambda s: s.cpu_percent,
           lambda s: f"{s.cpu_percent:.0f}%", lambda s: _pct_level(s.cpu_percent, 70, 90),
           icon="cpu", accent="blue", parts=lambda s: _pct_parts(s.cpu_percent),
           fraction=lambda s: _pct(s.cpu_percent), series="cpu", chart_range=(0.0, 100.0)),
    Metric("temp", "CPU Temperature", "T", lambda s: s.cpu_temp_c,
           _temp_text, lambda s: _pct_level(s.cpu_temp_c, 75, 90),
           icon="thermometer", accent="orange", parts=_temp_parts,
           fraction=lambda s: None if s.cpu_temp_c is None else max(0.0, min(1.0, (s.cpu_temp_c - 30) / 70.0)),
           series="temp", chart_range=(30.0, 100.0), short_label="Temp"),
    Metric("ram", "Memory", "RAM", lambda s: s.ram_percent,
           lambda s: f"{s.ram_percent:.0f}%", lambda s: _pct_level(s.ram_percent, 75, 90),
           icon="memory", accent="purple", parts=lambda s: _pct_parts(s.ram_percent),
           fraction=lambda s: _pct(s.ram_percent), series="ram", chart_range=(0.0, 100.0)),
    Metric("swap", "Swap", "Swap", lambda s: s.swap_percent,
           lambda s: f"{s.swap_percent:.0f}%", lambda s: _pct_level(s.swap_percent, 50, 80),
           icon="memory", accent="pink", parts=lambda s: _pct_parts(s.swap_percent),
           fraction=lambda s: _pct(s.swap_percent), series="swap", chart_range=(0.0, 100.0)),
    Metric("disk", "Disk", "SSD", lambda s: s.disk_percent,
           lambda s: f"{s.disk_percent:.0f}%", lambda s: _pct_level(s.disk_percent, 80, 95),
           icon="disk", accent="teal", parts=lambda s: _pct_parts(s.disk_percent),
           fraction=lambda s: _pct(s.disk_percent), series="disk", chart_range=(0.0, 100.0)),
    Metric("ping", "Ping", "Ping", lambda s: s.ping_ms,
           _ping_text, _net_level,
           icon="ping", accent="green", parts=_ping_parts,
           fraction=lambda s: None if s.ping_ms is None else max(0.0, min(1.0, s.ping_ms / 300.0)),
           series="ping", chart_range=(0.0, None)),
    Metric("net_down", "Download", "↓", lambda s: s.net_down_bps,
           lambda s: fmt_rate(s.net_down_bps), lambda s: OK,
           icon="network", accent="blue", parts=lambda s: [split_rate(s.net_down_bps)],
           adaptive=True, series="net_down", chart_range=(0.0, None), short_label="Down"),
    Metric("net_up", "Upload", "↑", lambda s: s.net_up_bps,
           lambda s: fmt_rate(s.net_up_bps), lambda s: OK,
           icon="network", accent="green", parts=lambda s: [split_rate(s.net_up_bps)],
           adaptive=True, series="net_up", chart_range=(0.0, None), short_label="Up"),
    Metric("battery", "Battery", "Bat", lambda s: s.battery_percent,
           lambda s: "n/a" if s.battery_percent is None else f"{s.battery_percent:.0f}%",
           lambda s: NA if s.battery_percent is None
           else (CRIT if s.battery_percent <= 10 else WARN if s.battery_percent <= 20 else OK),
           icon="battery", accent="green", parts=lambda s: _pct_parts(s.battery_percent),
           fraction=lambda s: _pct(s.battery_percent), series="battery", chart_range=(0.0, 100.0)),
    Metric("uptime", "Uptime", "Up", lambda s: s.uptime_s,
           lambda s: fmt_uptime(s.uptime_s), lambda s: OK,
           icon="clock", accent="indigo", parts=lambda s: uptime_parts(s.uptime_s)),
]

METRICS: Dict[str, Metric] = {m.id: m for m in _METRIC_LIST}

DEFAULT_TRAY: List[str] = ["cpu", "temp", "ping"]


def metric_fraction(metric: Metric, snap: Snapshot, series: Optional[List[Optional[float]]] = None) -> Optional[float]:
    """0..1 fill level for rings / bars. Rate-like metrics scale against their recent peak."""
    if metric.adaptive:
        value = metric.value(snap) or 0.0
        peak = max([v for v in (series or []) if v is not None] + [value, 1024.0 * 1024.0])
        return max(0.0, min(1.0, value / peak))
    return metric.fraction(snap) if metric.fraction else None


def tray_text(snap: Snapshot, metric_ids: List[str], sep: str = "  ") -> str:
    """Compact one-line readout, e.g. ``CPU 12%  T 54°C  Ping 18 ms``."""
    parts = []
    for mid in metric_ids:
        m = METRICS.get(mid)
        if m:
            parts.append(f"{m.short} {m.text(snap)}")
    return sep.join(parts)


def worst_level(snap: Snapshot, metric_ids: List[str]) -> str:
    order = {NA: 0, OK: 1, WARN: 2, CRIT: 3}
    worst = NA
    for mid in metric_ids:
        m = METRICS.get(mid)
        if m:
            lv = m.level(snap)
            if order[lv] > order[worst]:
                worst = lv
    return worst
