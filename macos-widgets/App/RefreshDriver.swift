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

    @Published private(set) var lastRefresh: Date?
    @Published private(set) var launchInfo: LaunchInfo?

    /// How often the app asks macOS to reload the widgets (seconds). Saved between launches.
    static let intervalChoices = [15, 30, 60, 300]
    private static let intervalKey = "refreshIntervalSeconds"
    @Published var intervalSeconds: Int {
        didSet {
            UserDefaults.standard.set(intervalSeconds, forKey: Self.intervalKey)
            if timer != nil {
                stop()
                start()
            }
        }
    }

    private var timer: Timer?

    init() {
        let saved = UserDefaults.standard.integer(forKey: Self.intervalKey)
        intervalSeconds = Self.intervalChoices.contains(saved) ? saved : 15
    }

    func start() {
        guard timer == nil else { return }
        tick()
        timer = Timer.scheduledTimer(withTimeInterval: TimeInterval(intervalSeconds), repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    var menuBarAppRunning: Bool {
        if case .pythonApp = source { return true }
        return false
    }

    func tick() {
        launchInfo = LaunchInfo.load()
        if let shared = SharedSnapshotStore.loadFresh() {
            source = .pythonApp(age: max(0, Date().timeIntervalSince1970 - shared.timestamp),
                                hasTemperature: shared.temperature != nil)
        } else {
            source = .widgetOnly
        }
        WidgetCenter.shared.reloadAllTimelines()
        lastRefresh = Date()
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
