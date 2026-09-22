"""UI tests - run headless with Qt's offscreen platform."""

from PySide6.QtGui import QImage

from iox_stats.history import History
from iox_stats.settings import Settings
from iox_stats.ui.dashboard import Dashboard
from iox_stats.ui.theme import DARK, LIGHT, resolve_theme
from iox_stats.ui.tray import (MAX_TRAY_METRICS, TrayController, effective_style,
                               render_compact_icon, render_text_icon)


class _FakeAutostart:
    """In-memory stand-in so UI tests never touch the real login items."""

    supported = True

    def __init__(self, enabled=False, works=True):
        self.enabled, self.works = enabled, works

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, value):
        if self.works:
            self.enabled = value
        return self.enabled == value


def _filled_history(snap, n=30):
    h = History(60)
    for i in range(n):
        snap.cpu_percent = 20 + i
        snap.net_down_bps = 1e5 * (i + 1)
        h.push(snap)
    return h


def _distinct_colors(img: QImage) -> int:
    seen = set()
    for x in range(0, img.width(), 3):
        for y in range(0, img.height(), 3):
            seen.add(img.pixel(x, y))
    return len(seen)


def test_dashboard_builds_all_widgets(qapp):
    dash = Dashboard("light")
    assert len(dash.cards) == 9
    for mid in ("cpu", "ram", "temp", "disk", "net_down", "ping", "uptime", "battery"):
        assert dash.card_for(mid) is not None, mid
    from iox_stats import __version__

    assert __version__ in dash.windowTitle()


def test_every_widget_paints_with_data(qapp, snap):
    dash = Dashboard("light")
    dash.update_data(snap, _filled_history(snap))
    dash.show()
    qapp.processEvents()
    for i, card in enumerate(dash.cards):
        img = card.grab().toImage()
        assert not img.isNull()
        assert _distinct_colors(img) > 4, f"widget {i} looks empty"


def test_widgets_handle_missing_sensors(qapp, snap):
    snap.cpu_temp_c = None
    snap.battery_percent = None
    snap.ping_ms, snap.ping_ok = None, False
    dash = Dashboard("dark")
    dash.update_data(snap, History())
    for card in dash.cards:
        assert not card.grab().isNull()


def test_theme_switch_changes_rendering(qapp, snap):
    dash = Dashboard("light")
    dash.update_data(snap, _filled_history(snap))
    light = dash.card_for("cpu").grab().toImage()
    dash.set_theme("dark")
    dark = dash.card_for("cpu").grab().toImage()
    assert dash.theme is DARK
    assert light.pixel(80, 80) != dark.pixel(80, 80)
    assert resolve_theme("light") is LIGHT


def test_card_sizes_follow_ios_grid(qapp):
    dash = Dashboard("light")
    from iox_stats.ui.widgets import GAP, UNIT

    small, medium = dash.card_for("cpu"), dash.card_for("net_down")
    assert (small.vis_w, small.vis_h) == (UNIT, UNIT)                    # iOS small widget: 158 x 158
    assert (medium.vis_w, medium.vis_h) == (2 * UNIT + GAP, UNIT)        # iOS medium widget: 2 units wide


def test_close_hides_when_tray_active(qapp):
    from PySide6.QtGui import QCloseEvent

    dash = Dashboard("light", hide_on_close=True)
    dash.show()
    ev = QCloseEvent()
    dash.closeEvent(ev)
    assert not ev.isAccepted() and not dash.isVisible()


def test_tray_text_icon_grows_with_metrics(qapp, snap):
    one = render_text_icon(snap, ["cpu"], LIGHT)
    three = render_text_icon(snap, ["cpu", "temp", "ping"], LIGHT)
    assert three.width() > one.width() > 0
    assert three.height() == one.height() == 44  # 22pt @2x


def test_tray_compact_icon_renders(qapp, snap):
    pm = render_compact_icon(snap, ["temp", "ping"], DARK)
    assert pm.width() == pm.height() > 0
    assert _distinct_colors(pm.toImage()) > 3


def test_tray_style_resolution():
    assert effective_style("text") == "text" and effective_style("compact") == "compact"
    assert effective_style("auto") in ("text", "compact")


