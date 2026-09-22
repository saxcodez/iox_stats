"""UI tests for the configurable widgets: styles, value limits, right-click / tray menus."""

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMenu

from iox_stats.history import History
from iox_stats.layout import CAPACITY, DEFAULT_LAYOUT, PRESETS, SIZES, STYLES, LayoutStore, W
from iox_stats.metrics import METRICS
from iox_stats.settings import Settings
from iox_stats.ui.dashboard import Dashboard
from iox_stats.ui.tray import TrayController
from iox_stats.ui.widget_menu import populate_widget_menu, populate_widgets_menu
from iox_stats.ui.widgets import GAP, UNIT, MultiCard, create_card

ALL_IDS = list(METRICS)


class _FakeAutostart:
    supported = True

    def is_enabled(self):
        return False

    def set_enabled(self, value):
        return True


def _colors(img: QImage) -> int:
    return len({img.pixel(x, y) for x in range(0, img.width(), 3) for y in range(0, img.height(), 3)})


def _history(snap, n=20):
    h = History(60)
    for i in range(n):
        snap.cpu_percent = 10 + i
        snap.net_down_bps = 2e5 * (i + 1)
        h.push(snap)
    return h


_KEEP = []      # keep menus alive: their submenus are owned by the parent menu


def _menu_for(store, index):
    menu = QMenu()
    populate_widget_menu(menu, store, index)
    _KEEP.append(menu)
    return menu


def _sub(menu, title_start):
    for act in menu.actions():
        if act.menu() and act.text().startswith(title_start):
            return act.menu()
    raise AssertionError(f"no submenu {title_start!r} in {[a.text() for a in menu.actions()]}")


def _by_text(menu, text):
    for act in menu.actions():
        if act.text() == text:
            return act
    raise AssertionError(f"no action {text!r} in {[a.text() for a in menu.actions()]}")


# ------------------------------------------------------------------ painting
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("style", ["rings", "bars", "numbers"])
def test_multicard_paints_full_capacity(qapp, snap, size, style):
    cfg = W(size, style, *ALL_IDS[:CAPACITY[(size, style)]])
    assert len(cfg.metrics) == CAPACITY[(size, style)]
    card = create_card(cfg)
    assert isinstance(card, MultiCard)
    card.update_data(snap, _history(snap))
    img = card.grab().toImage()
    assert _colors(img) > 6
    expected_w = UNIT if size == "small" else 2 * UNIT + GAP
    assert (card.vis_w, card.vis_h) == (expected_w, UNIT)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", SIZES)
def test_every_style_survives_missing_sensors(qapp, snap, size, style):
    snap.cpu_temp_c = None
    snap.battery_percent = None
    snap.ping_ms, snap.ping_ok = None, False
    cfg = W(size, style, "temp", "battery", "ping", "cpu", "ram", "disk")
    card = create_card(cfg)
    card.update_data(snap, History())
    assert not card.grab().isNull()


def test_every_metric_can_be_shown_in_every_style(qapp, snap):
    for style in STYLES:
        for mid in ALL_IDS:
            card = create_card(W("medium", style, mid))
            card.update_data(snap, _history(snap))
            assert not card.grab().isNull(), (style, mid)
            assert card.metric_ids == [mid]


def test_styles_look_different(qapp, snap):
    hist = _history(snap)
    shots = {}
    for style in ("rings", "bars", "numbers"):
        card = create_card(W("medium", style, "cpu", "ram", "disk"))
        card.update_data(snap, hist)
        shots[style] = card.grab().toImage()
    assert shots["rings"] != shots["bars"] != shots["numbers"]
    assert shots["rings"] != shots["numbers"]


