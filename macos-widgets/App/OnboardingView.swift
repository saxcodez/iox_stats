import SwiftUI

struct OnboardingView: View {
    let onContinue: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HeaderView(subtitle: "System status in the macOS widget gallery")

            VStack(alignment: .leading, spacing: 10) {
                step("1", "Right-click the desktop and choose Edit Widgets (or open Notification Center and click Edit Widgets at the bottom).")
                step("2", "Search for IOX Stats and drag the widget onto your desktop.")
                step("3", "Right-click the widget and choose Edit Widget: pick Rings, Bars or Numbers only and the values it shows.")
            }

            Text("Small widgets show up to 2 rings, 3 bars or 3 numbers, medium widgets up to 4 rings, 4 bars or 6 numbers. Add the widget several times to show different values.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Text("For live values and the CPU temperature, keep the IOX Stats menu bar app running (python -m iox_stats).")
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack {
                Spacer()
                Button("Continue", action: onContinue)
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(24)
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
