"""Menus for choosing what a widget shows: size, style (rings / bars / numbers) and which values."""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu

from ..layout import (MAX_WIDGETS, PRESET_LABELS, PRESETS, SIZE_LABELS, SIZES, STYLE_LABELS, STYLES, LayoutStore,
                      capacity)
from ..metrics import METRICS


def _radio(menu: QMenu, items, current, on_pick) -> None:
    group = QActionGroup(menu)
    group.setExclusive(True)
    for key, label in items:
        act = QAction(label, menu, checkable=True)
        act.setChecked(key == current)
        act.triggered.connect(lambda _c=False, key=key: on_pick(key))
        group.addAction(act)
        menu.addAction(act)


def populate_widget_menu(menu: QMenu, store: LayoutStore, index: int) -> None:
    """Size / style / values / order / remove for widget ``index``."""
    layout = store.layout
    if not 0 <= index < len(layout):
        return
    cfg = layout[index]

    _radio(menu.addMenu("Size"), [(s, SIZE_LABELS[s]) for s in SIZES], cfg.size,
           lambda s: store.update(index, cfg.with_size(s)))
    _radio(menu.addMenu("Display"), [(s, STYLE_LABELS[s]) for s in STYLES], cfg.style,
           lambda s: store.update(index, cfg.with_style(s)))

    vals = menu.addMenu(f"Values ({len(cfg.metrics)} of {cfg.capacity})")
    info = QAction(f"{SIZE_LABELS[cfg.size]} · {STYLE_LABELS[cfg.style]}: up to {cfg.capacity}", vals)
    info.setEnabled(False)
    vals.addAction(info)
    vals.addSeparator()
    for mid, m in METRICS.items():
        act = QAction(m.label, vals, checkable=True)
        act.setChecked(mid in cfg.metrics)
        # full widgets grey out the values that would not fit; the last value cannot be removed
        act.setEnabled(cfg.can_remove(mid) if mid in cfg.metrics else cfg.can_add(mid))
        act.triggered.connect(lambda _c=False, mid=mid: store.update(index, cfg.toggled(mid)))
        vals.addAction(act)

    menu.addSeparator()
    earlier = menu.addAction("Move Earlier")
    earlier.setEnabled(index > 0)
    earlier.triggered.connect(lambda: store.move(index, -1))
    later = menu.addAction("Move Later")
    later.setEnabled(index < len(layout) - 1)
    later.triggered.connect(lambda: store.move(index, 1))
    remove = menu.addAction("Remove Widget")
    remove.setEnabled(len(layout) > 1)
    remove.triggered.connect(lambda: store.remove(index))


def populate_layout_menu(menu: QMenu, store: LayoutStore) -> None:
    """Add widget / presets / reset."""
    add = menu.addMenu("Add Widget")
    add.setEnabled(len(store.layout) < MAX_WIDGETS)
    for size in SIZES:
        sub = add.addMenu(SIZE_LABELS[size])
        for style in STYLES:
            act = sub.addAction(f"{STYLE_LABELS[style]} (up to {capacity(size, style)})")
            act.triggered.connect(lambda _c=False, size=size, style=style: store.add(size, style))
    presets = menu.addMenu("Layout Preset")
    for key, label in PRESET_LABELS.items():
        act = presets.addAction(label)
        act.triggered.connect(lambda _c=False, key=key: store.apply_preset(key))
    reset = menu.addAction("Reset Layout")
    reset.triggered.connect(store.reset)


def populate_widgets_menu(menu: QMenu, store: LayoutStore) -> None:
    """The tray menu's "Widgets" submenu: one entry per widget plus the layout actions."""
    for act in menu.actions():
        if act.menu() is not None:
            act.menu().deleteLater()
    menu.clear()
    for i, cfg in enumerate(store.layout):
        sub = menu.addMenu(f"{i + 1}. {cfg.describe()}")
        populate_widget_menu(sub, store, i)
    menu.addSeparator()
    populate_layout_menu(menu, store)
