"""Native macOS menu bar item (NSStatusItem) with real text.

Why: Qt's ``QSystemTrayIcon`` squeezes every icon into a square of about 18 pt on macOS. A wide picture
with ``CPU 12%  T 54°C  Ping 18 ms`` therefore ends up tiny and cramped. A native status item shows
the text in the system menu bar font, crisp, at the right size and with the right colours in light and
dark menu bars - exactly like Apple's own items.

Needs ``pyobjc-framework-Cocoa`` (installed by requirements.txt on macOS). If it is missing or anything
fails, the caller falls back to ``QSystemTrayIcon`` (see ``TrayController``).
"""

from __future__ import annotations

import os
import sys
from typing import Callable, List, Optional, Tuple

Segment = Tuple[str, str, str]      # (label, value, level)  level: ok / warn / crit / na

MENU_BAR_FONT_SIZE = 13             # points; the system menu bar font size
LABEL_FONT_SIZE = 10


def native_available() -> bool:
    """True on macOS when pyobjc's AppKit can be imported and it is not switched off."""
    if sys.platform != "darwin" or os.environ.get("IOX_STATS_NO_NATIVE_STATUSITEM"):
        return False
    try:
        import AppKit  # noqa: F401
        import objc  # noqa: F401
    except Exception:
        return False
    return True


_TARGET_CLASS = None


def _click_target_class():
    """Objective-C object that receives the click (created once - ObjC classes cannot be redefined)."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        import objc
        from Foundation import NSObject

        class IOXStatusClickTarget(NSObject):
            def initWithCallback_(self, callback):
                self = objc.super(IOXStatusClickTarget, self).init()
                if self is None:
                    return None
                self._callback = callback
                return self

            @objc.IBAction
            def clicked_(self, _sender):
                self._callback()

        _TARGET_CLASS = IOXStatusClickTarget
    return _TARGET_CLASS


class CocoaStatusItem:
    """Thin wrapper around one NSStatusItem. Every method is safe to call; failures raise on creation only."""

    def __init__(self, on_click: Callable[[], None]):
        from AppKit import NSStatusBar, NSVariableStatusItemLength

        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self._target = _click_target_class().alloc().initWithCallback_(on_click)   # keep a reference!
        button = self._item.button()
        button.setTarget_(self._target)
        button.setAction_("clicked:")
        self._button = button

    # -- content -------------------------------------------------------------
    def set_segments(self, segments: List[Segment]) -> None:
        from AppKit import (NSColor, NSFont, NSFontAttributeName, NSFontWeightMedium, NSFontWeightRegular,
                            NSForegroundColorAttributeName)
        from Foundation import NSAttributedString, NSMutableAttributedString

        level_color = {
            "warn": NSColor.systemOrangeColor(),
            "crit": NSColor.systemRedColor(),
        }
        value_font = NSFont.monospacedDigitSystemFontOfSize_weight_(MENU_BAR_FONT_SIZE, NSFontWeightMedium)
        label_font = NSFont.systemFontOfSize_weight_(LABEL_FONT_SIZE, NSFontWeightRegular)

        out = NSMutableAttributedString.alloc().init()

        def add(text: str, font, color) -> None:
            attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: color}
            out.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(text, attrs))

        for i, (label, value, level) in enumerate(segments):
            if i:
                add("   ", value_font, NSColor.labelColor())
            add(label + (" " if value else ""), label_font, NSColor.secondaryLabelColor())
            if value:
                add(value, value_font, level_color.get(level, NSColor.labelColor()))
        self._button.setAttributedTitle_(out)

    def set_tooltip(self, text: str) -> None:
        self._button.setToolTip_(text)

    # -- geometry (for popping the Qt menu right below the item) ----------------
    def anchor(self) -> Optional[Tuple[float, float]]:
        """Bottom-left corner of the item in Cocoa screen coordinates (origin bottom-left), or None."""
        try:
            frame = self._button.window().frame()
            return float(frame.origin.x), float(frame.origin.y)
        except Exception:
            return None

    def remove(self) -> None:
        try:
            from AppKit import NSStatusBar

            NSStatusBar.systemStatusBar().removeStatusItem_(self._item)
        except Exception:
            pass


def create_status_item(on_click: Callable[[], None]) -> Optional[CocoaStatusItem]:
    """A native status item, or None when not on macOS / pyobjc missing / creation failed."""
    if not native_available():
        return None
    try:
        return CocoaStatusItem(on_click)
    except Exception:
        return None
