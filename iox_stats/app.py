"""Application entry point and the update controller."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional

from . import __app_name__, __version__
from .autostart import Autostart
from .collectors import Collector, Snapshot
from .history import History
from .layout import PRESETS, LayoutStore
from .settings import Settings
from .share import SnapshotWriter, enabled_by_default


class Controller:
    """Samples metrics on a timer, keeps history, and notifies the UI."""

    def __init__(self, settings: Settings, dashboard, tray=None, writer: Optional[SnapshotWriter] = None):
        from PySide6.QtCore import QTimer

        self.settings = settings
        self.dashboard = dashboard
        self.tray = tray
        self.writer = writer            # shares the live values with the macOS widget gallery widget
        self.history = History(60)
        self.collector = Collector(settings.ping_host, settings.ping_port)
        self.collector.start()
        self.last: Optional[Snapshot] = None
        self.timer = QTimer()
        self.timer.setInterval(settings.interval_ms)
        self.timer.timeout.connect(self.tick)

    def start(self) -> None:
        self.tick()
        self.timer.start()

    def tick(self) -> Snapshot:
        snap = self.collector.sample()
        self.last = snap
        self.history.push(snap)
        self.dashboard.update_data(snap, self.history)
        if self.tray is not None:
            self.tray.refresh(snap)
        if self.writer is not None:
            self.writer.write(snap, snap.timestamp)
        return snap

    def refresh_helpers(self) -> Optional[str]:
        """Pick up a freshly installed temperature helper without restarting the app."""
        return self.collector.refresh_helpers()

    def stop(self) -> None:
        self.timer.stop()
        self.collector.stop()
        if self.writer is not None:
            self.writer.remove()


def _install_helpers() -> int:
    """CLI: show the temperature helper status and install it (macOS, needs Homebrew, no admin password)."""
    from . import helpers

    st = helpers.status()
    print(st.summary())
    if not st.supported:
        print("Nothing to do: this system has built-in sensors or needs no helper.")
        return 0
    if st.tool:
        print(f"Found: {st.path}")
        return 0
    if st.needs_homebrew:
        print(f"Homebrew is missing. Install it from {helpers.BREW_URL}:")
        print(f"  {helpers.BREW_INSTALL_HINT}")
        return 1
    print(f"Installing {st.recommended} with Homebrew ...")
    ok, msg = helpers.run_install(st)
    print(msg)
    return 0 if ok else 1


def _print_once() -> int:
    c = Collector()
    c.sample()
    time.sleep(0.6)
    c.start()
    time.sleep(1.8)
    snap = c.sample()
    c.stop()
    print(json.dumps(snap.to_dict(), indent=2))
    return 0


def _screenshot(path: str, theme: str, demo: bool = False, preset: Optional[str] = None) -> int:
    """Render the dashboard headlessly to a PNG (used by tests and docs)."""
    from PySide6.QtWidgets import QApplication

    from .ui.dashboard import Dashboard

    app = QApplication.instance() or QApplication(sys.argv[:1])
    settings = Settings(theme=theme).sanitize()
    dash = Dashboard(settings.theme, layout=PRESETS.get(preset or "detailed"))
    if demo:
        from .demo import demo_snapshots

        hist = History(60)
        snaps = demo_snapshots(60)
        for sn in snaps:
            hist.push(sn)
        dash.update_data(snaps[-1], hist)
        dash.adjustSize()
        return 0 if dash.grab().save(path) else 1
    ctrl = Controller(settings, dash)
    for _ in range(6):
        ctrl.tick()
        time.sleep(0.25)
        app.processEvents()
    dash.adjustSize()
    ok = dash.grab().save(path)
    ctrl.stop()
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="iox-stats", description=f"{__app_name__} - system status widgets")
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    parser.add_argument("--once", action="store_true", help="print one JSON snapshot and exit")
    parser.add_argument("--screenshot", metavar="PNG", help="render the dashboard to a PNG file and exit")
    parser.add_argument("--layout", choices=sorted(PRESETS), help="with --screenshot: render a layout preset")
    parser.add_argument("--demo", action="store_true", help="with --screenshot: use synthetic demo data")
    parser.add_argument("--theme", choices=["system", "light", "dark"], help="override the saved theme")
    parser.add_argument("--background", action="store_true",
                        help="start quietly in the menu bar / tray without opening the dashboard (used by autostart)")
    parser.add_argument("--no-tray", action="store_true", help="do not create a menu bar / tray icon")
    parser.add_argument("--desktop", action="store_true",
                        help="start in desktop widget mode (frameless glass widgets behind your windows)")
    parser.add_argument("--install-helpers", action="store_true",
                        help="macOS: install the CPU temperature helper (macmon / osx-cpu-temp) via Homebrew and exit")
    args = parser.parse_args(argv)

    if args.install_helpers:
        return _install_helpers()

    if args.once:
        return _print_once()
    if args.screenshot:
        return _screenshot(args.screenshot, args.theme or "light", args.demo, args.layout)

    from PySide6.QtWidgets import QApplication

    from .ui.dashboard import Dashboard
    from .ui.tray import TrayController

    app = QApplication(sys.argv[:1])
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings.load()
    if args.theme:
        settings.theme = args.theme
    if args.desktop:
        settings.desktop_mode = True

    from .ui.helper_ui import HelperSetup

    store = LayoutStore(settings)
    holder: dict = {}
    helper_setup = HelperSetup(on_installed=lambda: _helpers_installed(holder))
    tray = None
    if not args.no_tray:
        tray = TrayController(
            settings,
            on_toggle_dashboard=lambda: _toggle(holder["dash"]),
            on_settings_changed=lambda: holder["dash"].set_theme(settings.theme),
            on_quit=app.quit,
            store=store,
            helper_setup=helper_setup,
            on_desktop_mode=lambda on: holder["dash"].set_desktop_mode(on),
        )
        if not tray.available:
            tray = None

    dash = Dashboard(settings.theme, ping_label=settings.ping_host, hide_on_close=tray is not None,
                     use_glass=settings.glass, store=store)
    holder["dash"] = dash
    holder["tray"] = tray
    if len(settings.window_pos) == 2:
        dash.move(*settings.window_pos)

    def remember_position(x: int, y: int) -> None:
        settings.window_pos = [x, y]
        settings.save()

    dash.on_moved = remember_position
    if settings.desktop_mode:
        dash.set_desktop_mode(True)
    if tray is not None:
        tray.show()
        app.aboutToQuit.connect(tray.remove)
    writer = SnapshotWriter() if (settings.share_with_widgets and enabled_by_default()) else None
    ctrl = Controller(settings, dash, tray, writer)
    holder["ctrl"] = ctrl
    ctrl.start()
    if not (args.background and tray is not None):     # background start: menu bar only
        dash.show()
    app.aboutToQuit.connect(ctrl.stop)
    if tray is not None:
        _first_run_questions(settings, tray, dash, helper_setup)
    return app.exec()


def _helpers_installed(holder: dict) -> None:
    """The temperature helper was just installed: start it and update the menu."""
    ctrl, tray = holder.get("ctrl"), holder.get("tray")
    if ctrl is not None:
        ctrl.refresh_helpers()
    if tray is not None:
        tray.refresh_helper_action()


def _first_run_questions(settings: Settings, tray, parent, helper_setup) -> None:
    """One-time, opt-in questions (launch at login, CPU temperature helper). Both can be redone from the menu."""
    if settings.first_run_done and settings.helper_prompt_done:
        return
    from PySide6.QtCore import QTimer

    def ask() -> None:
        if not settings.first_run_done:
            _ask_autostart(settings, tray, parent)
        if not settings.helper_prompt_done:
            _ask_helper(settings, tray, helper_setup, parent)

    QTimer.singleShot(600, ask)


def _ask_helper(settings: Settings, tray, helper_setup, parent) -> None:
    st = helper_setup.status()
    settings.helper_prompt_done = True
    settings.save()
    if st.supported and not st.tool:
        helper_setup.run(parent)
        tray.refresh_helper_action()


def _ask_autostart(settings: Settings, tray, parent) -> None:
    """The answer can be changed any time in the menu."""
    from PySide6.QtWidgets import QMessageBox

    if tray.autostart.supported and not tray.autostart.is_enabled():
        box = QMessageBox(QMessageBox.Icon.Question, __app_name__, "Launch IOX Stats when you log in?",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, parent)
        box.setInformativeText("It starts quietly in the menu bar. You can change this at any time "
                               "via the menu item \"Launch at Login\".")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            tray.autostart_action.setChecked(True)
    settings.first_run_done = True
    settings.save()


def _toggle(dash) -> None:
    if dash.isVisible():
        dash.hide()
    else:
        dash.show()
        dash.raise_()
        dash.activateWindow()


if __name__ == "__main__":
    raise SystemExit(main())
