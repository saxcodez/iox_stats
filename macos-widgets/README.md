# IOX Stats - macOS widget gallery (WidgetKit)

Native macOS widgets for the **widget gallery** (desktop, Notification Center), written in Swift / SwiftUI.
Apple only allows widgets that are WidgetKit extensions inside an app, so this part is a small native project
next to the Python app. The Python app keeps the live **menu bar readout**, the IOX Stats window and the
**desktop widget mode** (glass widgets that really tick every second).

What you get:

- **System Status** widget in *small* and *medium*.
- In **Edit Widget** you choose the display - **Rings, Bars or Numbers only** - and up to six values
  (CPU, **CPU Temperature**, Memory, Swap, Disk, Ping, Download, Upload, Battery, Uptime, Thermal State).
- Values that do not fit are ignored, exactly like the window: small = 2 rings / 3 bars / 3 numbers,
  medium = 4 rings / 4 bars / 6 numbers.
- Add the widget several times to show different values.
- **Live data from the IOX Stats app:** while the Python app runs it writes its current values (incl. the CPU
  temperature) to `~/Library/Application Support/IOXStats/snapshot.json`. The widget reads that file when it is
  fresh (< 2 minutes old) and measures on its own otherwise.
- Native look: system fonts, system colours, SF Symbols and the standard widget background, so it sits
  next to Apple's own widgets.

## Requirements

- macOS 14 (Sonoma) or newer, **Xcode 15 or newer** (free in the App Store)
- An Apple ID added in Xcode (*Xcode > Settings > Accounts*) - a free personal team is enough for your own Mac
- [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen`

## Build and install

```bash
cd macos-widgets
xcodegen generate
open IOXStats.xcodeproj
```

In Xcode:

1. Select the project **IOXStats** > target **IOXStats** > *Signing & Capabilities* > choose your **Team**.
2. Do the same for the target **IOXStatsWidgets**.
3. If Xcode says the bundle identifier is not available, change `com.saxcodez.IOXStats` (and
   `com.saxcodez.IOXStats.Widgets`) to your own, e.g. `com.yourname.IOXStats` - the widget id must start with the
   app id. Best done in `project.yml` (`PRODUCT_BUNDLE_IDENTIFIER`), then run `xcodegen generate` again.
4. Choose the scheme **IOXStats**, destination **My Mac**, press **Run** (Cmd+R). A small window opens.
5. Right-click the desktop > **Edit Widgets** > search **IOX Stats** > drag it onto the desktop.
6. Right-click the widget > **Edit Widget** > choose display and values.

To keep it: *Product > Archive*, or copy the built `IOX Stats.app` (Product > Show Build Folder in Finder) to
*Applications* and open it once.

### Without XcodeGen

*File > New > Project > macOS > App* (SwiftUI, name `IOXStats`), then *File > New > Target > Widget Extension*
(name `IOXStatsWidgets`, **untick** "Include Live Activity" and "Include Configuration App Intent").
Delete the generated Swift files of both targets, drag in `App/*.swift` and `Widget/*.swift`, set the widget
target's entitlements to `Widget/Widget.entitlements` (App Sandbox + Outgoing Connections) and the deployment
target to macOS 14.

## Good to know

- **Gallery widgets are not per-second live.** macOS decides when a widget refreshes; the app can only *ask*.
  The widget asks for a new timeline every minute, and this small host app calls `reloadAllTimelines()` every
  15 seconds while it is running (the window says whether it is receiving live data). macOS may delay some of
  these reloads - that is a limit of every widget on macOS. For values that change every second use the menu bar
  item or the **Desktop Widget Mode** of the Python app.
- **CPU temperature.** macOS offers no public temperature API and the widget sandbox cannot run helper tools.
  The Python app reads it (it installs `macmon` / `osx-cpu-temp` with Homebrew after asking once - no kernel
  driver, no admin password) and hands it to the widget through `snapshot.json`. Without the Python app the
  temperature shows `--`; the widget still offers **Thermal State** (OK / Warm / Hot).
- **File access.** The widget reads that one folder through a read-only *temporary exception* entitlement
  (`com.apple.security.temporary-exception.files.home-relative-path.read-only`). That is fine for apps you build
  yourself; the Mac App Store would not accept it.
- **Start at login.** The toggle in the host app window uses `SMAppService` and is off by default.
- **Ping** needs the *Outgoing Connections* entitlement (already set) and does a TCP connect to 1.1.1.1:443.
- The Python app and the widgets are independent: settings of one do not change the other.

## Status

Written without access to a Mac: the Swift code is checked by a GitHub Actions build (`widgets` job in
`.github/workflows/ci.yml`) but has **not been run on a real Mac yet**. If Xcode shows an error, send it and it
will be fixed in the next version.
