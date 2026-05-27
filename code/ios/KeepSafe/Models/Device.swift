import Foundation

// MARK: - Device Models

struct Device: Codable, Identifiable {
    let id: String
    let nickname: String?
    let boundAt: String?
    let isActive: Bool
    let lastSeen: String?

    var deviceId: String { id }

    enum CodingKeys: String, CodingKey {
        case id = "device_id"
        case nickname
        case boundAt = "bound_at"
        case isActive = "is_active"
        case lastSeen = "last_seen"
    }
}

// MARK: - Location Model

struct DeviceLocation: Codable {
    let deviceId: String?
    let latitude: Double?
    let longitude: Double?
    let accuracy: Double?
    let altitude: Double?
    let speed: Double?
    let heading: Double?
    let satellites: Int?
    let fixType: Int?
    let cellId: String?
    let battery: Int?
    let charging: Bool?
    let rssi: Int?
    let fwVersion: String?
    let timestamp: String?

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case latitude = "lat"
        case longitude = "lng"
        case accuracy
        case altitude = "alt"
        case speed
        case heading
        case satellites
        case fixType = "fix_type"
        case cellId = "cell_id"
        case battery
        case charging
        case rssi
        case fwVersion = "fw_version"
        case timestamp = "ts"
    }
}

// MARK: - Device Status Model

struct DeviceStatusResponse: Codable {
    let deviceId: String
    let online: Bool
    let battery: Int?
    let charging: Bool?
    let rssi: Int?
    let lastSeen: String?
    let lat: Double?
    let lng: Double?

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case online
        case battery
        case charging
        case rssi
        case lastSeen = "last_seen"
        case lat
        case lng
    }
}

// MARK: - SOS Event Model

struct SosEvent: Codable, Identifiable {
    let id: Int
    let deviceId: String
    let timestamp: String
    let lat: Double?
    let lng: Double?
    let accuracy: Double?
    let battery: Int?
    let triggerDurationMs: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case deviceId = "device_id"
        case timestamp = "ts"
        case lat
        case lng
        case accuracy
        case battery
        case triggerDurationMs = "trigger_duration_ms"
    }
}

// MARK: - Device Bind Request

struct DeviceBindRequest: Codable {
    let deviceId: String
    let token: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case token
    }
}

// MARK: - API Response Wrapper

struct APIResponse<T: Codable>: Codable {
    let code: Int
    let message: String
    let data: T?
}

struct EmptyResponse: Codable {}

struct BindResponse: Codable {
    let success: Bool
    let message: String
}
