import AppKit
import SwiftUI

struct SettingsView: View {
    @ObservedObject var driver: RefreshDriver
    let showGuide: () -> Void

    private var version: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                HeaderView(subtitle: "Settings")
                Button("Done") { closeWindow() }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.defaultAction)
            }
            .padding([.horizontal, .top], 24)
            .padding(.bottom, 8)

            Form {
                Section {
                    step("1", "Right-click the desktop and choose Edit Widgets (or Notification Center > Edit Widgets).")
                    step("2", "Search for IOX Stats and drag it onto the desktop - small or medium.")
                    step("3", "Right-click the widget > Edit Widget: choose Rings, Bars or Numbers and the values.")
                } header: {
                    Text("Add the widget")
                } footer: {
                    Text("Add it several times to show different values. Small: 2 rings / 3 bars / 3 numbers, medium: 4 / 4 / 6.")
                }

                Section {
                    statusRow
                    if !driver.menuBarAppRunning {
                        if let info = driver.launchInfo {
                            Text(info.command)
                                .font(.system(.callout, design: .monospaced))
                                .textSelection(.enabled)
                                .fixedSize(horizontal: false, vertical: true)
                            Button("Copy Start Command") {
                                NSPasteboard.general.clearContents()
                                NSPasteboard.general.setString(info.command, forType: .string)
                            }
                        } else {
                            Text("In the IOX Stats project folder, run: bash scripts/start_menubar.sh")
                                .font(.callout)
                                .textSelection(.enabled)
                        }
                    }
                } header: {
                    Text("Menu bar app")
                } footer: {
                    Text("The menu bar readout and its settings - which values, 2 or 1 value, CPU temperature setup, appearance - are in the IOX Stats menu bar item: click it in the menu bar. It also feeds the widget with live values and the CPU temperature. \"bash scripts/start_menubar.sh\" starts it at every login.")
                }

                Section {
                    Picker("Refresh widgets every", selection: $driver.intervalSeconds) {
                        ForEach(RefreshDriver.intervalChoices, id: \.self) { seconds in
                            Text(label(for: seconds)).tag(seconds)
                        }
                    }
                    HStack {
                        Button("Refresh Now") { driver.tick() }
                        Spacer()
                        if let last = driver.lastRefresh {
                            Text("Last request: \(last.formatted(date: .omitted, time: .standard))")
                                .foregroundStyle(.secondary)
                                .font(.callout)
                        }
                    }
                } header: {
                    Text("Refresh")
                } footer: {
                    Text("The app asks macOS to reload the widgets while it runs (you can close this window). macOS decides when it really happens, so gallery widgets are never second-by-second - the menu bar item is.")
                }

                Section("General") {
                    Toggle("Start this app when I log in", isOn: Binding(
                        get: { driver.launchAtLogin },
                        set: { driver.setLaunchAtLogin($0) }
                    ))
                    if let error = driver.loginError {
                        Text(error).font(.footnote).foregroundStyle(.red)
                    }
                }

                Section("Help") {
                    Button("How to add the widget") { showGuide() }
                    Button("Open Desktop & Dock settings (Show widgets)") {
                        if let url = URL(string: "x-apple.systempreferences:com.apple.Desktop-Settings.extension") {
                            NSWorkspace.shared.open(url)
                        }
                    }
                    Link("IOX Stats on GitHub", destination: URL(string: "https://github.com/saxcodez/iox_stats")!)
                }
            }
            .formStyle(.grouped)

            HStack {
                Button("Quit Widget App") { NSApplication.shared.terminate(nil) }
                    .help("Stops the refresh requests. The widgets stay on the desktop.")
                Spacer()
                Button("Done") { closeWindow() }
                    .buttonStyle(.borderedProminent)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 8)

            Text("IOX Stats \(version) - a non-commercial community project by saxcodez")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity)
                .padding(.bottom, 12)
        }
        .frame(minHeight: 720)
    }

    /// Closes the window; the app keeps running in the background and keeps refreshing the widgets.
    private func closeWindow() {
        NSApplication.shared.keyWindow?.close()
    }

    private func step(_ number: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(number)
                .font(.caption.weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 18, height: 18)
                .background(Circle().fill(.blue))
            Text(text)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func label(for seconds: Int) -> String {
        seconds < 60 ? "\(seconds) seconds" : (seconds == 60 ? "1 minute" : "\(seconds / 60) minutes")
    }

    @ViewBuilder
    private var statusRow: some View {
        switch driver.source {
        case .pythonApp(let age, let hasTemperature):
            Label(hasTemperature
                  ? "Live data from the IOX Stats menu bar app (\(Int(age)) s old), including the CPU temperature."
                  : "Live data from the IOX Stats menu bar app (\(Int(age)) s old). No CPU temperature yet: choose \"Set Up CPU Temperature...\" in its menu.",
                  systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
                .fixedSize(horizontal: false, vertical: true)
        case .widgetOnly:
            Label("The IOX Stats menu bar app is not running (start it with python -m iox_stats). Until then the widgets measure on their own, without the CPU temperature.",
                  systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
