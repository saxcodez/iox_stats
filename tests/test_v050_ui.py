"""v0.5.0: helper setup dialogs/flow, tray menu items, desktop mode, first-run questions, snapshot in the controller."""

import json
import types

from PySide6.QtCore import QCoreApplication

from iox_stats import helpers
from iox_stats.app import Controller, _ask_helper, _helpers_installed
from iox_stats.settings import Settings, config_dir
from iox_stats.share import SnapshotWriter
from iox_stats.ui.dashboard import Dashboard
from iox_stats.ui.helper_ui import HelperSetup
from iox_stats.ui.tray import TrayController


def _status(installed=(), machine="arm64", platform="darwin"):
    finder = lambda name: f"/opt/homebrew/bin/{name}" if name in installed else None  # noqa: E731
    return helpers.status(platform, machine, finder)


class QuietSetup(HelperSetup):
    """No real dialogs: records what would have been shown; installs through a fake."""

    def __init__(self, state, **kw):
        self.state = state
        self.asked, self.explained, self.notified = 0, 0, []
        self.answer = True
        super().__init__(status_fn=lambda: self.state, install_fn=self._fake_install, **kw)
        self.installs = []

    def _fake_install(self, st, on_done):
        self.installs.append(st.recommended)
        self.state = _status(["macmon", "brew"])             # the tool appears
        on_done(True, f"{st.recommended} installed.")

    def confirm(self, st, parent=None):
        self.asked += 1
        return self.answer

    def explain_homebrew(self, st, parent=None):
        self.explained += 1

    def notify(self, ok, message, parent=None):
        self.notified.append((ok, message))


class FakeAuto:
    supported = True

    def is_enabled(self):
        return False

    def set_enabled(self, value):
        return True


def _tray(setup=None, settings=None, **kw):
    return TrayController(settings or Settings(), lambda: None, lambda: None, lambda: None, autostart=FakeAuto(),
                          native_factory=lambda cb: None, helper_setup=setup, **kw)


# --- helper setup -------------------------------------------------------------
def test_setup_installs_after_confirmation_and_reports(qapp):
    installed = []
    s = QuietSetup(_status(["brew"]), on_installed=lambda: installed.append(1))
    s.run()
    QCoreApplication.processEvents()
    assert s.asked == 1 and s.installs == ["macmon"] and installed == [1]
    assert s.notified == [(True, "macmon installed.")] and not s.busy
    assert s.menu_text() == "CPU temperature: macmon active"


def test_setup_declined_installs_nothing(qapp):
    s = QuietSetup(_status(["brew"]))
    s.answer = False
    s.run()
    assert s.installs == [] and s.notified == []


def test_setup_without_homebrew_explains_instead(qapp):
    s = QuietSetup(_status([]))
    s.run()
    assert s.explained == 1 and s.asked == 0 and s.installs == []
    assert s.menu_text() == "Set Up CPU Temperature..."      # still clickable: it explains how to get Homebrew


def test_setup_does_nothing_when_ready_or_unsupported(qapp):
    for st in (_status(["macmon"]), _status([], platform="linux")):
        s = QuietSetup(st)
        s.run()
        assert s.asked == s.explained == 0 and s.installs == []


# --- tray -----------------------------------------------------------------------
def test_tray_has_no_helper_item_off_macos(qapp):
    tray = _tray(QuietSetup(_status([], platform="linux")))
    assert tray.helper_action is None


def test_tray_helper_item_offers_setup_then_shows_active_tool(qapp):
    setup = QuietSetup(_status(["brew"]))
    tray = _tray(setup)
    assert tray.helper_action.text() == "Set Up CPU Temperature..."
    assert tray.helper_action.isEnabled()
    tray.helper_action.trigger()
    QCoreApplication.processEvents()
    assert setup.installs == ["macmon"]
    assert tray.helper_action.text() == "CPU temperature: macmon active"
    assert not tray.helper_action.isEnabled()


