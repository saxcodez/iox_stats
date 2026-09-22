import Foundation
import SwiftUI

// MARK: - Raw values

/// Everything the collector can measure. Missing values are nil.
struct SystemSnapshot {
    var cpu: Double?            // percent
    var memory: Double?         // percent
    var swap: Double?           // percent
    var disk: Double?           // percent used
    var pingMs: Double?
    var pingMeasured = false    // true when a ping was attempted (nil pingMs then means "offline")
    var downBytesPerSecond: Double?
    var upBytesPerSecond: Double?
    var battery: Double?        // percent
    var charging = false
    var uptime: TimeInterval?
    var thermal: ProcessInfo.ThermalState = .nominal
    var temperature: Double?    // CPU temperature in Celsius - only available through the IOX Stats app

    /// Plausible values for the gallery preview and placeholders.
    static let sample = SystemSnapshot(
        cpu: 34, memory: 61, swap: 12, disk: 64, pingMs: 18, pingMeasured: true,
        downBytesPerSecond: 2_400_000, upBytesPerSecond: 320_000,
        battery: 81, charging: false, uptime: 3 * 86_400 + 5 * 3_600, thermal: .nominal, temperature: 54
    )
}

// MARK: - Display values

/// One value ready to draw.
struct Reading: Identifiable {
    enum Level { case ok, warn, crit, unavailable }

    let kind: MetricKind
    let fraction: Double?       // 0...1 for rings and bars
    let value: String           // "34"
    let unit: String            // "%"
    let level: Level

    var id: String { kind.rawValue }

    /// The colour: the metric's system colour, orange / red when it needs attention.
    var color: Color {
        switch level {
        case .ok: return kind.tint
        case .warn: return .orange
        case .crit: return .red
        case .unavailable: return .gray
        }
    }
}

extension SystemSnapshot {
    func reading(for kind: MetricKind) -> Reading {
        switch kind {
        case .empty:
            return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
        case .cpu:
            return percent(kind, cpu, warn: 70, crit: 90)
        case .temperature:
            guard let t = temperature else {
                return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
            }
            let level: Reading.Level = t >= 90 ? .crit : (t >= 75 ? .warn : .ok)
            return Reading(kind: kind, fraction: max(0, min(1, t / 100)), value: String(format: "%.0f", t), unit: "°", level: level)
        case .memory:
            return percent(kind, memory, warn: 75, crit: 90)
        case .swap:
            return percent(kind, swap, warn: 50, crit: 80)
        case .disk:
            return percent(kind, disk, warn: 80, crit: 95)
        case .battery:
            guard let b = battery else {
                return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
            }
            let level: Reading.Level = b <= 10 ? .crit : (b <= 20 ? .warn : .ok)
            return Reading(kind: kind, fraction: b / 100, value: String(format: "%.0f", b), unit: "%", level: charging ? .ok : level)
        case .ping:
            if let ms = pingMs {
                let level: Reading.Level = ms >= 300 ? .crit : (ms >= 100 ? .warn : .ok)
                return Reading(kind: kind, fraction: min(1, ms / 300), value: String(format: "%.0f", ms), unit: "ms", level: level)
            }
            let offline = pingMeasured
            return Reading(kind: kind, fraction: nil, value: offline ? "Off" : "--", unit: "", level: offline ? .crit : .unavailable)
        case .download:
            return rate(kind, downBytesPerSecond)
        case .upload:
            return rate(kind, upBytesPerSecond)
        case .uptime:
            guard let up = uptime else {
                return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
            }
            return Reading(kind: kind, fraction: nil, value: Self.formatUptime(up), unit: "", level: .ok)
        case .thermal:
            switch thermal {
            case .nominal: return Reading(kind: kind, fraction: 0.15, value: "OK", unit: "", level: .ok)
            case .fair: return Reading(kind: kind, fraction: 0.4, value: "Warm", unit: "", level: .warn)
            case .serious: return Reading(kind: kind, fraction: 0.75, value: "Hot", unit: "", level: .crit)
            case .critical: return Reading(kind: kind, fraction: 1, value: "Hot", unit: "", level: .crit)
            @unknown default: return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
            }
        }
    }

    private func percent(_ kind: MetricKind, _ value: Double?, warn: Double, crit: Double) -> Reading {
        guard let v = value else {
            return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
        }
        let level: Reading.Level = v >= crit ? .crit : (v >= warn ? .warn : .ok)
        return Reading(kind: kind, fraction: max(0, min(1, v / 100)), value: String(format: "%.0f", v), unit: "%", level: level)
    }

    /// Network rates have no natural maximum: use a logarithmic scale from 0 to 100 MB/s.
    private func rate(_ kind: MetricKind, _ bytesPerSecond: Double?) -> Reading {
        guard let bps = bytesPerSecond else {
            return Reading(kind: kind, fraction: nil, value: "--", unit: "", level: .unavailable)
        }
        let (value, unit) = Self.formatRate(bps)
        let fraction = min(1, log10(1 + bps / 1024) / log10(1 + 100 * 1024))
        return Reading(kind: kind, fraction: fraction, value: value, unit: unit, level: .ok)
    }

    // MARK: formatting

    static func formatRate(_ bytesPerSecond: Double) -> (String, String) {
        let units = ["B/s", "KB/s", "MB/s", "GB/s"]
        var v = max(0, bytesPerSecond)
        var i = 0
        while v >= 1000 && i < units.count - 1 {
            v /= 1000
            i += 1
        }
        let text = (v >= 100 || i == 0) ? String(format: "%.0f", v) : String(format: "%.1f", v)
        return (text, units[i])
    }

    static func formatUptime(_ seconds: TimeInterval) -> String {
        let total = Int(seconds)
        let days = total / 86_400
        let hours = (total % 86_400) / 3_600
        let minutes = (total % 3_600) / 60
        if days > 0 { return "\(days)d \(hours)h" }
        if hours > 0 { return "\(hours)h \(minutes)m" }
        return "\(minutes)m"
    }
}
