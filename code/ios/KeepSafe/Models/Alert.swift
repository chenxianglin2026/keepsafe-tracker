import Foundation

// MARK: - Alert Model

struct Alert: Codable, Identifiable {
    let id: Int
    let deviceId: String
    let timestamp: String
    let alertType: String
    let payload: AlertPayload?
    let isRead: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case deviceId = "device_id"
        case timestamp = "ts"
        case alertType = "alert_type"
        case payload
        case isRead = "is_read"
    }
}

struct AlertPayload: Codable {
    let deviceName: String?
    let message: String?
    let lat: Double?
    let lng: Double?
    let address: String?

    enum CodingKeys: String, CodingKey {
        case deviceName = "device_name"
        case message
        case lat
        case lng
        case address
    }
}

struct AlertListResponse: Codable {
    let items: [Alert]
    let total: Int
    let page: Int
    let pageSize: Int

    enum CodingKeys: String, CodingKey {
        case items, total, page
        case pageSize = "page_size"
    }
}

// MARK: - Alert Types (for display)

enum AlertType: String, Codable, CaseIterable, Identifiable {
    case geofenceExit = "geofence_exit"
    case geofenceEnter = "geofence_enter"
    case lowBattery = "low_battery"
    case deviceOffline = "device_offline"
    case deviceOnline = "device_online"
    case sos
    case fallDetection = "fall_detection"
    case movementAlert = "movement_alert"
    case deviceDisconnected = "device_disconnected"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .geofenceExit: return "离开安全区域"
        case .geofenceEnter: return "进入安全区域"
        case .lowBattery: return "电量低"
        case .deviceOffline: return "设备离线"
        case .deviceOnline: return "设备上线"
        case .sos: return "SOS 求救"
        case .fallDetection: return "跌倒检测"
        case .movementAlert: return "移动告警"
        case .deviceDisconnected: return "设备断开连接"
        }
    }

    var iconName: String {
        switch self {
        case .geofenceExit: return "figure.walk"
        case .geofenceEnter: return "house.fill"
        case .lowBattery: return "battery.25"
        case .deviceOffline: return "wifi.slash"
        case .deviceOnline: return "wifi"
        case .sos: return "exclamationmark.triangle.fill"
        case .fallDetection: return "figure.fall"
        case .movementAlert: return "bell.fill"
        case .deviceDisconnected: return "link.icloud"
        }
    }

    var color: String {
        switch self {
        case .sos, .fallDetection: return "red"
        case .geofenceExit, .movementAlert: return "orange"
        case .lowBattery: return "yellow"
        case .deviceOffline, .deviceDisconnected: return "gray"
        case .geofenceEnter, .deviceOnline: return "green"
        }
    }
}

struct AlertLocation: Codable {
    let latitude: Double
    let longitude: Double
    let address: String?
}
