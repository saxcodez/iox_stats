# Changelog

All notable changes to **IOX Stats** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-09-22

**Menu bar rotation, logging, and the first pieces for a real release.**

### Added
- **Menu bar rotation** (on by default): instead of cramming several values side by side (which could push
  other menu bar icons out, e.g. the Weather icon), IOX Stats now shows one value at a time and rotates
  through the selected ones every 4 seconds. Up to 6 values can be selected (was 4). Turn it off in the
  menu ("Rotate through the values") to go back to showing them all at once.
- **Log file** for diagnostics: `<config folder>/logs/iox_stats.log` (rotated, max 5 MB total), captures
  startup, the temperature helper install, and uncaught errors. Menu item **Open Log Folder**, CLI
  `--show-log` prints its path.
- **About IOX Stats** dialog (version, short disclaimer, link to the GitHub page).
- **Start Hidden** menu checkbox / `--start-hidden`: start with no window, menu bar only - independent of
  Launch at Login (which controls whether IOX Stats starts automatically at all).

### Changed
- `MAX_TRAY_METRICS` raised from 4 to 6 (rotation makes more values practical without crowding the menu bar).

### Known limitations
- Menu bar rotation, the log file location and the About dialog are not yet verified on a real Mac.
- The macOS gallery widget (`macos-widgets/`) is still unverified on real hardware (see v0.4.0 / v0.5.0 notes).

## [0.5.0] - 2026-09-20

**Live data for the widgets and a working CPU temperature.**

### Added
- **CPU temperature helper setup (macOS).** macOS needs no driver for this: a small user-space tool (`macmon` on
  Apple Silicon, `osx-cpu-temp` on Intel) reads the sensors. IOX Stats now finds it in the Homebrew folders (also
  when started at login), asks once on first start and installs it through Homebrew - no sudo. New menu item
  **Set Up CPU Temperature...**, command `--install-helpers` and `scripts/setup_macos.sh`.
- **Desktop Widget Mode** (menu item, `--desktop`): frameless glass widgets behind your windows, live every
  second, draggable, position remembered.
- **Live data in the macOS widget gallery widget:** the app shares its values via
  `~/Library/Application Support/IOXStats/snapshot.json`; the widget reads them when fresh, measures on its own
  otherwise. New widget value **CPU Temperature**.
- The widget host app asks macOS to refresh the widgets every 15 seconds while it runs and shows where the data
  comes from; opt-in **Start this app when I log in** toggle (`SMAppService`).
- Settings `share_with_widgets`, `desktop_mode`, `window_pos`, `helper_prompt_done`.

### Changed
- The widget asks for a refresh every minute instead of every five (macOS may still throttle).
- The widget gets a read-only *temporary exception* entitlement for the `IOXStats` folder in Application Support
  (fine for self-built apps, not for the Mac App Store).
- The first-run questions (launch at login, temperature helper) share one flow; both can be redone from the menu.

### Known limitations
- Gallery widgets can never refresh every second: macOS budgets widget reloads. Use the window, the menu bar item
  or Desktop Widget Mode for per-second values.
- Without the IOX Stats app running, the gallery widget has no CPU temperature (shows `--`).
- Desktop Widget Mode has no blur-behind (the cards are translucent glass over your wallpaper).
- Still **not verified on a real Mac**: the Swift widget, the native status item, the Homebrew install flow and the
  desktop window behaviour were written and unit-tested without one. Please report problems.

## [0.4.0] - 2026-09-19

**Widgets in the macOS widget gallery.** New native WidgetKit project in `macos-widgets/`: the IOX Stats
widget can be added to the desktop and Notification Center next to Apple's own widgets.

### Added
- **macOS widget gallery widget "System Status"** (Swift / SwiftUI / WidgetKit), small and medium.
- **Edit Widget** lets you choose the display - **Rings, Bars or Numbers only** - and up to six values
  (CPU, Memory, Swap, Disk, Ping, Download, Upload, Battery, Uptime, Thermal State). Limits per widget are the
  same as in the window: small 2 rings / 3 bars / 3 numbers, medium 4 rings / 4 bars / 6 numbers.
- Native look: system fonts and colours, SF Symbols, standard widget background, accented / tinted widget mode.
- Small host app "IOX Stats" that carries the extension; XcodeGen spec (`macos-widgets/project.yml`),
  build instructions in `macos-widgets/README.md`.
- CI job `widgets` compiles the Swift project on macOS; new tests keep the Swift limits, version and files in sync
  with the Python app; `scripts/check_version.py` also checks the widget version.

### Changed
- Version numbers of the Python app and the widget project are kept identical.

