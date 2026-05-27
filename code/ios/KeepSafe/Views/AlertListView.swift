import SwiftUI

/// 告警列表页面
struct AlertListView: View {
    @StateObject private var viewModel = AlertListViewModel()
    @State private var selectedAlert: Alert?

    var body: some View {
        NavigationStack {
            ZStack {
                if viewModel.isLoading && viewModel.alerts.isEmpty {
                    ProgressView("加载中...")
                } else if viewModel.alerts.isEmpty {
                    emptyStateView
                } else {
                    alertList
                }
            }
            .navigationTitle("告警")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.unreadCount > 0 {
                        Button("全部已读") {
                            Task { await viewModel.markAllAsRead() }
                        }
                        .font(.subheadline)
                    }
                }
            }
            .task {
                await viewModel.loadAlerts()
            }
            .refreshable {
                await viewModel.refresh()
            }
            .alert("错误", isPresented: $viewModel.showError) {
                Button("确定", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "未知错误")
            }
        }
    }

    // MARK: - Alert List

    private var alertList: some View {
        List {
            ForEach(viewModel.alerts) { alert in
                alertRow(alert)
                    .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
                    .listRowSeparator(.hidden)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        if !alert.isRead {
                            Button {
                                Task { await viewModel.markAsRead(alert) }
                            } label: {
                                Label("已读", systemImage: "checkmark")
                            }
                            .tint(.blue)
                        }
                    }
                    .onTapGesture {
                        selectedAlert = alert
                        if !alert.isRead {
                            Task { await viewModel.markAsRead(alert) }
                        }
                    }
            }

            if viewModel.hasMore {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .listRowSeparator(.hidden)
                    .task {
                        await viewModel.loadMore()
                    }
            }
        }
        .listStyle(.plain)
        .sheet(item: $selectedAlert) { alert in
            alertDetailSheet(alert)
        }
    }

    // MARK: - Alert Row

    private func alertRow(_ alert: Alert) -> some View {
        HStack(alignment: .top, spacing: 12) {
            // Icon
            ZStack {
                Circle()
                    .fill(alertTypeColor(alert.alertType).opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: alertTypeIcon(alert.alertType))
                    .font(.system(size: 16))
                    .foregroundColor(alertTypeColor(alert.alertType))
            }

            VStack(alignment: .leading, spacing: 4) {
                // Title row
                HStack {
                    Text(alertTypeDisplayName(alert.alertType))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Spacer()
                    if !alert.isRead {
                        Circle()
                            .fill(.blue)
                            .frame(width: 8, height: 8)
                    }
                }

                // Message
                Text(alert.payload?.message ?? alert.alertType)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)

                // Time
                Text(formatTime(alert.timestamp))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }

    // MARK: - Alert Detail Sheet

    private func alertDetailSheet(_ alert: Alert) -> some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Icon
                ZStack {
                    Circle()
                        .fill(alertTypeColor(alert.alertType).opacity(0.2))
                        .frame(width: 80, height: 80)
                    Image(systemName: alertTypeIcon(alert.alertType))
                        .font(.system(size: 32))
                        .foregroundColor(alertTypeColor(alert.alertType))
                }
                .padding(.top, 40)

                // Type
                Text(alertTypeDisplayName(alert.alertType))
                    .font(.title2)
                    .fontWeight(.bold)

                // Device name
                if let deviceName = alert.payload?.deviceName {
                    Label(deviceName, systemImage: "device.tag")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                // Message
                Text(alert.payload?.message ?? alert.alertType)
                    .font(.body)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)

                // Time
                HStack {
                    Image(systemName: "clock")
                    Text(formatTime(alert.timestamp))
                }
                .font(.caption)
                .foregroundColor(.secondary)

                Spacer()
            }
            .padding()
            .navigationTitle("告警详情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("关闭") {
                        selectedAlert = nil
                    }
                }
            }
        }
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: 12) {
            Image(systemName: "bell.badge.slash")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            Text("暂无告警")
                .font(.headline)
                .foregroundColor(.secondary)
            Text("所有告警将显示在这里")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Helpers

    private func alertTypeColor(_ type: String) -> Color {
        guard let alertType = AlertType(rawValue: type) else {
            return .gray
        }
        switch alertType {
        case .sos, .fallDetection: return .red
        case .geofenceExit, .movementAlert: return .orange
        case .lowBattery: return .yellow
        case .deviceOffline, .deviceDisconnected: return .gray
        case .geofenceEnter, .deviceOnline: return .green
        }
    }

    private func alertTypeIcon(_ type: String) -> String {
        guard let alertType = AlertType(rawValue: type) else {
            return "bell.fill"
        }
        return alertType.iconName
    }

    private func alertTypeDisplayName(_ type: String) -> String {
        guard let alertType = AlertType(rawValue: type) else {
            return type
        }
        return alertType.displayName
    }

    private func formatTime(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        if let date = formatter.date(from: isoString) {
            let relative = RelativeDateTimeFormatter()
            relative.unitsStyle = .abbreviated
            relative.locale = Locale(identifier: "zh-Hans")
            return relative.localizedString(for: date, relativeTo: Date())
        }

        return isoString
    }
}

// MARK: - Alert Identifiable for Sheet

extension Alert: @retroactive Identifiable {}

// MARK: - Preview

#Preview {
    AlertListView()
}
