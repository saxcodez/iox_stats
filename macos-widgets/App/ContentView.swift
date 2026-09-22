import SwiftUI

struct ContentView: View {
    @StateObject private var driver = RefreshDriver()

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                Image(systemName: "gauge.with.dots.needle.67percent")
                    .font(.system(size: 34))
                    .foregroundStyle(.blue)
                VStack(alignment: .leading, spacing: 2) {
                    Text("IOX Stats Widgets")
                        .font(.title2.weight(.semibold))
                    Text("System status in the macOS widget gallery")
                        .foregroundStyle(.secondary)
                }
            }

            VStack(alignment: .leading, spacing: 10) {
                step("1", "Right-click the desktop (or open Notification Center) and choose Edit Widgets.")
                step("2", "Search for IOX Stats and drag the widget onto your desktop.")
                step("3", "Right-click the widget and choose Edit Widget: pick Rings, Bars or Numbers only and the values it shows.")
            }

            Text("Small widgets show up to 2 rings, 3 bars or 3 numbers. Medium widgets show up to 4 rings, 4 bars or 6 numbers. Add the widget several times to show different values.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Divider()

            statusRow
            Text("Keep this app running (you can close its window) and it asks macOS to refresh the widgets every \(Int(RefreshDriver.interval)) seconds. macOS decides how often that really happens, so gallery widgets are a snapshot. For values that change every second use the IOX Stats menu bar item or its desktop widget mode.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Toggle("Start this app when I log in", isOn: Binding(
                get: { driver.launchAtLogin },
                set: { driver.setLaunchAtLogin($0) }
            ))
            if let error = driver.loginError {
                Text(error).font(.footnote).foregroundStyle(.red)
            }
        }
        .padding(24)
        .frame(width: 480)
        .onAppear { driver.start() }
    }

    @ViewBuilder
    private var statusRow: some View {
        switch driver.source {
        case .pythonApp(let age, let hasTemperature):
            Label(hasTemperature
                  ? "Live data from the IOX Stats app (updated \(Int(age)) s ago), including the CPU temperature."
                  : "Live data from the IOX Stats app (updated \(Int(age)) s ago). No CPU temperature yet: choose \"Set Up CPU Temperature...\" in its menu.",
                  systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
                .fixedSize(horizontal: false, vertical: true)
        case .widgetOnly:
            Label("The IOX Stats app is not running. The widgets measure on their own, without the CPU temperature.",
                  systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func step(_ number: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(number)
                .font(.headline)
                .foregroundStyle(.white)
                .frame(width: 22, height: 22)
                .background(Circle().fill(.blue))
            Text(text)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