def test_tray_desktop_toggle_saves_and_calls_back(qapp):
    calls, settings = [], Settings()
    tray = _tray(settings=settings, on_desktop_mode=calls.append)
    assert tray.desktop_action.isEnabled() and not tray.desktop_action.isChecked()
    tray.desktop_action.setChecked(True)
    assert calls == [True] and settings.desktop_mode is True
    assert json.loads((config_dir() / "settings.json").read_text())["desktop_mode"] is True
    assert not _tray().desktop_action.isEnabled()            # nothing to control -> disabled


# --- desktop mode -----------------------------------------------------------------
def test_desktop_mode_is_frameless_and_paints_nothing(qapp, snap):
    from PySide6.QtCore import Qt
    from iox_stats.history import History

    dash = Dashboard("light", use_glass=False)
    dash.update_data(snap, History(5))
    dash.show()
    dash.set_desktop_mode(True)
    assert dash.desktop_mode and dash.isVisible()
    assert dash.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dash.windowFlags() & Qt.WindowType.WindowStaysOnBottomHint
    assert dash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    img = dash.grab().toImage()
    assert img.pixelColor(2, 2).alpha() == 0                   # no backdrop: the desktop shows through
    dash.set_desktop_mode(False)
    assert not dash.desktop_mode and not (dash.windowFlags() & Qt.WindowType.FramelessWindowHint)
    dash.set_desktop_mode(False)                                # idempotent
    dash.close()


def test_moving_the_window_reports_the_position_once(qapp):
    dash = Dashboard("light", use_glass=False)
    seen = []
    dash.on_moved = lambda x, y: seen.append((x, y))
    dash.show()
    dash.move(123, 145)
    dash._move_timer.timeout.emit()                             # do not wait for the debounce
    assert seen and seen[-1] == (dash.x(), dash.y())
    dash.close()


def test_settings_window_pos_is_validated():
    assert Settings(window_pos=[10.7, 20]).sanitize().window_pos == [10, 20]
    for bad in ([1], "x", [1, "a"], None):
        assert Settings(window_pos=bad).sanitize().window_pos == []
    assert Settings().desktop_mode is False and Settings().share_with_widgets is True


def test_old_settings_file_loads_with_new_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"theme": "dark", "first_run_done": True}))
    s = Settings.load(p)
    assert s.theme == "dark" and s.first_run_done and not s.helper_prompt_done and s.window_pos == []


# --- app glue -----------------------------------------------------------------------
def test_first_run_helper_question_is_asked_once(qapp):
    settings = Settings()
    setup = QuietSetup(_status(["brew"]))
    tray = _tray(setup)
    _ask_helper(settings, tray, setup, None)
    assert settings.helper_prompt_done and setup.installs == ["macmon"]
    assert Settings.load().helper_prompt_done                  # persisted


def test_first_run_helper_question_skipped_when_tool_exists(qapp):
    settings = Settings()
    setup = QuietSetup(_status(["macmon"]))
    _ask_helper(settings, _tray(setup), setup, None)
    assert settings.helper_prompt_done and setup.asked == 0


def test_controller_writes_snapshot_for_widgets_and_cleans_up(qapp, tmp_path):
    path = tmp_path / "snapshot.json"
    dash = types.SimpleNamespace(update_data=lambda *a: None)
    ctrl = Controller(Settings(), dash, None, SnapshotWriter(path, min_interval=0))
    ctrl.tick()
    data = json.loads(path.read_text())
    assert data["schema"] == 1 and "temperature" in data
    ctrl.stop()
    assert not path.exists()


def test_helpers_installed_restarts_temperature_and_updates_menu(qapp):
    calls = []
    ctrl = types.SimpleNamespace(refresh_helpers=lambda: calls.append("restart"))
    tray = types.SimpleNamespace(refresh_helper_action=lambda: calls.append("menu"))
    _helpers_installed({"ctrl": ctrl, "tray": tray})
    assert calls == ["restart", "menu"]
    _helpers_installed({})                                     # nothing set up yet: no crash
