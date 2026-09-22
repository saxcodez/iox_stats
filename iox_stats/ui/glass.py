"""Glass look: card surfaces, soft shadows, simulated backdrop, and native blur where available.

* macOS: real blur-behind via ``NSVisualEffectView`` (needs the optional ``pyobjc-framework-Cocoa``).
* Everywhere else (or if that fails): a simulated soft-colour backdrop so the translucent cards
  still read as glass. Set ``IOX_STATS_NO_NATIVE_BLUR=1`` to force the simulated backdrop.
"""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QRadialGradient

from .shapes import squircle_path
from .theme import Theme

RADIUS = 22.0     # iOS small-widget corner radius (continuous corners)


# ----------------------------------------------------------------- backdrop
def paint_backdrop(p: QPainter, rect: QRectF, theme: Theme, native: bool) -> None:
    """Window background. With native blur only a light tint is painted (the OS blurs behind us)."""
    if native:
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(rect, theme.native_tint)
        p.restore()
        return
    p.fillRect(rect, theme.backdrop_base)
    w, h = rect.width(), rect.height()
    scale = max(w, h)
    for bx, by, br, color in theme.backdrop_blobs:
        center = QPointF(rect.left() + bx * w, rect.top() + by * h)
        grad = QRadialGradient(center, br * scale)
        c0, c1 = QColor(color), QColor(color)
        c1.setAlpha(0)
        grad.setColorAt(0, c0)
        grad.setColorAt(1, c1)
        p.fillRect(rect, grad)


# --------------------------------------------------------------------- card
def paint_glass_card(p: QPainter, rect: QRectF, theme: Theme, radius: float = RADIUS) -> None:
    """One glass widget surface: shadow, translucent body, top gloss, specular rim, hairline."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # soft ambient shadow (layered squircles, cheap and resolution independent)
    steps = 7
    for i in range(steps, 0, -1):
        grow = i * 1.15
        a = int(theme.shadow_alpha * (1 - i / (steps + 1)) ** 2.4 / 2.4)
        if a <= 0:
            continue
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, a))
        p.drawPath(squircle_path(rect.adjusted(-grow, -grow + 2.5, grow, grow + 2.5), radius + grow))

    body = squircle_path(rect, radius)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.glass_fill)
    p.drawPath(body)

    # gloss: light falling on the top half
    gloss = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.62))
    top = QColor(theme.glass_gloss)
    bottom = QColor(theme.glass_gloss)
    bottom.setAlpha(0)
    gloss.setColorAt(0, top)
    gloss.setColorAt(1, bottom)
    p.setBrush(gloss)
    p.drawPath(body)

    # specular rim: bright at the top-left, fading to the bottom-right
    rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
    rim.setColorAt(0, theme.rim_start)
    rim.setColorAt(0.5, QColor(theme.rim_end.red(), theme.rim_end.green(), theme.rim_end.blue(),
                               (theme.rim_start.alpha() + theme.rim_end.alpha()) // 3))
    rim.setColorAt(1, theme.rim_end)
    p.setPen(QPen(QBrush(rim), 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(squircle_path(rect.adjusted(0.6, 0.6, -0.6, -0.6), radius - 0.6))

    p.setPen(QPen(theme.hairline, 0.8))
    p.drawPath(squircle_path(rect.adjusted(-0.4, -0.4, 0.4, 0.4), radius + 0.4))
    p.restore()


# ------------------------------------------------------------- native blur
def native_blur_supported() -> bool:
    if os.environ.get("IOX_STATS_NO_NATIVE_BLUR"):
        return False
    if sys.platform != "darwin":
        return False
    try:
        import objc  # noqa: F401
        from AppKit import NSVisualEffectView  # noqa: F401
    except Exception:
        return False
    return True


def apply_native_blur(widget, theme_setting: str = "system") -> bool:
    """Insert an NSVisualEffectView behind the Qt content view (macOS). Returns success."""
    if not native_blur_supported():
        return False
    try:
        import objc
        from AppKit import NSColor, NSVisualEffectView

        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
        window = view.window()
        if window is None:
            return False
        effect = NSVisualEffectView.alloc().initWithFrame_(view.bounds())
        effect.setAutoresizingMask_(2 | 16)          # width + height sizable
        effect.setBlendingMode_(0)                   # behind window
        effect.setState_(1)                          # always active
        effect.setMaterial_(21)                      # under-window background
        superview = view.superview()
        if superview is None:
            return False
        superview.addSubview_positioned_relativeTo_(effect, -1, view)   # NSWindowBelow
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.clearColor())
        set_native_appearance(window, theme_setting)
        widget._iox_effect_window = window
        return True
    except Exception:
        return False


def set_native_appearance(window, theme_setting: str) -> None:
    """Force the blur material to light/dark when the user overrides the system appearance."""
    try:
        from AppKit import NSAppearance

        if theme_setting == "dark":
            window.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        elif theme_setting == "light":
            window.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
        else:
            window.setAppearance_(None)
    except Exception:
        pass


def set_desktop_behavior(widget, enabled: bool) -> bool:
    """macOS: keep the window on every Space, out of Cmd-Tab / Mission Control cycling and behind other windows."""
    if sys.platform != "darwin":
        return False
    try:
        import objc

        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
        window = view.window()
        if window is None:
            return False
        # NSWindowCollectionBehavior: CanJoinAllSpaces = 1, Stationary = 16, IgnoresCycle = 64
        window.setCollectionBehavior_((1 | 16 | 64) if enabled else 0)
        window.setHasShadow_(not enabled)
        return True
    except Exception:
        return False