### Known limitations
- The widget project was written without access to a Mac and has **not been run on a real Mac yet**; its build is
  only verified by the new CI job. Please report Xcode errors.
- Widgets are refreshed by macOS every few minutes, not live. The live readout stays in the menu bar item.
- The widget cannot show the CPU temperature (no public API in the widget sandbox); it offers Thermal State.
- Building needs Xcode (free) and an Apple ID / signing team; the widget is not distributed as a ready-made app.
- The widget and the Python app do not share settings.

## [0.3.1] - 2026-09-19

Menu bar fix for macOS.

### Fixed
- **macOS menu bar: text was tiny and several values overlapped.** Qt squeezes every tray icon into a
  small square on macOS, so the wide text picture was shrunk and cramped. The menu bar now uses a native
  status item (system menu bar font, correct size, light/dark aware, orange / red when a value is high,
  tabular digits so nothing jumps). Needs `pyobjc-framework-Cocoa` (already in `requirements.txt`);
  without it a readable square ring icon is used instead of the unreadable wide one.
- The **Widgets** submenu is now refreshed when the layout changes instead of while the menu opens
  (native macOS menus ignore changes made at that moment). Old submenus are released on rebuild.

### Added
- The menu opens directly below the menu bar item. Tooltip shows all values.
- `IOX_STATS_NO_NATIVE_STATUSITEM=1` forces the previous Qt tray icon (for troubleshooting).

### Known limitations
- The native macOS menu bar item is covered by tests with a stand-in only; it is not yet verified on a real Mac.
- The widgets live in the IOX Stats window. They cannot be added to the macOS widget gallery (Notification
  Center / desktop): that needs a native Swift WidgetKit extension, which a Python app cannot provide.

## [0.3.0] - 2026-09-19

You decide what you see: every widget can now be shown as rings, bars or plain numbers, and you pick
which values it shows - limited by what fits into a small or medium widget.

### Added
- **Display style per widget**: Detailed, Rings, Bars or Numbers only.
- **Choose the values of each widget** (CPU, temperature, memory, swap, disk, ping, download, upload,
  battery, uptime). The number of values is limited by size and style:

  | Style | Small | Medium |
  |---|---|---|
  | Detailed | 1 | 2 |
  | Rings | 2 | 4 |
  | Bars | 3 | 4 |
  | Numbers only | 3 | 6 |

  Values that would not fit are greyed out in the menu; the last remaining value cannot be removed.
- **Right-click any widget** (or use the menu bar / tray menu "Widgets") to change size, display style and
  values, move the widget earlier / later, remove it, add a new one (up to 12) or reset the layout.
- **Layout presets**: Detailed, Rings, Bars, Numbers only, Mixed.
- New values available for widgets: swap, download and upload as separate values, ping and temperature as bars.
- `--layout <preset>` for `--screenshot`; new screenshots of all presets in `docs/screenshots/`.
- The layout is saved in `settings.json` (`widgets`); files from older versions get the default layout.

### Changed
- The dashboard is built from a layout list instead of a fixed set of widgets; the window resizes to fit.
- Switching size or style keeps as many values as fit (in their order).

### Known limitations
- The macOS blur-behind, the menu bar rendering and login autostart are still not verified on real Macs.
- The layout menu is a context menu; there is no drag-and-drop arranging yet.

## [0.2.0] - 2026-09-19

Apple look & feel: the widgets now follow the iOS / macOS widget design (glass surface, system
typography and colours, SF-Symbols-style icons) so they sit next to native widgets without standing out.
Plus opt-in launch at login.

### Added
- **Launch at Login** - opt-in and reversible. Menu item "Launch at Login" (checkbox) in the menu bar / tray
  menu, plus a one-time question on first launch (default answer: No). macOS: LaunchAgent, Windows:
  per-user `Run` registry value, Linux: autostart `.desktop` entry - nothing system-wide, no admin rights.
  Autostart starts quietly in the menu bar (`--background`, no dashboard window).
- **Glass surface**: translucent widget cards with top gloss, specular rim light, hairline edge and soft shadow.
  On macOS the window gets a real blur-behind (`NSVisualEffectView`, needs `pyobjc-framework-Cocoa`, which
  is installed by `requirements.txt` on macOS); elsewhere a simulated soft backdrop is painted.
  Switch off with `"glass": false` in `settings.json` or `IOX_STATS_NO_NATIVE_BLUR=1`.
- **Continuous "squircle" corners** (22 pt, 60 % smoothing) like iOS widgets, iOS grid geometry
  (158 pt small widget, 332 pt medium, 16 pt gaps and padding).
