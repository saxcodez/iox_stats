import SwiftUI

/// First launch: a short guide with a Continue button. After that: the settings page.
struct ContentView: View {
    @AppStorage("onboardingDone") private var onboardingDone = false
    @StateObject private var driver = RefreshDriver()

    var body: some View {
        Group {
            if onboardingDone {
                SettingsView(driver: driver, showGuide: { onboardingDone = false })
            } else {
                OnboardingView(onContinue: { onboardingDone = true })
            }
        }
        .frame(width: 500)
        .onAppear { driver.start() }
    }
}

/// Shared header for both pages.
struct HeaderView: View {
    let subtitle: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "gauge.with.dots.needle.67percent")
                .font(.system(size: 34))
                .foregroundStyle(.blue)
            VStack(alignment: .leading, spacing: 2) {
                Text("IOX Stats Widgets")
                    .font(.title2.weight(.semibold))
                Text(subtitle)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
    }
}
