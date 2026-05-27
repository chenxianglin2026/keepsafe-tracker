import SwiftUI

/// 主框架 — 底部 TabView
struct ContentView: View {
    @State private var selectedTab: Tab = .map

    enum Tab: String, CaseIterable {
        case map = "地图"
        case alerts = "告警"
        case settings = "设置"

        var icon: String {
            switch self {
            case .map: return "map.fill"
            case .alerts: return "bell.fill"
            case .settings: return "gearshape.fill"
            }
        }

        var activeIcon: String {
            switch self {
            case .map: return "map.fill"
            case .alerts: return "bell.badge.fill"
            case .settings: return "gearshape.fill"
            }
        }
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Map
            MapView()
                .tabItem {
                    Label(Tab.map.rawValue, systemImage: selectedTab == .map ? Tab.map.activeIcon : Tab.map.icon)
                }
                .tag(Tab.map)

            // Tab 2: Alerts
            AlertListView()
                .tabItem {
                    Label(Tab.alerts.rawValue, systemImage: selectedTab == .alerts ? Tab.alerts.activeIcon : Tab.alerts.icon)
                }
                .tag(Tab.alerts)

            // Tab 3: Settings
            SettingsView()
                .tabItem {
                    Label(Tab.settings.rawValue, systemImage: selectedTab == .settings ? Tab.settings.activeIcon : Tab.settings.icon)
                }
                .tag(Tab.settings)
        }
        .tint(.blue)
    }
}

// MARK: - Preview

#Preview {
    ContentView()
}
