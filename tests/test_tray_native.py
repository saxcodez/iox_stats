"""Menu bar item: segments, native macOS status item glue (with a fake), fallback and live widgets submenu."""

from PySide6.QtCore import QPoint

from iox_stats.layout import LayoutStore, W
from iox_stats.settings import Settings
from iox_stats.ui import macos_status
from iox_stats.ui.tray import TrayController, tray_segments


class FakeNative:
    def __init__(self, on_click):
        self.on_click = on_click
        self.segments, self.tooltip, self.removed = None, None, False
        self.corner = (1200.0, 900.0)       # Cocoa coordinates (origin bottom-left)

    def set_segments(self, segments):
        self.segments = segments

    def set_tooltip(self, text):
        self.tooltip = text

    def anchor(self):
        return self.corner

    def remove(self):
        self.removed = True


class _Auto:
    supported = True

    def is_enabled(self):
        return False

    def set_enabled(self, value):
        return True


def _tray(settings=None, factory=FakeNative, **kw):
    return TrayController(settings or Settings(tray_metrics=["cpu", "temp", "ping"]), lambda: None, lambda: None,
                          lambda: None, autostart=_Auto(), native_factory=factory, **kw)


def test_segments_carry_label_value_and_level(snap):
    segs = tray_segments(snap, ["cpu", "temp", "ping"])
    assert segs == [("CPU", "42%", "ok"), ("T", "61°C", "ok"), ("Ping", "18 ms", "ok")]
    snap.cpu_percent = 95
    assert tray_segments(snap, ["cpu"])[0][2] == "crit"
    assert tray_segments(snap, [])[0][0] == "IOX"


def test_native_item_gets_live_text_instead_of_a_pixmap(qapp, snap):
    tray = _tray()
    assert isinstance(tray.native, FakeNative) and tray.available
    assert tray.native.segments is not None                      # initial content
    tray.refresh(snap)
    assert [s[0] for s in tray.native.segments] == ["CPU", "T", "Ping"]
    assert "CPU 42%" in tray.native.tooltip
    tray.show()
    assert not tray.icon.isVisible()                             # the Qt icon is not used at all


def test_native_item_follows_menu_selection(qapp, snap):
    settings = Settings(tray_metrics=["cpu"])
    tray = _tray(settings)
    tray.metric_actions["ram"].setChecked(True)
    tray.metric_actions["temp"].setChecked(True)
    assert [s[0] for s in tray.native.segments] == ["CPU", "RAM", "T"]      # refreshed on every change
    assert len(tray.native.segments) == 3


def test_click_opens_menu_below_the_item(qapp, monkeypatch):
    tray = _tray()
    popped = []
    monkeypatch.setattr(tray.menu, "popup", lambda pos: popped.append(pos))
    tray.native.on_click()
    assert len(popped) == 1 and isinstance(popped[0], QPoint)
    assert popped[0].x() == 1200          # x carries over, y is flipped to Qt's top-left origin


def test_click_without_anchor_falls_back_to_cursor(qapp, monkeypatch):
    tray = _tray()
    tray.native.corner = None
    tray.native.anchor = lambda: None
    popped = []
    monkeypatch.setattr(tray.menu, "popup", lambda pos: popped.append(pos))
    tray.native.on_click()
    assert popped


def test_no_native_item_falls_back_to_qt_icon(qapp, snap):
    tray = _tray(factory=lambda cb: None)
    assert tray.native is None
    tray.refresh(snap)
    assert not tray.icon.icon().isNull()
    assert tray.icon.contextMenu() is tray.menu


def test_explicit_compact_style_never_uses_native(qapp):
    calls = []
    tray = _tray(Settings(tray_style="compact"), factory=lambda cb: calls.append(cb) or FakeNative(cb))
    assert tray.native is None and not calls


def test_remove_cleans_up(qapp):
    tray = _tray()
    native = tray.native
    tray.remove()
    assert native.removed


def test_native_helpers_are_inert_off_macos():
    assert macos_status.native_available() is False              # tests run on Linux
    assert macos_status.create_status_item(lambda: None) is None


def test_widgets_submenu_follows_layout_changes(qapp):
    settings = Settings()
    store = LayoutStore(settings)
    tray = _tray(settings, store=store)
    before = len([a for a in tray.widgets_menu.actions() if a.text()[:1].isdigit()])
    store.add("small", "rings")
    qapp.processEvents()
    after = [a.text() for a in tray.widgets_menu.actions() if a.text()[:1].isdigit()]
    assert len(after) == before + 1 and "Rings" in after[-1]
    store.set_layout([W("small", "detail", "cpu")])
    qapp.processEvents()
    assert len([a for a in tray.widgets_menu.actions() if a.text()[:1].isdigit()]) == 1
