"""Widget layout model: which widgets exist, how big they are, how they look and what they show.

Pure logic (no Qt) so it can be tested and reused by the menus, the dashboard and the settings file.

* ``size``   - ``small`` (1x1 iOS unit) or ``medium`` (2x1)
* ``style``  - ``detail`` (rich, metric specific), ``rings``, ``bars`` or ``numbers``
* ``metrics`` - what the widget shows; the number is limited by what fits (see ``CAPACITY``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .metrics import METRICS

SIZES = ("small", "medium")
STYLES = ("detail", "rings", "bars", "numbers")
MAX_WIDGETS = 12

SIZE_LABELS = {"small": "Small", "medium": "Medium"}
STYLE_LABELS = {"detail": "Detailed", "rings": "Rings", "bars": "Bars", "numbers": "Numbers only"}

# How many values fit into a widget, by (size, style).
CAPACITY: Dict[Tuple[str, str], int] = {
    ("small", "detail"): 1, ("medium", "detail"): 2,
    ("small", "rings"): 2, ("medium", "rings"): 4,
    ("small", "bars"): 3, ("medium", "bars"): 4,
    ("small", "numbers"): 3, ("medium", "numbers"): 6,
}


def capacity(size: str, style: str) -> int:
    return CAPACITY.get((size, style), 1)


@dataclass(frozen=True)
class WidgetConfig:
    size: str = "small"
    style: str = "detail"
    metrics: Tuple[str, ...] = ("cpu",)

    # -- derived ---------------------------------------------------------------
    @property
    def capacity(self) -> int:
        return capacity(self.size, self.style)

    @property
    def cols(self) -> int:
        return 2 if self.size == "medium" else 1

    def title(self) -> str:
        names = [METRICS[m].label for m in self.metrics if m in METRICS]
        return ", ".join(names) if names else "Empty"

    def describe(self) -> str:
        return f"{self.title()} · {SIZE_LABELS[self.size]}, {STYLE_LABELS[self.style]}"

    # -- (de)serialisation -----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {"size": self.size, "style": self.style, "metrics": list(self.metrics)}

    @classmethod
    def from_dict(cls, raw: Any) -> "WidgetConfig":
        if not isinstance(raw, dict):
            return cls()
        size = raw.get("size") if raw.get("size") in SIZES else "small"
        style = raw.get("style") if raw.get("style") in STYLES else "detail"
        seen: List[str] = []
        for m in raw.get("metrics") or []:
            if isinstance(m, str) and m in METRICS and m not in seen:
                seen.append(m)
        seen = seen[:capacity(size, style)] or ["cpu"]
        return cls(size, style, tuple(seen))

    # -- edits (always return a valid config) ---------------------------------
    def with_size(self, size: str) -> "WidgetConfig":
        return WidgetConfig.from_dict({**self.to_dict(), "size": size})

    def with_style(self, style: str) -> "WidgetConfig":
        return WidgetConfig.from_dict({**self.to_dict(), "style": style})

    def can_add(self, metric_id: str) -> bool:
        return metric_id in METRICS and metric_id not in self.metrics and len(self.metrics) < self.capacity

    def can_remove(self, metric_id: str) -> bool:
        return metric_id in self.metrics and len(self.metrics) > 1     # a widget always shows something

    def toggled(self, metric_id: str) -> Optional["WidgetConfig"]:
        """Config with ``metric_id`` switched on/off, or None if the limit / minimum forbids it."""
        if metric_id in self.metrics:
            if not self.can_remove(metric_id):
                return None
            return WidgetConfig(self.size, self.style, tuple(m for m in self.metrics if m != metric_id))
        if not self.can_add(metric_id):
            return None
        return WidgetConfig(self.size, self.style, self.metrics + (metric_id,))


Layout = List[WidgetConfig]


def W(size: str, style: str, *metrics: str) -> WidgetConfig:
    return WidgetConfig.from_dict({"size": size, "style": style, "metrics": list(metrics)})


DEFAULT_LAYOUT: Layout = [
    W("small", "detail", "cpu"),
    W("small", "detail", "ram"),
    W("small", "detail", "temp"),
    W("small", "detail", "disk"),
    W("medium", "detail", "net_down", "net_up"),
    W("medium", "detail", "ping"),
    W("medium", "detail", "cpu"),          # per-core capsules
    W("small", "detail", "uptime"),
    W("small", "detail", "battery"),
]

PRESETS: Dict[str, Layout] = {
    "detailed": DEFAULT_LAYOUT,
    "rings": [
        W("small", "rings", "cpu", "ram"),
        W("small", "rings", "temp", "disk"),
        W("medium", "rings", "cpu", "ram", "disk", "temp"),
        W("medium", "detail", "ping"),
        W("small", "rings", "battery", "swap"),
        W("small", "detail", "uptime"),
    ],
    "bars": [
        W("small", "bars", "cpu", "ram", "disk"),
        W("small", "bars", "temp", "ping", "battery"),
        W("medium", "bars", "cpu", "ram", "disk", "temp"),
        W("medium", "bars", "net_down", "net_up", "ping"),
    ],
    "numbers": [
        W("small", "numbers", "cpu", "ram", "temp"),
        W("small", "numbers", "disk", "ping", "uptime"),
        W("medium", "numbers", "cpu", "ram", "temp", "disk", "net_down", "net_up"),
        W("medium", "numbers", "ping", "battery", "swap", "uptime"),
    ],
    "mixed": [
        W("small", "rings", "cpu", "ram"),
        W("small", "detail", "temp"),
        W("small", "bars", "disk", "swap", "battery"),
        W("small", "numbers", "ping", "uptime", "net_down"),
        W("medium", "detail", "net_down", "net_up"),
        W("medium", "bars", "cpu", "ram", "disk", "temp"),
    ],
}
PRESET_LABELS = {"detailed": "Detailed", "rings": "Rings", "bars": "Bars", "numbers": "Numbers only", "mixed": "Mixed"}


def sanitize_layout(raw: Any) -> Layout:
    """Turn whatever is in settings.json into a valid layout (falls back to the default)."""
    if not isinstance(raw, list) or not raw:
        return list(DEFAULT_LAYOUT)
    return [WidgetConfig.from_dict(item) for item in raw[:MAX_WIDGETS]]


def layout_to_raw(layout: Iterable[WidgetConfig]) -> List[Dict[str, Any]]:
    return [w.to_dict() for w in layout]


def total_columns_used(layout: Layout, columns: int = 4) -> int:
    """Number of grid rows the layout needs (used for sizing checks)."""
    row, col = 1, 0
    for w in layout:
        if col + w.cols > columns:
            row, col = row + 1, 0
        col += w.cols
    return row


# ---------------------------------------------------------------- store
_ADD_ORDER = ["cpu", "ram", "temp", "disk", "ping", "net_down", "net_up", "battery", "swap", "uptime"]


class LayoutStore:
    """Holds the live layout, persists it through ``settings`` and tells listeners about changes.

    ``settings`` is anything with a ``widgets`` list attribute and a ``save()`` method.
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self._listeners: List[Any] = []

    @property
    def layout(self) -> Layout:
        return sanitize_layout(self.settings.widgets)

    def subscribe(self, fn) -> None:
        self._listeners.append(fn)

    def set_layout(self, layout: Iterable[WidgetConfig]) -> None:
        layout = list(layout)[:MAX_WIDGETS] or list(DEFAULT_LAYOUT)
        self.settings.widgets = layout_to_raw(layout)
        self.settings.save()
        for fn in list(self._listeners):
            fn(layout)

    # single-widget edits -------------------------------------------------
    def update(self, index: int, cfg: Optional[WidgetConfig]) -> bool:
        layout = self.layout
        if cfg is None or not 0 <= index < len(layout) or layout[index] == cfg:
            return False
        layout[index] = cfg
        self.set_layout(layout)
        return True

    def remove(self, index: int) -> bool:
        layout = self.layout
        if len(layout) <= 1 or not 0 <= index < len(layout):
            return False
        del layout[index]
        self.set_layout(layout)
        return True

    def move(self, index: int, delta: int) -> bool:
        layout = self.layout
        j = index + delta
        if not (0 <= index < len(layout) and 0 <= j < len(layout)):
            return False
        layout[index], layout[j] = layout[j], layout[index]
        self.set_layout(layout)
        return True

    def add(self, size: str, style: str) -> bool:
        layout = self.layout
        if len(layout) >= MAX_WIDGETS:
            return False
        used = {m for w in layout for m in w.metrics}
        pool = [m for m in _ADD_ORDER if m not in used] + [m for m in _ADD_ORDER if m in used]
        layout.append(W(size, style, *pool[:capacity(size, style)]))
        self.set_layout(layout)
        return True

    def apply_preset(self, name: str) -> bool:
        if name not in PRESETS:
            return False
        self.set_layout(PRESETS[name])
        return True

    def reset(self) -> None:
        self.set_layout(DEFAULT_LAYOUT)
