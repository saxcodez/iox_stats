import AppIntents
import SwiftUI
import WidgetKit

// MARK: - Timeline entry

struct StatsEntry: TimelineEntry {
    let date: Date
    let style: WidgetStyle
    let kinds: [MetricKind]
    let snapshot: SystemSnapshot
    var palette: WidgetPalette = .ios
    var background: WidgetBackground = .glass

    static func sample(style: WidgetStyle, kinds: [MetricKind], palette: WidgetPalette = .ios,
                       background: WidgetBackground = .glass) -> StatsEntry {
        StatsEntry(date: Date(), style: style, kinds: kinds, snapshot: .sample, palette: palette, background: background)
    }
}

// MARK: - Provider

/// macOS decides how often a widget may refresh, so the values are the latest snapshot, not a per-second readout.
/// The data comes from the IOX Stats app (live, incl. CPU temperature) when it is running, otherwise the widget
/// measures itself. The per-second readouts are the app's menu bar item and its desktop widgets.
struct Provider: AppIntentTimelineProvider {
    typealias Entry = StatsEntry
    typealias Intent = SystemStatsIntent

    func placeholder(in context: Context) -> StatsEntry {
        .sample(style: .rings, kinds: [.cpu, .memory, .disk, .ping])
    }

    func snapshot(for configuration: SystemStatsIntent, in context: Context) async -> StatsEntry {
        if context.isPreview {
            return .sample(style: configuration.style, kinds: configuration.chosenKinds,
                           palette: configuration.palette, background: configuration.background)
        }
        return await makeEntry(for: configuration)
    }

    func timeline(for configuration: SystemStatsIntent, in context: Context) async -> Timeline<StatsEntry> {
        let entry = await makeEntry(for: configuration)
        // Ask for a refresh soon (the IOX Stats host app also requests reloads while it runs);
        // macOS throttles this, so the real interval can be longer.
        return Timeline(entries: [entry], policy: .after(entry.date.addingTimeInterval(60)))
    }

    private func makeEntry(for configuration: SystemStatsIntent) async -> StatsEntry {
        let kinds = configuration.chosenKinds
        let snapshot: SystemSnapshot
        if let shared = SharedSnapshotStore.loadFresh() {
            snapshot = shared.systemSnapshot
        } else {
            snapshot = await SystemCollector.collect(needing: Set(kinds))
        }
        return StatsEntry(date: Date(), style: configuration.style, kinds: kinds, snapshot: snapshot,
                          palette: configuration.palette, background: configuration.background)
    }
}

// MARK: - Widget

struct IOXStatsWidget: Widget {
    let kind = "IOXStatsWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: SystemStatsIntent.self, provider: Provider()) { entry in
            StatsWidgetView(entry: entry)
        }
        .configurationDisplayName("System Status")
        .description("CPU, memory, disk, network and more as rings, bars or numbers. Choose the values in Edit Widget.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct IOXStatsWidgetBundle: WidgetBundle {
    var body: some Widget {
        IOXStatsWidget()
    }
}