# ---------------------------------------------------------------- dashboard
def test_dashboard_follows_layout_store(qapp, snap):
    settings = Settings()
    store = LayoutStore(settings)
    dash = Dashboard("light", store=store)
    dash.update_data(snap, _history(snap))
    assert len(dash.cards) == len(DEFAULT_LAYOUT)
    store.apply_preset("numbers")
    qapp.processEvents()                                   # rebuild is queued
    assert len(dash.cards) == len(PRESETS["numbers"])
    assert all(isinstance(c, MultiCard) for c in dash.cards)
    assert all(c.snap is snap for c in dash.cards)         # new cards get the latest data immediately
    assert Settings.load().widgets == [w.to_dict() for w in PRESETS["numbers"]]


def test_dashboard_from_explicit_layout_has_no_menu_store(qapp):
    dash = Dashboard("light", layout=PRESETS["rings"])
    assert len(dash.cards) == len(PRESETS["rings"])
    dash.show_widget_menu(0, None)                         # no store -> silently does nothing


def test_card_for_finds_metric_in_multi_widgets(qapp):
    dash = Dashboard("light", layout=[W("medium", "bars", "cpu", "ping"), W("small", "detail", "disk")])
    assert dash.card_for("ping") is dash.cards[0]
    assert dash.card_for("disk") is dash.cards[1]
    assert dash.card_for("battery") is None


def test_right_click_wires_context_menu_when_store_present(qapp):
    dash = Dashboard("light", store=LayoutStore(Settings()))
    assert all(c.context_requested is not None for c in dash.cards)
    assert Dashboard("light").cards[0].context_requested is None


def test_dashboard_window_grows_and_shrinks_with_layout(qapp):
    store = LayoutStore(Settings())
    dash = Dashboard("light", store=store)
    dash.show()
    qapp.processEvents()
    tall = dash.height()
    store.set_layout([W("small", "detail", "cpu")])
    qapp.processEvents()
    qapp.processEvents()
    assert dash.height() < tall


# ---------------------------------------------------------------- widget menu
def test_menu_style_and_size_radios_reflect_and_change(qapp):
    store = LayoutStore(Settings())
    store.set_layout([W("small", "rings", "cpu", "ram")])
    menu = _menu_for(store, 0)
    size, display = _sub(menu, "Size"), _sub(menu, "Display")
    assert [a.isChecked() for a in size.actions()] == [True, False]
    assert [a.text() for a in display.actions()] == ["Detailed", "Rings", "Bars", "Numbers only"]
    assert display.actions()[1].isChecked()

    _by_text(display, "Numbers only").trigger()
    assert store.layout[0].style == "numbers" and store.layout[0].metrics == ("cpu", "ram")
    _by_text(size, "Medium").trigger()
    assert store.layout[0].size == "medium"


def test_menu_values_limit_greys_out_extra_values(qapp):
    store = LayoutStore(Settings())
    store.set_layout([W("small", "rings", "cpu", "ram"), W("small", "detail", "cpu")])
    vals = _sub(_menu_for(store, 0), "Values")
    assert vals.title() == "Values (2 of 2)"
    items = {a.text(): a for a in vals.actions() if a.isCheckable()}
    assert items["CPU"].isChecked() and items["Memory"].isChecked()
    assert items["CPU"].isEnabled() and items["Memory"].isEnabled()           # may be removed
    assert not items["Disk"].isEnabled() and not items["Disk"].isChecked()    # would not fit
    assert sum(a.isChecked() for a in items.values()) == 2


def test_menu_values_toggle_changes_layout(qapp):
    store = LayoutStore(Settings())
    store.set_layout([W("medium", "bars", "cpu")])
    _by_text(_sub(_menu_for(store, 0), "Values"), "Disk").trigger()
    assert store.layout[0].metrics == ("cpu", "disk")
    # fill up to the medium/bars limit of 4, then the rest is refused
    for name, mid in (("Memory", "ram"), ("Ping", "ping")):
        _by_text(_sub(_menu_for(store, 0), "Values"), name).trigger()
    assert store.layout[0].metrics == ("cpu", "disk", "ram", "ping")
    vals = _sub(_menu_for(store, 0), "Values")
    assert vals.title() == "Values (4 of 4)"
    assert not _by_text(vals, "Swap").isEnabled()
    # removing one frees a slot again
    _by_text(vals, "Disk").trigger()
    assert _by_text(_sub(_menu_for(store, 0), "Values"), "Swap").isEnabled()


