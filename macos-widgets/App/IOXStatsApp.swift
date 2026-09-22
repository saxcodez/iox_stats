import SwiftUI

/// Small host app. macOS only lists widgets of apps that are installed, so this app carries the widget
/// extension. Open it once; after that the widgets are in the widget gallery.
@main
struct IOXStatsApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowResizability(.contentSize)
    }
}
