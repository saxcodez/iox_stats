# Project status

Living document: what works, what is verified on real hardware, what is next. Updated with every release.

**Current version:** 1.0.0 · **Owner:** [saxcodez](https://github.com/saxcodez) ·
**License:** [PolyForm Noncommercial 1.0.0](../LICENSE) · **Platform:** macOS 14+ (Apple Silicon & Intel)

## Components

| Component | Tech | Where |
|---|---|---|
| App: menu bar item, glass widget window, collectors | Python 3.9+, PySide6 (Qt), psutil, pyobjc | `iox_stats/` |
| Widget gallery widget + small host app | Swift, SwiftUI, WidgetKit, AppIntents | `macos-widgets/` |
| CPU temperature | SoC sensors via IOHID (Apple Silicon), `macmon` / `osx-cpu-temp` via Homebrew | `iox_stats/iohid_temp.py`, `temperature.py`, `helpers.py` |
| Data hand-over app -> widget | `snapshot.json`, written every ~2 s | `iox_stats/share.py`, `macos-widgets/Shared/` |

## Verified on real hardware

Legend: ✅ confirmed · 🟡 works, details still open · ⬜ not tested yet

Reference machine: macOS 26.3.2, Apple Silicon, Xcode 26.6. Release test for 1.0.0 by the owner on 2026-09-23.

| Area | Status | Notes |
|---|---|---|
| Setup (`setup_macos.sh`), app start, menu bar readout | ✅ | paste Terminal commands without `#` comments (zsh) |
| Menu bar: 2 / 1 value, rotation, settings menu | ✅ | |
| Glass widget window, light / dark, iOS Green palette | ✅ | |
| Menu bar app at login (`start_menubar.sh`, LaunchAgent) | ✅ | fixed in 0.10.0 |
| Widget: build, team signing, install (`install_widgets.sh`) | ✅ | |
| Widget appears in Edit Widgets and shows values | ✅ | since 0.9.1 (sandbox fix) |
| Widget app: settings page, Done button, glass background | ✅ | |
| CPU temperature on Apple Silicon | 🟡 | works in the release test; which source (SoC sensors / macmon) each chip uses is being collected - send `--diagnose` |
| Start Hidden, About, log file | 🟡 | shipped, not explicitly tested yet |
| Intel Macs (`osx-cpu-temp`) | ⬜ | test reports wanted |
| M1 / M2 / M3 / M5 sensor names | ⬜ | test reports wanted |
| GitHub Actions (CI, release) | ⬜ | run on the first push |

## Automated tests

Python side: headless UI tests with pytest (`QT_QPA_PLATFORM=offscreen python -m pytest`), run in CI on Ubuntu
and macOS. They cover collectors, layouts, menu bar logic, settings, snapshot hand-over, helper install flow (with
fakes), and keep the Swift project in sync (versions, value lists, size limits). The Swift code is compiled by
the `widgets` CI job.

## Known limitations

- Gallery widgets refresh when macOS allows it - never every second. Live values: menu bar and window.
- Without the running app the widget has no CPU temperature (sandbox).
- The widget reads the app's data through a temporary-exception entitlement: fine for self-built installs, not
  accepted by the Mac App Store. An App Group would be the long-term fix.
- No downloadable app yet - install from source (three scripts, see the README). The widget needs Xcode and a free Apple ID.

## Next

1. Downloadable DMG: one signed app, no Terminal, temperature set up automatically
2. Community test reports (Intel, other Apple Silicon generations)
3. Ideas from the README vision: AI usage meter with reset time, time to home, device batteries

See the roadmap in the [README](../README.md#roadmap) and the [CHANGELOG](../CHANGELOG.md).
