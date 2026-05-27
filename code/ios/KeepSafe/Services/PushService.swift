import Foundation
import UserNotifications
#if canImport(UIKit)
import UIKit
#endif

/// Push notification service (APNs)
actor PushService: NSObject {
    static let shared = PushService()

    // MARK: - Properties

    private var pushToken: String?
    private var notificationCenter: UNUserNotificationCenter {
        UNUserNotificationCenter.current()
    }

    // MARK: - Initialization

    private override init() {
        super.init()
        notificationCenter.delegate = self
    }

    // MARK: - Registration

    /// 请求推送通知权限
    func requestAuthorization() async throws -> Bool {
        let options: UNAuthorizationOptions = [.alert, .badge, .sound]
        return try await notificationCenter.requestAuthorization(options: options)
    }

    /// 获取当前通知权限状态
    func getAuthorizationStatus() async -> UNAuthorizationStatus {
        let settings = await notificationCenter.notificationSettings()
        return settings.authorizationStatus
    }

    /// 注册 APNs（iOS 应用启动时调用）
    #if canImport(UIKit)
    func registerForPushNotifications() {
        DispatchQueue.main.async {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }
    #endif

    /// 接收 APNs 注册返回的 Token（在 AppDelegate 中调用）
    func didRegisterForRemoteNotifications(deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        pushToken = token
        Task {
            try? await uploadPushToken(token)
        }
    }

    /// APNs 注册失败
    func didFailToRegisterForRemoteNotifications(error: Error) {
        print("Failed to register for remote notifications: \(error.localizedDescription)")
    }

    // MARK: - Token Upload

    private func uploadPushToken(_ token: String) async throws {
        try await APIService.shared.registerPushToken(token: token)
    }

    /// 获取当前推送 Token
    func getPushToken() -> String? {
        return pushToken
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension PushService: UNUserNotificationCenterDelegate {
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        // App 在前台时也显示通知
        return [.banner, .sound, .badge, .list]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        // 处理通知点击事件
        let userInfo = response.notification.request.content.userInfo
        print("Notification received: \(userInfo)")
    }
}