- **New displays**: Weather-style temperature gauge (green-to-red arc with indicator dot and
  Cool / Normal / Warm / Hot label), iOS-Storage-style disk widget (free space as hero number plus capsule bar),
  battery glyph with charge level and bolt, activity rings with gradient and tinted track,
  smooth area charts with an end marker, uptime as `3d 5h`, ping average / max, per-core capsules.
- Hero numbers are drawn with a large rounded number and a smaller unit (`14 ms`, `2.9 MB/s`, `180 GB`)
  and shrink automatically when they would not fit.
- `--background` command line flag; `glass` and `first_run_done` settings.
- Menu header showing the running version.
- Tests: autostart backends (macOS / Linux / Windows with a fake registry), squircle geometry, smooth curves,
  hero-text fitting, glass fallback and translucency, autostart menu toggling.

### Changed
- Colours are Apple's system colours with the alpha-based label hierarchy (primary / secondary / tertiary label,
  system fill). Each widget has its own accent (CPU blue, Memory purple, Disk teal, Ping green ...) and turns
  system orange / red only when a value needs attention.
- Typography uses the platform UI font (San Francisco on macOS, Segoe UI Variable on Windows) with
  SF Pro Rounded for hero numbers where available, and tabular figures so values do not jitter.
- The dashboard header was removed (window title shows the version); the window has a fixed, widget-gallery size.
- The menu bar / tray readout uses the same fonts and label colours.
- Minimum PySide6 version is now 6.7 (tabular figure support).

### Known limitations
- The macOS blur-behind and the menu bar icon have not yet been verified on real macOS hardware (the
  simulated glass and all drawing code are tested headlessly). If the blur misbehaves, set `"glass": false`.
- Windows uses the simulated glass backdrop (no acrylic / Mica yet).
- macOS still shows a Dock icon while running (menu-bar-only mode is planned).

## [0.1.0] - 2026-09-18

First tagged release: a working dashboard with iOS-style widgets and a live menu bar / tray readout.

### Added
- **Dashboard** with iOS home-screen style widgets on a 4-column grid (small 1x1 and medium 2x1 cards,
  rounded corners, soft borders): CPU ring, Memory ring (used / total), Temperature gauge, Disk usage bar,
  Network (download / upload with sparklines), Ping (status dot, latency, history), per-core CPU bars,
  Uptime and Battery.
- **Light and dark theme** using the iOS system colours; follows the operating system by default,
  can be forced via the tray menu (Appearance) or `--theme`.
- **Menu bar / tray readout**: choose up to four values (CPU, CPU temperature, Memory, Disk, Ping,
  Download, Upload, Battery). macOS/Linux show live text such as `CPU 12%  T 54°C  Ping 18 ms`;
  Windows shows a compact status ring with the first value and the rest in the tooltip.
  Values turn orange/red when they reach warning / critical levels.
- **Ping** measured as TCP connect latency (default `1.1.1.1:443`) in a background thread - no admin
  rights and no UI freezes; shows "offline" when there is no connection.
- **CPU temperature**: `psutil` sensors on Linux; on macOS via the optional helpers
  [`macmon`](https://github.com/vladkens/macmon) (Apple Silicon) or `osx-cpu-temp` (Intel) - no sudo needed.
  Without a sensor the widget shows "n/a" plus an install hint.
- Persistent settings (`settings.json` in the platform config directory).
- CLI: `--version`, `--once` (JSON snapshot), `--screenshot PNG` (headless render, `--demo` for synthetic data),
  `--theme`, `--no-tray`.
- Automated tests (33): collectors, metrics, history, settings, temperature parsing and headless UI tests
  (all widgets paint, theme switch, tray menu limits, tray icon rendering, close-to-tray, screenshot CLI, version/changelog/release-notes consistency, versioned ZIP).
- GitHub Actions: CI on Linux / macOS / Windows and a tag-triggered release workflow that builds
  app bundles and publishes a GitHub Release from `docs/release-notes/`.
- Release tooling: `scripts/check_version.py` (version / changelog / release-notes consistency)
  and `scripts/package_zip.py` (versioned source ZIP).

### Known limitations
- The macOS menu bar text icon and the Windows compact tray icon are rendered and unit-tested headlessly
  but have not yet been verified on real macOS / Windows machines.
- macOS shows a Dock icon while running (menu-bar-only mode is planned).
- No login-item / autostart option yet.

[Unreleased]: https://github.com/OWNER/IOX_Stats/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/OWNER/IOX_Stats/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/OWNER/IOX_Stats/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/OWNER/IOX_Stats/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/OWNER/IOX_Stats/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/OWNER/IOX_Stats/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/OWNER/IOX_Stats/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/OWNER/IOX_Stats/releases/tag/v0.1.0
