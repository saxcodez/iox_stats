"""Colour palettes: iOS green by default, warnings stay orange / red, same choices in Python and Swift."""

import re
from pathlib import Path

from iox_stats.metrics import CRIT, OK, WARN
from iox_stats.settings import Settings
from iox_stats.ui import theme as th

ROOT = Path(__file__).resolve().parent.parent


def teardown_function(_fn):
    th.set_palette(th.DEFAULT_PALETTE)


def test_default_is_ios_green():
    assert Settings().palette == "ios" and th.DEFAULT_PALETTE == "ios"
    th.set_palette("ios")
    assert th.DARK.level_color(OK, "purple") == th.DARK.color("green")
    assert th.DARK.accent("blue") == th.DARK.color("green")


def test_warnings_keep_their_colours_in_every_palette():
    for key in th.PALETTES:
        th.set_palette(key)
        assert th.LIGHT.level_color(WARN, "blue") == th.LIGHT.color("orange")
        assert th.LIGHT.level_color(CRIT, "blue") == th.LIGHT.color("red")


def test_colorful_and_single_accent_palettes():
    th.set_palette("colorful")
    assert th.DARK.accent("purple") == th.DARK.color("purple")
    th.set_palette("teal")
    assert th.DARK.accent("purple") == th.DARK.color("teal")
    th.set_palette("graphite")
    assert th.DARK.accent("purple") == th.DARK.color("gray")
    assert th.set_palette("neon") == "ios"                       # unknown -> default


def test_settings_sanitize_matches_theme_palettes():
    for key in th.PALETTES:
        assert Settings(palette=key).sanitize().palette == key
    assert Settings(palette="neon").sanitize().palette == "ios"


def test_swift_offers_the_same_palettes():
    text = (ROOT / "macos-widgets/Widget/Layout.swift").read_text(encoding="utf-8")
    cases = re.search(r"enum WidgetPalette: String, AppEnum \{\s*case ([\w, ]+)\n", text).group(1)
    assert [c.strip() for c in cases.split(",")] == list(th.PALETTES)
    assert '@Parameter(title: "Colors", default: .ios)' in text


def test_tray_palette_menu_switches_and_saves(qapp):
    from iox_stats.ui.tray import TrayController

    class Auto:
        supported = True

        def is_enabled(self):
            return False

        def set_enabled(self, v):
            return True

    changed, settings = [], Settings()
    tray = TrayController(settings, lambda: None, lambda: changed.append(1), lambda: None, autostart=Auto(),
                          native_factory=lambda cb: None)
    assert tray.palette_actions["ios"].isChecked()
    tray.palette_actions["purple"].trigger()
    assert settings.palette == "purple" and th.get_palette() == "purple" and changed
    assert Settings.load().palette == "purple"
