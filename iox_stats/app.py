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
from . import logging_setup


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

    logger = logging_setup.setup()
    st = helpers.status()
    logger.info("helper status: %s", st.summary())
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
    (logger.info if ok else logger.error)("helper install: %s", msg)
    return 0 if ok else 1


def _diagnose() -> int:
    """CLI: explain where every value comes from - especially the CPU temperature. Safe to paste into an issue."""
    import platform

    from . import helpers, iohid_temp
    from .autostart import Autostart
    from .share import snapshot_path
    from .temperature import MacTempProvider, parse_macmon_line

    print(f"{__app_name__} {__version__}  Python {platform.python_version()}  {sys.platform} {platform.machine()}")
    if sys.platform == "darwin":
        print(f"macOS {platform.mac_ver()[0]}")
    st = helpers.status()
    print(f"\n[temperature helper] {st.summary()}  path={st.path}  homebrew={st.brew}")
    if st.tool == "macmon" and st.path:
        import subprocess

        try:
            r = subprocess.run([st.path, "pipe", "-s", "1", "-i", "500"], capture_output=True, text=True, timeout=15)
            line = (r.stdout or "").strip().splitlines()[:1]
            print(f"  macmon exit={r.returncode} value={parse_macmon_line(line[0]) if line else None}")
            print(f"  macmon output: {(line[0][:400] if line else '(none)')}")
            if r.stderr.strip():
                print(f"  macmon stderr: {r.stderr.strip()[-400:]}")
        except Exception as exc:  # noqa: BLE001 - diagnostics must never crash
            print(f"  macmon failed: {exc}")
    if sys.platform == "darwin":
        v = iohid_temp.probe()
        print(f"\n[IOHID sensors, no helper needed] CPU temperature: {v if v is not None else 'not available'}")
    if MacTempProvider.supported():
        prov = MacTempProvider()
        prov.start()
        for _ in range(40):                 # up to 20 s: covers the helper timeout and the IOHID fallback
            if prov.value is not None:
                break
            time.sleep(0.5)
        print(f"\n[what the app uses] source={prov.tool} value={prov.value} error={prov.last_error}")
        prov.stop()
    else:
        from .collectors import _cpu_temperature

        print(f"\n[what the app uses] source=psutil value={_cpu_temperature()}")
    snap_file = snapshot_path()
    if snap_file.exists():
        try:
            data = json.loads(snap_file.read_text(encoding="utf-8"))
            age = time.time() - float(data.get("timestamp", 0))
            print(f"\n[widget hand-over] {snap_file}  age={age:.0f}s  temperature={data.get('temperature')}")
        except (OSError, ValueError) as exc:
            print(f"\n[widget hand-over] {snap_file} unreadable: {exc}")
    else:
        print(f"\n[widget hand-over] {snap_file} missing - the menu bar app is not running")
    print(f"\n[launch at login] {'on' if Autostart().is_enabled() else 'off'}")
    print(f"[log] {logging_setup.log_path()}")
    return 0


def _set_login(enabled: bool) -> int:
    from .autostart import Autostart

    auto = Autostart()
    auto.set_enabled(enabled)
    print(f"Launch at login: {'on' if auto.is_enabled() else 'off'}  ({auto.path})")
    return 0 if auto.is_enabled() == enabled else 1


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
                        help="experimental: floating frameless widgets behind your windows (not the macOS widget gallery)")
    parser.add_argument("--install-helpers", action="store_true",
                        help="macOS: install the CPU temperature helper (macmon / osx-cpu-temp) via Homebrew and exit")
    parser.add_argument("--start-hidden", action="store_true", help="start with no window, menu bar only")
    parser.add_argument("--show-log", action="store_true", help="print the path to the log file and exit")
    parser.add_argument("--diagnose", action="store_true",
                        help="show where each value (especially the CPU temperature) comes from, and exit")
    parser.add_argument("--enable-login", action="store_true", help="turn Launch at Login on and exit")
    parser.add_argument("--disable-login", action="store_true", help="turn Launch at Login off and exit")
    args = parser.parse_args(argv)

    if args.diagnose:
        return _diagnose()
    if args.enable_login or args.disable_login:
        return _set_login(bool(args.enable_login))

    if args.show_log:
        from .logging_setup import log_path

        print(log_path())
        return 0

    if args.install_helpers:
        return _install_helpers()

    if args.once:
        return _print_once()
    if args.screenshot:
        return _screenshot(args.screenshot, args.theme or "light", args.demo, args.layout)

    logger = logging_setup.setup()
    if sys.platform == "darwin":
        from .share import write_launch_info

        write_launch_info()

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
    from .ui.theme import set_palette

    set_palette(settings.palette)
    if args.desktop:
        settings.desktop_mode = True
    if args.start_hidden:
        settings.start_hidden = True

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
            # the floating-window mode is experimental and only offered when started with --desktop
            on_desktop_mode=(lambda on: holder["dash"].set_desktop_mode(on)) if args.desktop else None,
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
    stay_hidden = args.background or settings.start_hidden
    if not (stay_hidden and tray is not None):     # background / start-hidden: menu bar only
        dash.show()
    app.aboutToQuit.connect(ctrl.stop)
    if tray is not None:
        _first_run_questions(settings, tray, dash, helper_setup)
    logger.info("started (tray=%s, desktop_mode=%s, hidden=%s)", tray is not None, settings.desktop_mode, stay_hidden)
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