def test_menu_last_value_cannot_be_removed(qapp):
    store = LayoutStore(Settings())
    store.set_layout([W("small", "numbers", "temp")])
    vals = _sub(_menu_for(store, 0), "Values")
    assert not _by_text(vals, "CPU Temperature").isEnabled()


def test_menu_capacity_shown_per_style(qapp):
    store = LayoutStore(Settings())
    for (size, style), cap in CAPACITY.items():
        store.set_layout([W(size, style, "cpu")])
        assert _sub(_menu_for(store, 0), "Values").title() == f"Values (1 of {cap})"


def test_menu_move_and_remove(qapp):
    store = LayoutStore(Settings())
    store.set_layout([W("small", "detail", "cpu"), W("small", "detail", "ram"), W("small", "detail", "disk")])
    first = _menu_for(store, 0)
    assert not _by_text(first, "Move Earlier").isEnabled() and _by_text(first, "Move Later").isEnabled()
    _by_text(first, "Move Later").trigger()
    assert [w.metrics[0] for w in store.layout] == ["ram", "cpu", "disk"]
    last = _menu_for(store, 2)
    assert not _by_text(last, "Move Later").isEnabled()
    _by_text(last, "Remove Widget").trigger()
    assert len(store.layout) == 2
    only = LayoutStore(Settings())
    only.set_layout([W("small", "detail", "cpu")])
    assert not _by_text(_menu_for(only, 0), "Remove Widget").isEnabled()


def test_menu_out_of_range_index_is_ignored(qapp):
    store = LayoutStore(Settings())
    menu = QMenu()
    populate_widget_menu(menu, store, 99)
    assert menu.actions() == []


# ------------------------------------------------------------------ tray menu
def test_tray_widgets_submenu_lists_all_widgets_and_layout_actions(qapp):
    settings = Settings()
    store = LayoutStore(settings)
    tray = TrayController(settings, lambda: None, lambda: None, lambda: None,
                          autostart=_FakeAutostart(), store=store)
    populate_widgets_menu(tray.widgets_menu, store)
    titles = [a.text() for a in tray.widgets_menu.actions() if a.text()]
    assert len([t for t in titles if t[0].isdigit()]) == len(store.layout)
    assert {"Add Widget", "Layout Preset", "Reset Layout"} <= set(titles)


def test_tray_add_widget_and_presets_via_menu(qapp):
    settings = Settings()
    store = LayoutStore(settings)
    tray = TrayController(settings, lambda: None, lambda: None, lambda: None,
                          autostart=_FakeAutostart(), store=store)
    populate_widgets_menu(tray.widgets_menu, store)
    n = len(store.layout)
    add = _sub(tray.widgets_menu, "Add Widget")
    _sub(add, "Medium").actions()[3].trigger()             # Medium > Numbers only
    assert len(store.layout) == n + 1
    assert (store.layout[-1].size, store.layout[-1].style) == ("medium", "numbers")
    presets = _sub(tray.widgets_menu, "Layout Preset")
    _by_text(presets, "Bars").trigger()
    assert store.layout == PRESETS["bars"]
    _by_text(tray.widgets_menu, "Reset Layout").trigger()
    assert store.layout == DEFAULT_LAYOUT


def test_tray_without_store_has_no_widgets_menu(qapp):
    tray = TrayController(Settings(), lambda: None, lambda: None, lambda: None, autostart=_FakeAutostart())
    assert getattr(tray, "widgets_menu", None) is None


# ------------------------------------------------------------------------ CLI
@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_screenshot_cli_renders_each_preset(qapp, tmp_path, preset):
    from iox_stats.app import main

    out = tmp_path / f"{preset}.png"
    assert main(["--screenshot", str(out), "--theme", "light", "--demo", "--layout", preset]) == 0
    img = QImage(str(out))
    assert img.width() > 300 and img.height() > 150
