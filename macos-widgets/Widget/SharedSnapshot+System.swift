import Foundation

/// Widget side: turns the shared file into the widget's own value type (which needs SwiftUI types, so it is
/// not part of the file that the host app shares).
extension SharedSnapshot {
    /// The widget's own value type.
    var systemSnapshot: SystemSnapshot {
        var s = SystemSnapshot()
        s.cpu = cpu
        s.temperature = temperature
        s.memory = memory
        s.swap = swap
        s.disk = disk
        s.pingMs = pingMs
        s.pingMeasured = !(pingPending ?? false)
        s.downBytesPerSecond = netDownBps
        s.upBytesPerSecond = netUpBps
        s.battery = battery
        s.charging = charging ?? false
        s.uptime = uptimeS
        s.thermal = ProcessInfo.processInfo.thermalState
        return s
    }
}
