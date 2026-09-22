"""Apple-style themes: iOS/macOS system colours, label hierarchy and glass parameters.

Colour values are Apple's documented system colours (Human Interface Guidelines) for the
light and dark appearance, including the alpha-based label colours (primary / secondary /
tertiary) that let text stay readable on translucent glass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from ..metrics import CRIT, NA, OK, WARN


def _c(r: int, g: int, b: int, a: int = 255) -> QColor:
    return QColor(r, g, b, a)


@dataclass(frozen=True)
class Theme:
    name: str
    is_dark: bool
    # labels
    label: QColor
    label2: QColor          # secondary label
    label3: QColor          # tertiary label
    fill: QColor            # systemFill - tracks, empty bars
    # system colours
    colors: Dict[str, QColor]
    # glass
    glass_fill: QColor      # card body
    glass_gloss: QColor     # top highlight start colour
    rim_start: QColor       # specular rim, top-left
    rim_end: QColor         # specular rim, bottom-right
    hairline: QColor        # thin outer edge
    shadow_alpha: int
    # backdrop used when there is no native blur
    backdrop_base: QColor
    backdrop_blobs: tuple = field(default_factory=tuple)   # (x, y, radius, QColor) in 0..1 units
    native_tint: QColor = field(default_factory=lambda: QColor(0, 0, 0, 0))

    def color(self, name: str) -> QColor:
        return QColor(self.colors.get(name, self.colors["blue"]))

    def level_color(self, level: str, accent: str = "blue") -> QColor:
        """Accent while everything is fine, system orange / red when it needs attention."""
        if level == WARN:
            return self.color("orange")
        if level == CRIT:
            return self.color("red")
        if level == NA:
            return QColor(self.label2)
        return self.color(accent)


LIGHT = Theme(
    name="light",
    is_dark=False,
    label=_c(0, 0, 0),
    label2=_c(60, 60, 67, 153),
    label3=_c(60, 60, 67, 77),
    fill=_c(120, 120, 128, 51),
    colors={
        "blue": _c(0, 122, 255), "green": _c(52, 199, 89), "orange": _c(255, 149, 0),
        "red": _c(255, 59, 48), "purple": _c(175, 82, 222), "teal": _c(48, 176, 199),
        "indigo": _c(88, 86, 214), "pink": _c(255, 45, 85), "yellow": _c(255, 204, 0),
        "cyan": _c(50, 173, 230), "mint": _c(0, 199, 190), "gray": _c(142, 142, 147),
    },
    glass_fill=_c(255, 255, 255, 150),
    glass_gloss=_c(255, 255, 255, 120),
    rim_start=_c(255, 255, 255, 235),
    rim_end=_c(255, 255, 255, 60),
    hairline=_c(0, 0, 0, 20),
    shadow_alpha=34,
    backdrop_base=_c(226, 232, 245),
    backdrop_blobs=(
        (0.10, 0.05, 0.60, _c(120, 165, 255, 170)),
        (0.95, 0.25, 0.55, _c(200, 160, 255, 150)),
        (0.30, 0.95, 0.60, _c(255, 190, 150, 150)),
        (0.85, 0.90, 0.45, _c(150, 225, 230, 130)),
    ),
    native_tint=_c(255, 255, 255, 40),
)

DARK = Theme(
    name="dark",
    is_dark=True,
    label=_c(255, 255, 255),
    label2=_c(235, 235, 245, 153),
    label3=_c(235, 235, 245, 77),
    fill=_c(120, 120, 128, 92),
    colors={
        "blue": _c(10, 132, 255), "green": _c(48, 209, 88), "orange": _c(255, 159, 10),
        "red": _c(255, 69, 58), "purple": _c(191, 90, 242), "teal": _c(64, 200, 224),
        "indigo": _c(94, 92, 230), "pink": _c(255, 55, 95), "yellow": _c(255, 214, 10),
        "cyan": _c(100, 210, 255), "mint": _c(99, 230, 226), "gray": _c(152, 152, 157),
    },
    glass_fill=_c(255, 255, 255, 26),
    glass_gloss=_c(255, 255, 255, 34),
    rim_start=_c(255, 255, 255, 105),
    rim_end=_c(255, 255, 255, 14),
    hairline=_c(0, 0, 0, 110),
    shadow_alpha=90,
    backdrop_base=_c(12, 12, 22),
    backdrop_blobs=(
        (0.10, 0.05, 0.65, _c(60, 60, 170, 190)),
        (0.95, 0.30, 0.55, _c(120, 50, 160, 160)),
        (0.25, 0.95, 0.60, _c(20, 110, 140, 150)),
        (0.90, 0.95, 0.45, _c(150, 60, 90, 110)),
    ),
    native_tint=_c(0, 0, 0, 50),
)


def system_is_dark() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return False
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # Qt < 6.5
        return QGuiApplication.palette().window().color().lightness() < 128


def resolve_theme(setting: str) -> Theme:
    if setting == "dark":
        return DARK
    if setting == "light":
        return LIGHT
    return DARK if system_is_dark() else LIGHT
