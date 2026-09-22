import Darwin
import Foundation
import IOKit.ps
import Network

/// Reads the system values with public macOS APIs that work inside the widget sandbox.
/// Only what the widget actually shows is measured (a ping is only sent if Ping is selected).
enum SystemCollector {

    static func collect(needing kinds: Set<MetricKind>) async -> SystemSnapshot {
        var snap = SystemSnapshot()

        let needCPU = kinds.contains(.cpu)
        let needNet = kinds.contains(.download) || kinds.contains(.upload)

        // Start the ping first: it runs while we wait for the CPU / network samples.
        async let measuredPing: Double? = measurePing(if: kinds.contains(.ping))

        // CPU load and network rates need two samples a moment apart.
        let cpuBefore = needCPU ? cpuTicks() : nil
        let netBefore = needNet ? networkCounters() : [:]
        let started = Date()
        if needCPU || needNet {
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }
        let elapsed = max(0.2, Date().timeIntervalSince(started))

        if let a = cpuBefore, let b = cpuTicks() {
            let busy = b.busy &- a.busy
            let total = b.total &- a.total
            if total > 0 { snap.cpu = min(100, Double(busy) / Double(total) * 100) }
        }
        if needNet {
            let netAfter = networkCounters()
            var rx = 0.0
            var tx = 0.0
            for (name, before) in netBefore {
                if let after = netAfter[name] {
                    rx += Double(after.rx &- before.rx)     // 32-bit counters wrap around: &- is intended
                    tx += Double(after.tx &- before.tx)
                }
            }
            snap.downBytesPerSecond = rx / elapsed
            snap.upBytesPerSecond = tx / elapsed
        }

        if kinds.contains(.memory) { snap.memory = memoryPercent() }
        if kinds.contains(.swap) { snap.swap = swapPercent() }
        if kinds.contains(.disk) { snap.disk = diskPercent() }
        if kinds.contains(.uptime) { snap.uptime = uptimeSeconds() }
        if kinds.contains(.thermal) { snap.thermal = ProcessInfo.processInfo.thermalState }
        if kinds.contains(.battery), let b = batteryStatus() {
            snap.battery = b.percent
            snap.charging = b.charging
        }

        snap.pingMeasured = kinds.contains(.ping)
        snap.pingMs = await measuredPing
        return snap
    }

    // MARK: CPU

    private static func cpuTicks() -> (busy: UInt64, total: UInt64)? {
        var info = host_cpu_load_info()
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        let user = UInt64(info.cpu_ticks.0)
        let system = UInt64(info.cpu_ticks.1)
        let idle = UInt64(info.cpu_ticks.2)
        let nice = UInt64(info.cpu_ticks.3)
        return (user + system + nice, user + system + idle + nice)
    }

    // MARK: memory, swap, disk

    /// Like Activity Monitor's "Memory Used": app memory + wired + compressed.
    private static func memoryPercent() -> Double? {
        var stats = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        let pageSize = Double(getpagesize())
        let pages = Double(stats.internal_page_count) - Double(stats.purgeable_count)
            + Double(stats.wire_count) + Double(stats.compressor_page_count)
        let total = Double(ProcessInfo.processInfo.physicalMemory)
        guard total > 0 else { return nil }
        return min(100, max(0, pages * pageSize / total * 100))
    }

    private static func swapPercent() -> Double? {
        var usage = xsw_usage()
        var size = MemoryLayout<xsw_usage>.size
        guard sysctlbyname("vm.swapusage", &usage, &size, nil, 0) == 0 else { return nil }
        guard usage.xsu_total > 0 else { return 0 }
        return min(100, Double(usage.xsu_used) / Double(usage.xsu_total) * 100)
    }

    private static func diskPercent() -> Double? {
        let root = URL(fileURLWithPath: "/")
        let keys: Set<URLResourceKey> = [.volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey]
        if let values = try? root.resourceValues(forKeys: keys),
           let total = values.volumeTotalCapacity,
           let available = values.volumeAvailableCapacityForImportantUsage,
           total > 0 {
            return min(100, max(0, (1 - Double(available) / Double(total)) * 100))
        }
        if let attrs = try? FileManager.default.attributesOfFileSystem(forPath: "/"),
           let size = (attrs[.systemSize] as? NSNumber)?.doubleValue,
           let free = (attrs[.systemFreeSize] as? NSNumber)?.doubleValue,
           size > 0 {
            return min(100, max(0, (1 - free / size) * 100))
        }
        return nil
    }

