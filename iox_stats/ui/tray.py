"""Menu bar (macOS) / system tray (Windows, Linux) readout.

macOS and most Linux panels can show a wide icon, so we render live text such as
``CPU 12%  T 54°C  Ping 18 ms`` into the icon. Windows tray icons are tiny (16-32 px),
so there we render a compact ring with the first metric and put the rest in the tooltip.
"""

from __future__ import annotations

import sys
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QPoint, QRectF, QTimer, Qt
from PySide6.QtGui import (QAction, QActionGroup, QCursor, QDesktopServices, QFontMetrics, QGuiApplication, QIcon,
                           QPainter, QPixmap)
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import __app_name__, __github_url__, __version__
from ..autostart import Autostart
from ..collectors import Snapshot
from ..layout import LayoutStore
from ..metrics import METRICS, NA, OK
from ..settings import MAX_TRAY_METRICS, Settings
from .theme import DARK, LIGHT, Theme, resolve_theme
from .fonts import W_MEDIUM, W_SEMIBOLD, ui_font
from .macos_status import create_status_item
from .widget_menu import populate_widgets_menu
from .widgets import draw_activity_ring

ROTATE_INTERVAL_MS = 4000   # how long one value stays visible when rotation is on
_SCALE = 2  # render @2x for crisp menu bar text


def effective_style(setting: str) -> str:
    if setting in ("text", "compact"):
        return setting
    return "compact" if sys.platform.startswith("win") else "text"


def tray_segments(snap: Snapshot, metric_ids: List[str]) -> List[Tuple[str, str, str]]:
    """``(label, value, level)`` for every menu bar value, e.g. ``("CPU", "12%", "ok")``."""
    items = []
    for mid in metric_ids:
        m = METRICS.get(mid)
        if m:
            items.append((m.short, m.text(snap), m.level(snap)))
    return items or [("IOX", "", OK)]


def render_text_icon(snap: Snapshot, metric_ids: List[str], theme: Theme, height: int = 22) -> QPixmap:
    """Wide pixmap with ``LABEL value`` pairs (Linux panels). macOS uses a native status item instead."""
    h = height * _SCALE
    font = ui_font(13 * _SCALE, W_SEMIBOLD)
    small = ui_font(11 * _SCALE, W_MEDIUM)
    fm, fs = QFontMetrics(font), QFontMetrics(small)

    items = tray_segments(snap, metric_ids)

    pad, gap, inner = 6 * _SCALE, 10 * _SCALE, 4 * _SCALE
    widths = [fs.horizontalAdvance(lab) + (inner + fm.horizontalAdvance(val) if val else 0) for lab, val, _ in items]
    total = pad * 2 + sum(widths) + gap * (len(items) - 1)

    pm = QPixmap(int(total), int(h))
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(1.0)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    x = pad
    base = int(h / 2 + fm.ascent() / 2 - 2 * _SCALE)
    for (lab, val, level), w in zip(items, widths):
        p.setFont(small)
        p.setPen(theme.label2)
        p.drawText(int(x), base, lab)
        x += fs.horizontalAdvance(lab)
        if val:
            x += inner
            p.setFont(font)
            p.setPen(theme.label if level in (OK, NA) else theme.level_color(level, "blue"))
            p.drawText(int(x), base, val)
            x += fm.horizontalAdvance(val)
        x += gap
    p.end()
    return pm


def render_compact_icon(snap: Snapshot, metric_ids: List[str], theme: Theme, size: int = 32) -> QPixmap:
    """Small square icon: status ring + first metric's number."""
    s = size * _SCALE
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    m = METRICS.get(metric_ids[0]) if metric_ids else None
    level = m.level(snap) if m else NA
    color = theme.level_color(level, "blue")
    frac = 1.0
    if m and m.id in ("cpu", "ram", "disk", "battery", "temp"):
        v = m.value(snap)
        frac = (v / 100.0) if v is not None else 0.0
    draw_activity_ring(p, QRectF(2, 2, s - 4, s - 4), frac, color, width=s * 0.16)
    if m:
        text = m.text(snap).split(" ")[0].replace("%", "").replace("°C", "")
        p.setFont(ui_font(s * (0.42 if len(text) <= 2 else 0.32), W_SEMIBOLD, rounded=True))
        p.setPen(theme.label)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return pm


