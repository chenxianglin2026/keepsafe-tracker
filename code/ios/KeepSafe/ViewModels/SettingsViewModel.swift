import Foundation

/// 设置页面 ViewModel
@MainActor
class SettingsViewModel: ObservableObject {
    // MARK: - Published Properties

    @Published var user: UserProfile?
    @Published var devices: [Device] = []
    @Published var settings = AppSettings()
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showError = false
    @Published var showDeviceBindSheet = false
    @Published var pushNotificationEnabled = false

    // MARK: - Initialization

    init() {
        Task {
            pushNotificationEnabled = await (try? PushService.shared.getAuthorizationStatus() == .authorized) ?? false
        }
    }

    // MARK: - Data Loading

    /// 加载用户信息和设备列表
    func loadData() async {
        isLoading = true
        errorMessage = nil

        async let userTask = loadUserProfile()
        async let devicesTask = loadDevices()

        let (userResult, devicesResult) = await (userTask, devicesTask)

        if let error = userResult ?? devicesResult {
            errorMessage = error
            showError = true
        }

        isLoading = false
    }

    private func loadUserProfile() async -> String? {
        do {
            let profile = try await APIService.shared.getUserProfile()
            user = profile
            return nil
        } catch {
            return error.localizedDescription
        }
    }

    private func loadDevices() async -> String? {
        do {
            let fetchedDevices = try await APIService.shared.getDevices()
            devices = fetchedDevices
            return nil
        } catch {
            return error.localizedDescription
        }
    }

    // MARK: - Device Management

    /// 解绑设备
    func unbindDevice(_ device: Device) async -> Bool {
        do {
            try await APIService.shared.unbindDevice(id: device.id, userId: user?.userId ?? "")
            devices.removeAll { $0.id == device.id }
            return true
        } catch {
            errorMessage = error.localizedDescription
            showError = true
            return false
        }
    }

    /// 刷新设备列表
    func refreshDevices() async {
        _ = await loadDevices()
    }

    // MARK: - Push Notifications

    /// 请求推送通知权限
    func requestPushPermission() async {
        do {
            let granted = try await PushService.shared.requestAuthorization()
            pushNotificationEnabled = granted
            if granted {
                PushService.shared.registerForPushNotifications()
            }
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    // MARK: - Settings Persistence

    func saveSettings() {
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: "app_settings")
        }
    }

    func loadSettings() {
        if let data = UserDefaults.standard.data(forKey: "app_settings"),
           let decoded = try? JSONDecoder().decode(AppSettings.self, from: data) {
            settings = decoded
        }
    }
}
