# Project status

Living document: what works, what is verified on real hardware, what is next. Updated with every release.

**Current version:** 0.8.0 (pre-release) · **Owner:** [saxcodez](https://github.com/saxcodez) ·
**License:** [PolyForm Noncommercial 1.0.0](../LICENSE) · **Platform:** macOS 14+ (Apple Silicon & Intel)

## Components

| Component | Tech | Where |
|---|---|---|
| App: menu bar item, glass widget window, collectors | Python 3.9+, PySide6 (Qt), psutil, pyobjc | `iox_stats/` |
| Widget gallery widget + small host app | Swift, SwiftUI, WidgetKit, AppIntents | `macos-widgets/` |
| CPU temperature helper | `macmon` (Apple Silicon) / `osx-cpu-temp` (Intel) via Homebrew | `iox_stats/helpers.py` |
| Data hand-over app -> widget | `snapshot.json`, written every ~2 s | `iox_stats/share.py`, `macos-widgets/Shared/` |

## Verified on real hardware

Legend: ✅ confirmed · 🟡 partly / pending · ⬜ not tested yet

| Area | Status | Notes |
|---|---|---|
| App starts, menu bar readout | ✅ | macOS 26, Apple Silicon (v0.5.0) |
| Menu bar: 2 / 1 value, rotation of extra values | ⬜ | new in v0.7.0 |
| Glass widget window, light / dark | ✅ | |
| Setup script `scripts/setup_macos.sh` | ✅ | paste commands without `#` comments (zsh) |
| CPU temperature via `macmon` | ⬜ | |
| CPU temperature via `osx-cpu-temp` (Intel) | ⬜ | |
| Swift widget **compiles** | ✅ | macOS 26.3.2, Xcode 26.6, Apple Silicon (2026-09-22, `build_widgets.sh`) |
| Widget **appears in Edit Widgets** | 🟡 | needs signed install: `install_widgets.sh` (new in v0.8.0) |
| Widget shows live values + temperature | ⬜ | |
| Launch at Login (LaunchAgent) | ⬜ | |
| Start Hidden, About, log file | ⬜ | |
| Intel Macs | ⬜ | test reports wanted |
| GitHub Actions (CI, release) | ⬜ | run on first push |

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
- No downloadable app yet - install from source.

## Next

1. Widget in the gallery on a real Mac (`install_widgets.sh`), then live data + temperature in the widget
2. DMG: signed app bundle, temperature helper set up during install
3. First GitHub release (`v1.0.0` once the table above is green)

See the roadmap in the [README](../README.md#roadmap) and the [CHANGELOG](../CHANGELOG.md).
