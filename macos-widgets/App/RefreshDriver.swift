import Foundation
import ServiceManagement
import WidgetKit

/// Keeps the widgets as fresh as macOS allows and reports where their data comes from.
///
/// A widget cannot refresh itself every second: macOS budgets the reloads. The app can ask for them, and does so
/// every few seconds while it runs. macOS may still delay some of them.
@MainActor
final class RefreshDriver: ObservableObject {
    enum Source {
        case pythonApp(age: TimeInterval, hasTemperature: Bool)
        case widgetOnly
    }

    @Published private(set) var source: Source = .widgetOnly
    @Published private(set) var launchAtLogin = SMAppService.mainApp.status == .enabled
    @Published private(set) var loginError: String?

    private var timer: Timer?
    static let interval: TimeInterval = 15

    func start() {
        guard timer == nil else { return }
        tick()
        timer = Timer.scheduledTimer(withTimeInterval: Self.interval, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    func tick() {
        if let shared = SharedSnapshotStore.loadFresh() {
            source = .pythonApp(age: max(0, Date().timeIntervalSince1970 - shared.timestamp),
                                hasTemperature: shared.temperature != nil)
        } else {
            source = .widgetOnly
        }
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// Opt-in: start this small app (and with it the refreshing) when the user logs in.
    func setLaunchAtLogin(_ enabled: Bool) {
        do {
            if enabled { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            loginError = nil
        } catch {
            loginError = error.localizedDescription
        }
        launchAtLogin = SMAppService.mainApp.status == .enabled
    }
}
