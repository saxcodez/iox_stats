import SwiftUI
import WidgetKit

/// The widget's content. Native SwiftUI: system fonts, system colours, SF Symbols and the standard
/// widget background, so it looks exactly like Apple's own widgets next to it.
struct StatsWidgetView: View {
    let entry: StatsEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        let limit = WidgetLayout.capacity(family: family, style: entry.style)
        let readings = entry.kinds.prefix(limit).map { entry.snapshot.reading(for: $0) }

        Group {
            switch entry.style {
            case .rings:
                RingsLayout(readings: readings, palette: entry.palette)
            case .bars:
                BarsLayout(readings: readings, palette: entry.palette)
            case .numbers:
                NumbersLayout(readings: readings, wide: family != .systemSmall, palette: entry.palette)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .modifier(WidgetBackgroundModifier(background: entry.background))
    }
}

/// Glass = the translucent system fill Apple recommends for widgets (the desktop shows through, like the
/// Batteries widget). Solid = the opaque window background.
private struct WidgetBackgroundModifier: ViewModifier {
    let background: WidgetBackground

    @ViewBuilder
    func body(content: Content) -> some View {
        switch background {
        case .glass:
            content.containerBackground(.fill.tertiary, for: .widget)
        case .solid:
            content.containerBackground(.background, for: .widget)
        }
    }
}

// MARK: - Rings

private struct RingsLayout: View {
    let readings: [Reading]
    let palette: WidgetPalette

    var body: some View {
        HStack(spacing: readings.count > 2 ? 10 : 16) {
            ForEach(readings) { reading in
                RingView(reading: reading, palette: palette)
            }
        }
    }
}

private struct RingView: View {
    let reading: Reading
    let palette: WidgetPalette

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle()
                    .stroke(reading.track(in: palette), lineWidth: 9)
                Circle()
                    .trim(from: 0, to: reading.fraction ?? 0)
                    .stroke(reading.color(in: palette), style: StrokeStyle(lineWidth: 9, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .widgetAccentable()
                VStack(spacing: 0) {
                    Text(reading.value)
                        .font(.system(size: 18, weight: .semibold, design: .rounded))
                        .monospacedDigit()
                        .lineLimit(1)
                        .minimumScaleFactor(0.5)
                    if !reading.unit.isEmpty {
                        Text(reading.unit)
                            .font(.system(size: 9, weight: .medium))
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 10)
            }
            .aspectRatio(1, contentMode: .fit)

            Text(reading.kind.title)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }
}

// MARK: - Bars

private struct BarsLayout: View {
    let readings: [Reading]
    let palette: WidgetPalette

    var body: some View {
        VStack(spacing: 9) {
            ForEach(readings) { reading in
                BarRow(reading: reading, palette: palette)
            }
        }
    }
}

private struct BarRow: View {
    let reading: Reading
    let palette: WidgetPalette

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 5) {
                Image(systemName: reading.kind.symbol)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(reading.color(in: palette))
                Text(reading.kind.title)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.secondary)
                Spacer(minLength: 4)
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(reading.value)
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .monospacedDigit()
                    if !reading.unit.isEmpty {
                        Text(reading.unit)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(.secondary)
                    }
                }
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(reading.track(in: palette))
                    Capsule()
                        .fill(reading.color(in: palette))
                        .frame(width: max(6, geo.size.width * CGFloat(reading.fraction ?? 0)))
                        .widgetAccentable()
                }
            }
            .frame(height: 6)
        }
    }
}

// MARK: - Numbers only

private struct NumbersLayout: View {
    let readings: [Reading]
    let wide: Bool
    let palette: WidgetPalette

    var body: some View {
        let columns: [[Reading]] = (wide && readings.count > 3)
            ? [Array(readings.prefix(3)), Array(readings.dropFirst(3))]
            : [readings]

        HStack(alignment: .center, spacing: 20) {
            ForEach(Array(columns.enumerated()), id: \.offset) { _, column in
                VStack(spacing: 10) {
                    ForEach(column) { reading in
                        NumberRow(reading: reading, palette: palette)
                    }
                }
            }
        }
    }
}

private struct NumberRow: View {
    let reading: Reading
    let palette: WidgetPalette

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text(reading.kind.title)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer(minLength: 4)
            Text(reading.value)
                .font(.system(size: 21, weight: .semibold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(reading.color(in: palette))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            if !reading.unit.isEmpty {
                Text(reading.unit)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)
            }
        }
    }
}
