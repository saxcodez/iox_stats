"""Menu bar display modes, logging, About dialog, Start Hidden."""

import logging

from PySide6.QtCore import QCoreApplication

from iox_stats import __github_url__, logging_setup
from iox_stats.settings import MAX_TRAY_METRICS, Settings
from iox_stats.ui.tray import ROTATE_INTERVAL_MS, TrayController


class _Auto:
    supported = True

    def is_enabled(self):
        return False

    def set_enabled(self, value):
        return True


def _tray(settings=None, **kw):
    return TrayController(settings or Settings(), lambda: None, lambda: None, lambda: None,
                          autostart=_Auto(), native_factory=lambda cb: None, **kw)


# --- menu bar display: 2 values or 1 value, extra values rotate -----------------------------
def test_default_shows_two_values_side_by_side(qapp):
    settings = Settings(tray_metrics=["cpu", "temp"])
    assert settings.tray_mode == "two"
    tray = _tray(settings)
    assert tray._display_ids() == ["cpu", "temp"]
    tray._rotate_tick()
    assert tray._display_ids() == ["cpu", "temp"]                # everything fits: nothing rotates


def test_two_mode_rotates_in_pairs_when_more_are_selected(qapp):
    tray = _tray(Settings(tray_metrics=["cpu", "temp", "ping", "ram", "disk"]))
    seen = []
    for _ in range(4):
        seen.append(tray._display_ids())
        tray._rotate_tick()
    assert seen == [["cpu", "temp"], ["ping", "ram"], ["disk"], ["cpu", "temp"]]


def test_one_mode_rotates_single_values(qapp):
    settings = Settings(tray_metrics=["cpu", "temp", "ping"])
    tray = _tray(settings)
    tray.mode_actions["one"].trigger()
    assert settings.tray_mode == "one" and Settings.load().tray_mode == "one"
    assert tray.mode_actions["one"].isChecked() and not tray.mode_actions["two"].isChecked()
    shown = []
    for _ in range(4):
        shown.append(tray._display_ids())
        tray._rotate_tick()
    assert shown == [["cpu"], ["temp"], ["ping"], ["cpu"]]
    tray.mode_actions["two"].trigger()                           # and back: nothing is lost
    assert tray._display_ids() == ["cpu", "temp"] and settings.tray_metrics == ["cpu", "temp", "ping"]


def test_single_value_never_rotates(qapp):
    tray = _tray(Settings(tray_metrics=["cpu"], tray_mode="one"))
    tray._rotate_tick()
    assert tray._display_ids() == ["cpu"]


def test_unknown_mode_is_sanitized_and_ignored(qapp):
    assert Settings(tray_mode="all").sanitize().tray_mode == "two"
    settings = Settings()
    tray = _tray(settings)
    tray.set_tray_mode("bogus")
    assert settings.tray_mode == "two"
    assert tray._rotate_timer.interval() == ROTATE_INTERVAL_MS


def test_tooltip_always_lists_every_selected_value(qapp, snap):
    tray = _tray(Settings(tray_metrics=["cpu", "ping", "ram"], tray_mode="one"))
    tray.refresh(snap)
    tip = tray.icon.toolTip()
    assert "CPU 42%" in tip and "Ping 18 ms" in tip and "RAM" in tip


def test_max_tray_metrics_raised_to_six():
    assert MAX_TRAY_METRICS == 6
    s = Settings(tray_metrics=["cpu", "temp", "ram", "swap", "disk", "ping", "battery"]).sanitize()
    assert len(s.tray_metrics) == 6


def test_remove_stops_the_rotation_timer(qapp):
    tray = _tray(Settings(tray_metrics=["cpu", "temp"]))
    tray.remove()
    assert not tray._rotate_timer.isActive()


# --- start hidden -------------------------------------------------------------------
def test_start_hidden_checkbox_persists(qapp):
    settings = Settings()
    tray = _tray(settings)
    assert not tray.start_hidden_action.isChecked()
    tray.start_hidden_action.setChecked(True)
    assert settings.start_hidden is True
    assert Settings.load().start_hidden is True


# --- about dialog -------------------------------------------------------------------
def test_about_dialog_shows_version_and_offers_github_link(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr("iox_stats.ui.tray.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))

    from PySide6.QtWidgets import QMessageBox

    tray = _tray()
    captured = {}

    def fake_exec(self):
        captured["buttons"] = [b.text() for b in self.buttons()]
        return 0

    def fake_clicked(self):
        return next(b for b in self.buttons() if b.text() == "Open GitHub Page")

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", fake_clicked)
    tray.show_about()
    assert "Open GitHub Page" in captured["buttons"]
    assert opened == [__github_url__]


def test_open_log_folder_creates_dir_and_opens_it(qapp, monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr("iox_stats.ui.tray.QDesktopServices.openUrl", lambda url: opened.append(url.toLocalFile()))
    tray = _tray()
    tray.open_log_folder()
    from iox_stats.logging_setup import log_dir

    assert log_dir().is_dir()
    assert opened and opened[0] == str(log_dir())


# --- logging --------------------------------------------------------------------------
def test_setup_writes_a_log_file_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("IOX_STATS_CONFIG_DIR", str(tmp_path / "cfg"))
    logging_setup._configured = False
    try:
        logger1 = logging_setup.setup()
        logger2 = logging_setup.setup()
        assert logger1 is logger2
        assert len(logger1.handlers) == 2                          # file + stderr, not doubled on 2nd call
        logger1.error("boom")
        for h in logger1.handlers:
            h.flush()
        text = logging_setup.log_path().read_text(encoding="utf-8")
        assert "boom" in text and "starting" in text
        assert logging_setup.tail(1).strip().endswith("boom")
    finally:
        logging_setup._configured = False
        logging.getLogger("iox_stats").handlers.clear()


def test_tail_returns_none_without_a_log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("IOX_STATS_CONFIG_DIR", str(tmp_path / "cfg2"))
    assert logging_setup.tail() is None


# --- CLI ----------------------------------------------------------------------------
def test_show_log_cli_prints_path(capsys):
    from iox_stats.app import main
    from iox_stats.logging_setup import log_path

    assert main(["--show-log"]) == 0
    assert str(log_path()) in capsys.readouterr().out