    // MARK: network

    /// Byte counters of the Wi-Fi / Ethernet interfaces (en0, en1, ...), per interface.
    private static func networkCounters() -> [String: (rx: UInt32, tx: UInt32)] {
        var result: [String: (rx: UInt32, tx: UInt32)] = [:]
        var first: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&first) == 0, let head = first else { return result }
        defer { freeifaddrs(first) }

        var cursor: UnsafeMutablePointer<ifaddrs>? = head
        while let current = cursor {
            let entry = current.pointee
            let name = String(cString: entry.ifa_name)
            if name.hasPrefix("en"),
               let address = entry.ifa_addr,
               address.pointee.sa_family == UInt8(AF_LINK),
               (Int32(entry.ifa_flags) & IFF_UP) != 0,
               let data = entry.ifa_data {
                let counters = data.assumingMemoryBound(to: if_data.self).pointee
                result[name] = (counters.ifi_ibytes, counters.ifi_obytes)
            }
            cursor = entry.ifa_next
        }
        return result
    }

    // MARK: ping (TCP connect, no admin rights needed)

    private static func measurePing(if needed: Bool) async -> Double? {
        guard needed else { return nil }
        return await tcpConnectTime(host: "1.1.1.1", port: 443, timeout: 2.0)
    }

    private final class Once: @unchecked Sendable {
        private let lock = NSRecursiveLock()
        private var done = false
        func run(_ work: () -> Void) {
            lock.lock()
            defer { lock.unlock() }
            if done { return }
            done = true
            work()
        }
    }

    /// Milliseconds until a TCP connection to host:port is established, or nil on failure / timeout.
    private static func tcpConnectTime(host: String, port: UInt16, timeout: TimeInterval) async -> Double? {
        await withCheckedContinuation { (continuation: CheckedContinuation<Double?, Never>) in
            guard let nwPort = NWEndpoint.Port(rawValue: port) else {
                continuation.resume(returning: nil)
                return
            }
            let connection = NWConnection(host: NWEndpoint.Host(host), port: nwPort, using: .tcp)
            let once = Once()
            let queue = DispatchQueue(label: "de.iox.stats.ping")
            let start = DispatchTime.now()

            @Sendable func finish(_ value: Double?) {
                once.run {
                    connection.cancel()
                    continuation.resume(returning: value)
                }
            }

            connection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    let nanos = DispatchTime.now().uptimeNanoseconds - start.uptimeNanoseconds
                    finish(Double(nanos) / 1_000_000)
                case .failed:
                    finish(nil)
                default:
                    break
                }
            }
            queue.asyncAfter(deadline: .now() + timeout) { finish(nil) }
            connection.start(queue: queue)
        }
    }

    // MARK: uptime, battery

    private static func uptimeSeconds() -> TimeInterval? {
        var boot = timeval()
        var size = MemoryLayout<timeval>.size
        var mib: [Int32] = [CTL_KERN, KERN_BOOTTIME]
        guard sysctl(&mib, 2, &boot, &size, nil, 0) == 0 else { return nil }
        let bootDate = Double(boot.tv_sec) + Double(boot.tv_usec) / 1_000_000
        return max(0, Date().timeIntervalSince1970 - bootDate)
    }

    private static func batteryStatus() -> (percent: Double, charging: Bool)? {
        guard let info = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
              let list = IOPSCopyPowerSourcesList(info)?.takeRetainedValue() as? [CFTypeRef] else {
            return nil
        }
        for source in list {
            guard let description = IOPSGetPowerSourceDescription(info, source)?.takeUnretainedValue() as? [String: Any],
                  (description[kIOPSTypeKey] as? String) == kIOPSInternalBatteryType,
                  let current = description[kIOPSCurrentCapacityKey] as? Int,
                  let maximum = description[kIOPSMaxCapacityKey] as? Int,
                  maximum > 0 else { continue }
            let charging = (description[kIOPSIsChargingKey] as? Bool) ?? false
            return (Double(current) / Double(maximum) * 100, charging)
        }
        return nil
    }
}