def test_tray_menu_limits_and_persistence(qapp, snap):
    settings = Settings(tray_metrics=["cpu", "temp", "ping"])
    changed = []
    tray = TrayController(settings, lambda: None, lambda: changed.append(1), lambda: None,
                          autostart=_FakeAutostart())
    # add a 4th -> ok
    tray.metric_actions["ram"].setChecked(True)
    assert settings.tray_metrics == ["cpu", "temp", "ping", "ram"] and len(settings.tray_metrics) == MAX_TRAY_METRICS
    # 5th is refused and the checkbox reverts
    tray.metric_actions["disk"].setChecked(True)
    assert "disk" not in settings.tray_metrics and not tray.metric_actions["disk"].isChecked()
    # persisted to disk
    assert Settings.load().tray_metrics == ["cpu", "temp", "ping", "ram"]
    # cannot remove the last value
    for mid in ["temp", "ping", "ram"]:
        tray.metric_actions[mid].setChecked(False)
    tray.metric_actions["cpu"].setChecked(False)
    assert settings.tray_metrics == ["cpu"] and tray.metric_actions["cpu"].isChecked()
    assert changed


def test_tray_refresh_updates_tooltip(qapp, snap):
    tray = TrayController(Settings(tray_metrics=["cpu", "ping"]), lambda: None, lambda: None, lambda: None,
                          autostart=_FakeAutostart())
    tray.refresh(snap)
    tip = tray.icon.toolTip()
    assert "CPU 42%" in tip and "Ping 18 ms" in tip


def test_controller_tick_feeds_dashboard_and_history(qapp):
    from iox_stats.app import Controller

    dash = Dashboard("light")
    ctrl = Controller(Settings(), dash)
    try:
        for _ in range(3):
            ctrl.tick()
        assert len(ctrl.history) == 3
        assert dash.card_for("cpu").snap is ctrl.last
    finally:
        ctrl.stop()


def test_screenshot_cli(qapp, tmp_path):
    from iox_stats.app import main

    out = tmp_path / "shot.png"
    assert main(["--screenshot", str(out), "--theme", "dark"]) == 0
    img = QImage(str(out))
    assert img.width() > 600 and img.height() > 400


def test_tray_autostart_toggle_and_header(qapp):
    from iox_stats import __version__

    fake = _FakeAutostart()
    tray = TrayController(Settings(), lambda: None, lambda: None, lambda: None, autostart=fake)
    first = tray.menu.actions()[0]
    assert first.text().endswith(f"v{__version__}") and not first.isEnabled()
    assert not tray.autostart_action.isChecked()          # opt-in: off by default
    tray.autostart_action.setChecked(True)
    assert fake.enabled
    tray.autostart_action.setChecked(False)               # and can be switched off again
    assert not fake.enabled


def test_tray_autostart_checkbox_reflects_real_state_on_failure(qapp):
    fake = _FakeAutostart(works=False)
    tray = TrayController(Settings(), lambda: None, lambda: None, lambda: None, autostart=fake)
    tray.autostart_action.setChecked(True)
    assert not fake.enabled and not tray.autostart_action.isChecked()


def test_hero_text_shrinks_to_fit(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter

    from iox_stats.ui.widgets import draw_hero

    img = QImage(300, 60, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    narrow = draw_hero(p, QRectF(0, 0, 140, 50), [("1234.5", "GB/s")], LIGHT.label, LIGHT.label2)
    wide = draw_hero(p, QRectF(0, 0, 300, 50), [("1234.5", "GB/s")], LIGHT.label, LIGHT.label2)
    p.end()
    assert narrow <= 141 and wide > narrow


def test_glass_falls_back_to_simulated_backdrop(qapp, snap, monkeypatch):
    monkeypatch.setenv("IOX_STATS_NO_NATIVE_BLUR", "1")
    dash = Dashboard("dark")
    dash.show()
    qapp.processEvents()
    assert dash.native_glass is False
    dash.update_data(snap, _filled_history(snap))
    img = dash.grab().toImage()
    assert _distinct_colors(img) > 50        # gradient backdrop + glass, not a flat fill


def test_glass_card_is_translucent_over_backdrop(qapp, snap):
    """Cards let the backdrop show through - that is what makes them glass."""
    from dataclasses import replace

    dash = Dashboard("light")
    dash.update_data(snap, _filled_history(snap))
    a = dash.grab().toImage()
    dash.theme = replace(dash.theme, backdrop_base=LIGHT.color("red"), backdrop_blobs=())
    b = dash.grab().toImage()
    x, y = 40, 60        # inside the first card, left of the icon/title text
    assert a.pixel(x, y) != b.pixel(x, y)
