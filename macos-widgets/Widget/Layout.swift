import AppIntents
import SwiftUI
import WidgetKit

// MARK: - What the user can choose in "Edit Widget"

/// How the values are drawn.
enum WidgetStyle: String, AppEnum {
    case rings, bars, numbers

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Display"
    static let caseDisplayRepresentations: [WidgetStyle: DisplayRepresentation] = [
        .rings: "Rings",
        .bars: "Bars",
        .numbers: "Numbers only",
    ]
}

/// Colours. `ios` = one green like Apple's Batteries widget, `colorful` = one colour per value.
/// Orange / red for warnings stay in every palette.
enum WidgetPalette: String, AppEnum {
    case ios, colorful, blue, teal, purple, pink, orange, graphite

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Colors"
    static let caseDisplayRepresentations: [WidgetPalette: DisplayRepresentation] = [
        .ios: "iOS Green",
        .colorful: "Colorful",
        .blue: "Blue",
        .teal: "Teal",
        .purple: "Purple",
        .pink: "Pink",
        .orange: "Orange",
        .graphite: "Graphite",
    ]

    /// The accent for a value whose own colour is `natural`.
    func accent(for natural: Color) -> Color {
        switch self {
        case .ios: return .green
        case .colorful: return natural
        case .blue: return .blue
        case .teal: return .teal
        case .purple: return .purple
        case .pink: return .pink
        case .orange: return .orange
        case .graphite: return .gray
        }
    }
}

/// Widget background. `glass` = the translucent system fill Apple's own widgets use, `solid` = opaque.
enum WidgetBackground: String, AppEnum {
    case glass, solid

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Background"
    static let caseDisplayRepresentations: [WidgetBackground: DisplayRepresentation] = [
        .glass: "Glass (like Apple's widgets)",
        .solid: "Solid",
    ]
}

/// A value a widget can show. `empty` means "leave this slot unused".
enum MetricKind: String, AppEnum, CaseIterable {
    case empty, cpu, temperature, memory, swap, disk, ping, download, upload, battery, uptime, thermal

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Value"
    static let caseDisplayRepresentations: [MetricKind: DisplayRepresentation] = [
        .empty: "None",
        .cpu: "CPU",
        .temperature: "CPU Temperature",
        .memory: "Memory",
        .swap: "Swap",
        .disk: "Disk",
        .ping: "Ping",
        .download: "Download",
        .upload: "Upload",
        .battery: "Battery",
        .uptime: "Uptime",
        .thermal: "Thermal State",
    ]

    /// Short label under rings / next to bars.
    var title: String {
        switch self {
        case .empty: return ""
        case .cpu: return "CPU"
        case .temperature: return "Temp"
        case .memory: return "Memory"
        case .swap: return "Swap"
        case .disk: return "Disk"
        case .ping: return "Ping"
        case .download: return "Down"
        case .upload: return "Up"
        case .battery: return "Battery"
        case .uptime: return "Uptime"
        case .thermal: return "Thermal"
        }
    }

    /// SF Symbol - the same icons Apple's own widgets use.
    var symbol: String {
        switch self {
        case .empty: return "circle.dashed"
        case .cpu: return "cpu"
        case .temperature: return "thermometer.medium"
        case .memory, .swap: return "memorychip"
        case .disk: return "internaldrive"
        case .ping: return "wifi"
        case .download: return "arrow.down.circle.fill"
        case .upload: return "arrow.up.circle.fill"
        case .battery: return "battery.75percent"
        case .uptime: return "clock"
        case .thermal: return "thermometer.medium"
        }
    }

    /// Apple system colours, same accents as the Python dashboard.
    var tint: Color {
        switch self {
        case .empty: return .gray
        case .cpu: return .blue
        case .temperature: return .orange
        case .memory: return .purple
        case .swap: return .pink
        case .disk: return .teal
        case .ping: return .green
        case .download: return .blue
        case .upload: return .green
        case .battery: return .green
        case .uptime: return .indigo
        case .thermal: return .orange
        }
    }
}

// MARK: - How many values fit

/// Same limits as the IOX Stats window (see iox_stats/layout.py, CAPACITY).
/// The layout test in tests/test_widgets_project.py keeps both tables in sync.
enum WidgetLayout {
    static func capacity(family: WidgetFamily, style: WidgetStyle) -> Int {
        switch (family, style) {
        case (.systemSmall, .rings): return 2
        case (.systemSmall, .bars): return 3
        case (.systemSmall, .numbers): return 3
        case (_, .rings): return 4
        case (_, .bars): return 4
        case (_, .numbers): return 6
        }
    }
}

// MARK: - The configuration shown in "Edit Widget"

struct SystemStatsIntent: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "System Status"
    static let description = IntentDescription(
        "Choose how the values are shown and which ones. Small widgets show up to 2 rings, 3 bars or 3 numbers; medium widgets up to 4 rings, 4 bars or 6 numbers. Extra values are ignored."
    )

    @Parameter(title: "Display", default: .rings)
    var style: WidgetStyle

    @Parameter(title: "Colors", default: .ios)
    var palette: WidgetPalette

    @Parameter(title: "Background", default: .glass)
    var background: WidgetBackground

    @Parameter(title: "Value 1", default: .cpu)
    var metric1: MetricKind

    @Parameter(title: "Value 2", default: .memory)
    var metric2: MetricKind

    @Parameter(title: "Value 3", default: .disk)
    var metric3: MetricKind

    @Parameter(title: "Value 4", default: .ping)
    var metric4: MetricKind

    @Parameter(title: "Value 5", default: .empty)
    var metric5: MetricKind

    @Parameter(title: "Value 6", default: .empty)
    var metric6: MetricKind

    /// The chosen values in order, without duplicates and without empty slots.
    var chosenKinds: [MetricKind] {
        var seen = Set<MetricKind>()
        var result: [MetricKind] = []
        for kind in [metric1, metric2, metric3, metric4, metric5, metric6] {
            if kind != .empty && !seen.contains(kind) {
                seen.insert(kind)
                result.append(kind)
            }
        }
        return result.isEmpty ? [.cpu, .memory] : result
    }
}
