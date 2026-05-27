import Foundation

/// 告警列表 ViewModel
@MainActor
class AlertListViewModel: ObservableObject {
    // MARK: - Published Properties

    @Published var alerts: [Alert] = []
    @Published var unreadCount = 0
    @Published var isLoading = false
    @Published var isRefreshing = false
    @Published var errorMessage: String?
    @Published var showError = false

    private var currentPage = 1
    private var hasMore = true

    // MARK: - Data Loading

    /// 加载告警列表
    func loadAlerts() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIService.shared.getAlerts(page: 1)
            alerts = response.items
            unreadCount = 0
            currentPage = 1
            hasMore = response.total > alerts.count
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }

        isLoading = false
    }

    /// 下拉刷新
    func refresh() async {
        isRefreshing = true
        await loadAlerts()
        isRefreshing = false
    }

    /// 加载更多
    func loadMore() async {
        guard hasMore, !isLoading else { return }

        isLoading = true
        currentPage += 1

        do {
            let response = try await APIService.shared.getAlerts(page: currentPage)
            alerts.append(contentsOf: response.items)
            hasMore = response.total > alerts.count
        } catch {
            currentPage -= 1
            errorMessage = error.localizedDescription
            showError = true
        }

        isLoading = false
    }

    /// 标记告警已读
    func markAsRead(_ alert: Alert) async {
        guard !alert.isRead else { return }

        do {
            try await APIService.shared.markAlertRead(id: alert.id)
            if let index = alerts.firstIndex(where: { $0.id == alert.id }) {
                var updated = alerts[index]
                // Marking is done server-side; refresh will pick it up
                // Update the local isRead to reflect immediately
                let alertType = updated.alertType
                let payload = updated.payload
                updated = Alert(
                    id: updated.id,
                    deviceId: updated.deviceId,
                    timestamp: updated.timestamp,
                    alertType: alertType,
                    payload: payload,
                    isRead: true
                )
                alerts[index] = updated
            }
            unreadCount = max(0, unreadCount - 1)
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    /// 标记全部已读
    func markAllAsRead() async {
        do {
            try await APIService.shared.markAllAlertsRead()
            // Update all locally
            for i in alerts.indices {
                let alertType = alerts[i].alertType
                let payload = alerts[i].payload
                alerts[i] = Alert(
                    id: alerts[i].id,
                    deviceId: alerts[i].deviceId,
                    timestamp: alerts[i].timestamp,
                    alertType: alertType,
                    payload: payload,
                    isRead: true
                )
            }
            unreadCount = 0
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    /// 获取告警类型对应的颜色
    func colorForAlertType(_ type: String) -> String {
        guard let alertType = AlertType(rawValue: type) else {
            return "gray"
        }
        return alertType.color
    }
}
