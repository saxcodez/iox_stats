"""System typography: SF Pro on macOS/iOS look, Segoe UI Variable on Windows, system font elsewhere.

We never bundle or hard-code a foreign font: ``QFont()`` resolves to the platform UI font
(San Francisco on macOS). Hero numbers use the rounded design where the platform provides it
(``SF Pro Rounded``), tabular figures avoid jitter while values change.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont

W_REGULAR = QFont.Weight.Normal
W_MEDIUM = QFont.Weight.Medium
W_SEMIBOLD = QFont.Weight.DemiBold
W_BOLD = QFont.Weight.Bold


def _base_families(rounded: bool):
    if sys.platform == "darwin":
        if rounded:
            return [".AppleSystemUIFontRounded", "SF Pro Rounded", ".AppleSystemUIFont"]
        return [".AppleSystemUIFont"]
    if sys.platform.startswith("win"):
        return ["Segoe UI Variable Display", "Segoe UI"]
    return []


def ui_font(px: float, weight=W_REGULAR, rounded: bool = False, tracking: float = 0.0) -> QFont:
    f = QFont()
    fams = _base_families(rounded)
    if fams:
        f.setFamilies(fams)
    f.setPixelSize(max(1, int(round(px))))
    f.setWeight(weight)
    if hasattr(f, "setFeature"):
        try:
            f.setFeature(QFont.Tag("tnum"), 1)   # tabular numbers
        except Exception:
            pass
    if tracking:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    return f


# type scale (px == pt on macOS/iOS): matches the iOS widget text styles
TITLE = 13        # widget title: semibold
CAPTION = 12      # secondary lines
HERO = 34         # main number
HERO_UNIT = 17
