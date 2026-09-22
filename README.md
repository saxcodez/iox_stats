<div align="center">

# IOX Stats

**Your Mac's vital signs, dressed like iOS widgets.**

CPU · Memory · Disk · Network · Ping · CPU temperature - live in the menu bar, as glass widgets,
and right in the macOS widget gallery.

![macOS](https://img.shields.io/badge/macOS-14%2B-000000?logo=apple&logoColor=white)
![Apple Silicon & Intel](https://img.shields.io/badge/Apple%20Silicon%20%26%20Intel-supported-555555)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Swift](https://img.shields.io/badge/Swift-WidgetKit-F05138?logo=swift&logoColor=white)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)
![Version](https://img.shields.io/badge/version-1.0.0-34C759)

</div>

---

> **A non-commercial community project by [saxcodez](https://github.com/saxcodez).**
> IOX Stats is built for the Mac community - free to use, free to tinker with, **not for sale**.
> All rights remain with the author (see [License & intent](#license--intent)). Questions, ideas, bug reports and
> requests are very welcome: [open an issue](https://github.com/saxcodez/iox_stats/issues/new/choose).

| Light | Dark |
|---|---|
| ![Dashboard light](docs/screenshots/dashboard-light.png) | ![Dashboard dark](docs/screenshots/dashboard-dark.png) |

## Why

macOS knows a lot more about your machine than it shows you. CPU temperature, per-core load, real network
throughput, swap pressure, latency - it is all there, but hidden behind private APIs, Terminal commands or
Activity Monitor tabs nobody opens. **IOX Stats is an attempt to implement system stats on the Mac as well as
possible** and to put exactly that hidden data where you actually look: the menu bar and your widgets.

Activity Monitor is great for forensics, not for a glance. The menu bar tools out there are either ugly, closed or
subscription-ware. IOX Stats wants to be the thing you would expect Apple to ship: native look, honest numbers,
no account, no telemetry, no nonsense - and open for anyone to read, learn from and improve.

## Vision - more than system stats

System stats are the start. The idea behind IOX Stats is **a glanceable home for the numbers you keep checking**,
in the menu bar and as native widgets. Planned and being explored:

- 🤖 **AI usage meter** - token / message usage for Claude and other AI assistants: how much is left, **when the
  limit resets**, as a menu bar value and as a widget.
- 🚗 **Estimated time to home** - travel time with current traffic, so you know when to leave.
- 🌡️ **Hidden hardware data** - fan speed, GPU load, power draw, SSD health, battery cycle count and health.
- 🎧 **Connected devices** - battery of AirPods, Magic Mouse, keyboard in the same widget style.
- 🌐 **Network insight** - which app is using the bandwidth right now, Wi-Fi signal and channel.
- 🔔 **Smart alerts** - a quiet notification when something stays red (CPU hot for 5 minutes, disk almost full).

**Got an idea? Want to build one of these?** Open an
[idea / feature request](https://github.com/saxcodez/iox_stats/issues/new/choose) - every suggestion is read,
and help with development is very welcome.

## Features

| | |
|---|---|
| **Menu bar readout** | Live every second. **2 values** side by side or **1 value**; pick up to 6, the rest rotate every 4 s so your other menu bar icons keep their place. Orange / red when things get hot, slow or full. |
| **Glass widgets** | Continuous corners, iOS widget grid, San Francisco, Apple system colours, light & dark. Each widget: **rings**, **bars**, **numbers** or **detailed** - and you pick the values. |
| **Widget gallery** | A native **WidgetKit** widget: right-click the desktop > *Edit Widgets* > *IOX Stats*. Fed with the app's live values, CPU temperature included. |
| **CPU temperature** | Apple Silicon: read straight from the SoC sensors - no tool, no driver, no `sudo`. Intel: one click installs a tiny helper via Homebrew. |
| **Your colours** | **iOS Green** like Apple's Batteries widget (default), Colorful, or one accent of your choice - in the app and in *Edit Widget*. Glass background like Apple's own widgets. |
| **Well-behaved** | Launch at Login and Start Hidden are opt-in. Log file for troubleshooting. Zero data collection - the only network traffic is the ping you can see. |

## How it works

```mermaid
flowchart LR
    subgraph mac[Your Mac]
        S[psutil<br/>CPU, RAM, disk, net] --> A
        H[SoC sensors / macmon /<br/>osx-cpu-temp: temperature] --> A
        P[TCP ping 1.1.1.1:443] --> A
        A[IOX Stats app<br/>Python + Qt] --> M[Menu bar item]
        A --> W[Glass widget window]
        A -- snapshot.json<br/>every 2 s --> G[WidgetKit widget<br/>Swift]
        G --> D[Desktop /<br/>Notification Center]
    end
```

The widget runs in Apple's sandbox and cannot read sensors or run helpers itself, so the app hands it the numbers
through a small JSON file. If the app is not running, the widget measures what the sandbox allows on its own.

## Quick start

Requirements: macOS 14+, Python 3.9+ (`brew install python`), optionally [Homebrew](https://brew.sh) for the
temperature helper and Xcode (free) for the widget gallery widget.

```bash
bash scripts/setup_macos.sh
```

```bash
source .venv/bin/activate
```

```bash
python -m iox_stats
```

The setup script creates a virtual environment, installs the packages and offers to install the temperature
helper. Paste commands one at a time - zsh chokes on `# comments` pasted after a command.

Let the menu bar item start by itself at every login (recommended - it also feeds the widget):

```bash
bash scripts/start_menubar.sh
```

### Widget gallery widget

```bash
brew install xcodegen
```

```bash
bash scripts/install_widgets.sh
```

Builds the Swift widget signed with your (free) Apple ID team, installs `IOX Stats.app` to `/Applications` and
registers the widget. Then: right-click the desktop > **Edit Widgets** > search **IOX Stats**.
Details and troubleshooting: [`macos-widgets/README.md`](macos-widgets/README.md).

## Using it

Click the menu bar item: dashboard, *Menu bar values* (pick values, **Show 2 / Show 1 value**), *Widgets*,
*Appearance*, **Launch at Login**, **Start Hidden**, **Set Up CPU Temperature...**, **About**, **Open Log Folder**.

Right-click any widget in the window to change its size, style and values:

| Style | Small | Medium |
|---|---|---|
| Detailed | 1 value | 2 values |
| Rings | 2 | 4 |
| Bars | 3 | 4 |
| Numbers only | 3 | 6 |

| Rings | Bars | Numbers |
|---|---|---|
| ![Rings](docs/screenshots/layout-rings.png) | ![Bars](docs/screenshots/layout-bars.png) | ![Numbers](docs/screenshots/layout-numbers.png) |

A note on "live": the menu bar and the window update every second. Gallery widgets are refreshed when **macOS**
decides - IOX Stats asks often, macOS answers when it likes. That is a platform limit, not a bug.

### Command line

```text
python -m iox_stats --version
python -m iox_stats --once              # one JSON snapshot to stdout
python -m iox_stats --start-hidden      # menu bar only
python -m iox_stats --install-helpers   # set up the CPU temperature helper
python -m iox_stats --show-log          # where is the log?
python -m iox_stats --diagnose          # where does each value come from (temperature!)
python -m iox_stats --enable-login      # start at login (also: --disable-login)
python -m iox_stats --screenshot out.png --theme dark --demo --layout rings
```

Settings: `~/Library/Application Support/IOXStats/settings.json` · Log: `~/Library/Application Support/IOXStats/logs/`

## Project status

Version 1.0 - the first public release. What is verified on real hardware and what is still open is tracked openly in
**[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)**. Every release: [CHANGELOG.md](CHANGELOG.md) and
[release notes](docs/release-notes/).

## Roadmap

**Next (1.x)**
- Downloadable **DMG**: one signed app, no Terminal, temperature set up for you
- Test reports from Intel Macs and more Apple Silicon generations
- Menu-bar-only app (no Dock icon)

**After that**
- Settings window: ping target, refresh rate, your own orange / red thresholds
- Top processes, GPU load, fan speed, per-interface network
- Notifications when something stays red (e.g. CPU hot for 5 minutes)
- Large widget, StandBy-style layouts
- Localisation, German first

**Ideas** (see [Vision](#vision---more-than-system-stats)): AI usage & reset meter, time to home with live
traffic, device batteries, per-app network. Got another one? [Tell us.](https://github.com/saxcodez/iox_stats/issues/new/choose)

## Contributing & requests

This project lives from feedback. The most valuable contribution right now is **a test report from your Mac**.

- **Bug?** Open a *Bug report* and attach the log (menu > *Open Log Folder*) plus macOS version and chip.
- **Idea or request?** Open a *Feature request* - requests of any kind (features, collaboration, licensing) are
  welcome there.
- **Code?** Read [CONTRIBUTING.md](CONTRIBUTING.md), fork, branch, test, pull request.

## License & intent

IOX Stats is **source-available for non-commercial use** under the
[PolyForm Noncommercial License 1.0.0](LICENSE). In plain words (the license text is what counts):

- ✅ Use it, study it, modify it, share it - for personal, hobby, educational and other non-commercial purposes.
- ❌ Selling it, bundling it into a paid product or offering it as a paid service is not allowed.
- © Copyright and all rights not granted by the license stay with **saxcodez**. For anything beyond
  non-commercial use, open an issue and ask.

This is not legal advice; it is the reason the license was chosen: a tool made with good intentions, for the
community, that nobody should be able to turn into a paywall.

IOX Stats is provided as-is, without warranty. It is not affiliated with or endorsed by Apple Inc.; macOS, Apple
Silicon and San Francisco are trademarks of Apple Inc.

<div align="center"><sub>Built with curiosity, too much coffee and a soft spot for rounded corners. - saxcodez</sub></div>