def render_tray_pixmap(snap: Snapshot, metric_ids: List[str], theme: Theme, style: str) -> QPixmap:
    if effective_style(style) == "compact":
        return render_compact_icon(snap, metric_ids, theme)
    return render_text_icon(snap, metric_ids, theme)


class TrayController:
    """Owns the QSystemTrayIcon, its menu, and keeps the icon text live."""

    def __init__(self, settings: Settings, on_toggle_dashboard: Callable[[], None],
                 on_settings_changed: Callable[[], None], on_quit: Callable[[], None],
                 autostart: Optional[Autostart] = None, store: Optional[LayoutStore] = None,
                 native_factory: Callable = create_status_item, helper_setup=None,
                 on_desktop_mode: Optional[Callable[[bool], None]] = None):
        self.settings = settings
        self.helper_setup = helper_setup
        self._on_desktop_mode = on_desktop_mode
        self.store = store
        self.autostart = autostart or Autostart()
        self._on_toggle = on_toggle_dashboard
        self._on_changed = on_settings_changed
        self.icon = QSystemTrayIcon()
        self.menu = QMenu()
        self.metric_actions = {}
        self._rotate_index = 0
        self._rotate_timer = QTimer()
        self._rotate_timer.setInterval(ROTATE_INTERVAL_MS)
        self._rotate_timer.timeout.connect(self._rotate_tick)
        self._build_menu(on_quit)
        self._last_snap = Snapshot()
        if self.settings.tray_rotate:
            self._rotate_timer.start()

        # macOS: a native status item shows real, readable text. Qt's tray icon would squeeze it into a square.
        self.native = None
        if effective_style(settings.tray_style) == "text":
            self.native = native_factory(self._show_menu)
        self.available = self.native is not None or QSystemTrayIcon.isSystemTrayAvailable()
        if self.native is not None:
            self.native.set_segments(tray_segments(self._last_snap, self._display_ids()))
        else:
            self.icon.setContextMenu(self.menu)
            self.icon.activated.connect(self._activated)
            self.icon.setIcon(QIcon(render_tray_pixmap(self._last_snap, self._display_ids(),
                                                       resolve_theme(settings.theme), self._pixmap_style())))

    def _pixmap_style(self) -> str:
        """Style for the Qt tray icon. On macOS a wide icon is unreadable there, so use the square ring."""
        style = effective_style(self.settings.tray_style)
        if style == "text" and sys.platform == "darwin":
            return "compact"
        return style

    def _show_menu(self) -> None:
        """Open the menu right below the native status item."""
        pos = QCursor.pos()
        anchor = self.native.anchor() if self.native is not None else None
        if anchor is not None:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:      # Cocoa: origin bottom-left; Qt: top-left of the primary screen
                pos = QPoint(int(anchor[0]), int(screen.geometry().height() - anchor[1]))
        self.menu.popup(pos)

    # menu ---------------------------------------------------------------
    def _build_menu(self, on_quit: Callable[[], None]) -> None:
        header = QAction(f"{__app_name__} v{__version__}", self.menu)
        header.setEnabled(False)
        self.menu.addAction(header)
        show = QAction("Show Dashboard", self.menu)
        show.triggered.connect(self._on_toggle)
        self.menu.addAction(show)
        self.menu.addSeparator()

        sub = self.menu.addMenu(f"Menu bar values (max. {MAX_TRAY_METRICS})")
        for mid, m in METRICS.items():
            act = QAction(m.label, sub, checkable=True)
            act.setChecked(mid in self.settings.tray_metrics)
            act.toggled.connect(lambda checked, mid=mid: self.set_metric_enabled(mid, checked))
            sub.addAction(act)
            self.metric_actions[mid] = act
        sub.addSeparator()
        self.rotate_action = QAction("Rotate through the values", sub, checkable=True)
        self.rotate_action.setChecked(self.settings.tray_rotate)
        self.rotate_action.setToolTip("Show one value at a time, cycling every few seconds - takes less "
                                      "space next to your other menu bar icons.")
        self.rotate_action.toggled.connect(self.set_rotate)
        sub.addAction(self.rotate_action)

        if self.store is not None:
            self.widgets_menu = self.menu.addMenu("Widgets")
            populate_widgets_menu(self.widgets_menu, self.store)
            # Rebuild when the layout changes (not while the menu opens - native macOS menus ignore that).
            # Deferred, because the change usually comes from an item of this very menu.
            self.store.subscribe(lambda _lay: QTimer.singleShot(
                0, lambda: populate_widgets_menu(self.widgets_menu, self.store)))

        theme_menu = self.menu.addMenu("Appearance")
        group = QActionGroup(theme_menu)
        group.setExclusive(True)
        for key, label in (("system", "Automatic"), ("light", "Light"), ("dark", "Dark")):
            act = QAction(label, theme_menu, checkable=True)
            act.setChecked(self.settings.theme == key)
            act.triggered.connect(lambda _c=False, key=key: self.set_theme(key))
            group.addAction(act)
            theme_menu.addAction(act)

        self.menu.addSeparator()
        self.desktop_action = QAction("Desktop Widget Mode", self.menu, checkable=True)
        self.desktop_action.setChecked(self.settings.desktop_mode)
        self.desktop_action.setEnabled(self._on_desktop_mode is not None)
        self.desktop_action.toggled.connect(self.set_desktop_mode)
        self.menu.addAction(self.desktop_action)

        self.helper_action = None
        if self.helper_setup is not None and self.helper_setup.available:
            self.helper_action = QAction(self.helper_setup.menu_text(), self.menu)
            self.helper_action.triggered.connect(self._run_helper_setup)
            self.menu.addAction(self.helper_action)
            self.refresh_helper_action()

        self.autostart_action = QAction("Launch at Login", self.menu, checkable=True)
        self.autostart_action.setEnabled(self.autostart.supported)
        self.autostart_action.setChecked(self.autostart.is_enabled())
        self.autostart_action.toggled.connect(self.set_autostart)
        self.menu.addAction(self.autostart_action)

        self.start_hidden_action = QAction("Start Hidden (menu bar only)", self.menu, checkable=True)
        self.start_hidden_action.setChecked(self.settings.start_hidden)
        self.start_hidden_action.setToolTip("Next time IOX Stats starts, open only the menu bar item, "
                                            "no window - independent of Launch at Login.")
        self.start_hidden_action.toggled.connect(self.set_start_hidden)
        self.menu.addAction(self.start_hidden_action)

        self.menu.addSeparator()
        about_act = QAction("About IOX Stats", self.menu)
        about_act.triggered.connect(self.show_about)
        self.menu.addAction(about_act)
        log_act = QAction("Open Log Folder", self.menu)
        log_act.triggered.connect(self.open_log_folder)
        self.menu.addAction(log_act)

        self.menu.addSeparator()
        quit_act = QAction("Quit IOX Stats", self.menu)
        quit_act.triggered.connect(on_quit)
        self.menu.addAction(quit_act)

    def _display_ids(self) -> List[str]:
        """Menu bar ids to actually draw: one, rotating, or all of them side by side."""
        ids = self.settings.tray_metrics
        if self.settings.tray_rotate and len(ids) > 1:
            return [ids[self._rotate_index % len(ids)]]
        return ids

    def _rotate_tick(self) -> None:
        self._rotate_index += 1
        self.refresh(self._last_snap)

    def set_rotate(self, enabled: bool) -> None:
        self.settings.tray_rotate = enabled
        self.settings.save()
        self._rotate_index = 0
        if enabled:
            self._rotate_timer.start()
        else:
            self._rotate_timer.stop()
        self.refresh(self._last_snap)

    def set_metric_enabled(self, mid: str, enabled: bool) -> None:
        cur = list(self.settings.tray_metrics)
        if enabled and mid not in cur:
            if len(cur) >= MAX_TRAY_METRICS:
                # keep the limit: revert the checkbox
                act = self.metric_actions[mid]
                act.blockSignals(True)
                act.setChecked(False)
                act.blockSignals(False)
                return
            cur.append(mid)
        elif not enabled and mid in cur:
            if len(cur) == 1:  # always show at least one value
                act = self.metric_actions[mid]
                act.blockSignals(True)
                act.setChecked(True)
                act.blockSignals(False)
                return
            cur.remove(mid)
        self.settings.tray_metrics = cur
        self.settings.save()
        self.refresh(self._last_snap)
        self._on_changed()

    def set_desktop_mode(self, enabled: bool) -> None:
        self.settings.desktop_mode = bool(enabled)
        self.settings.save()
        if self._on_desktop_mode is not None:
            self._on_desktop_mode(bool(enabled))

    def refresh_helper_action(self) -> None:
        """Menu entry for the CPU temperature helper: shows the active tool, or offers the setup."""
        if self.helper_action is None or self.helper_setup is None:
            return
        st = self.helper_setup.status()
        self.helper_action.setText(self.helper_setup.menu_text())
        self.helper_action.setEnabled(not st.ready and not self.helper_setup.busy)

    def _run_helper_setup(self) -> None:
        self.helper_setup.run()
        self.refresh_helper_action()

    def set_start_hidden(self, enabled: bool) -> None:
        self.settings.start_hidden = bool(enabled)
        self.settings.save()

    def show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(QMessageBox.Icon.NoIcon, f"About {__app_name__}",
                          f"{__app_name__} {__version__}", QMessageBox.StandardButton.Close)
        box.setInformativeText(
            "System status widgets in iOS style, with a live menu bar readout and a native macOS "
            "widget gallery widget.\n\n"
            "Provided as-is, without warranty of any kind. IOX Stats reads local system metrics only; "
            "it does not collect or transmit any data.\n\n"
            f"{__github_url__}")
        open_btn = box.addButton("Open GitHub Page", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(__github_url__))

    def open_log_folder(self) -> None:
        from ..logging_setup import log_dir

        d = log_dir()
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def set_autostart(self, enabled: bool) -> bool:
        """Toggle launch at login; the checkbox always reflects the real state afterwards."""
        self.autostart.set_enabled(enabled)
        actual = self.autostart.is_enabled()
        if actual != self.autostart_action.isChecked():
            self.autostart_action.blockSignals(True)
            self.autostart_action.setChecked(actual)
            self.autostart_action.blockSignals(False)
        return actual

    def set_theme(self, key: str) -> None:
        self.settings.theme = key
        self.settings.save()
        self._on_changed()

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._on_toggle()

    # live update --------------------------------------------------------
    def refresh(self, snap: Snapshot) -> None:
        self._last_snap = snap
        theme = resolve_theme(self.settings.theme)
        from ..metrics import tray_text
        tip = "IOX Stats\n" + tray_text(snap, self.settings.tray_metrics, sep="\n")   # tooltip: always all of them
        shown = self._display_ids()
        if self.native is not None:
            self.native.set_segments(tray_segments(snap, shown))
            self.native.set_tooltip(tip)
        else:
            self.icon.setIcon(QIcon(render_tray_pixmap(snap, shown, theme, self._pixmap_style())))
        self.icon.setToolTip(tip)

    def show(self) -> None:
        if self.native is None and self.available:
            self.icon.show()

    def remove(self) -> None:
        self._rotate_timer.stop()
        if self.native is not None:
            self.native.remove()
        self.icon.hide()
