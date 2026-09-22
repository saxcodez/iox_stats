import Foundation

/// Live values written by the IOX Stats app (the Python one) to
/// `~/Library/Application Support/IOXStats/snapshot.json`, about every two seconds.
///
/// The widget cannot measure a CPU temperature itself (sandbox, no helper tools). The Python app can, so the widget
/// prefers this file whenever it is fresh and falls back to its own measurements otherwise.
struct SharedSnapshot: Decodable {
    var schema: Int?
    var timestamp: Double           // seconds since 1970
    var cpu: Double?
    var temperature: Double?
    var memory: Double?
    var swap: Double?
    var disk: Double?
    var pingMs: Double?
    var pingOk: Bool?
    var pingPending: Bool?
    var netDownBps: Double?
    var netUpBps: Double?
    var battery: Double?
    var charging: Bool?
    var uptimeS: Double?
}

enum SharedSnapshotStore {
    /// Older than this and the Python app is assumed to be closed.
    static let maxAge: TimeInterval = 120

    /// The real home directory. Inside the sandbox `NSHomeDirectory()` is the container, `getpwuid` is not.
    static func fileURL() -> URL? {
        guard let entry = getpwuid(getuid()), let dir = entry.pointee.pw_dir else { return nil }
        return URL(fileURLWithPath: String(cString: dir), isDirectory: true)
            .appendingPathComponent("Library/Application Support/IOXStats/snapshot.json")
    }

    static func load() -> SharedSnapshot? {
        guard let url = fileURL(), let data = try? Data(contentsOf: url) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(SharedSnapshot.self, from: data)
    }

    /// The shared values if the file exists and is fresh.
    static func loadFresh(maxAge: TimeInterval = SharedSnapshotStore.maxAge, now: Date = Date()) -> SharedSnapshot? {
        guard let shared = load() else { return nil }
        let age = now.timeIntervalSince1970 - shared.timestamp
        return (age >= -5 && age <= maxAge) ? shared : nil
    }
}

/// How the menu bar app is started (written by it at every start, kept when it quits). Lets the widget app show
/// a copyable start command while the menu bar app is not running.
struct LaunchInfo: Decodable {
    var command: String
    var appVersion: String?
    var projectDir: String?

    static func load() -> LaunchInfo? {
        guard let url = SharedSnapshotStore.fileURL()?.deletingLastPathComponent().appendingPathComponent("launch.json"),
              let data = try? Data(contentsOf: url) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(LaunchInfo.self, from: data)
    }
}
