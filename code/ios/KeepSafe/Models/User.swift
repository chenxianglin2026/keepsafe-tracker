import Foundation

// MARK: - User Profile Model

struct UserProfile: Codable {
    let userId: String
    let email: String
    let nickname: String?
    let avatarUrl: String?
    let phone: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case email
        case nickname
        case avatarUrl = "avatar_url"
        case phone
        case createdAt = "created_at"
    }
}

// MARK: - App Settings (local)

struct AppSettings: Codable {
    var notificationsEnabled: Bool = true
    var soundEnabled: Bool = true
    var vibrationEnabled: Bool = true
    var mapType: MapType = .standard
    var geofenceRadius: Double = 500 // meters

    enum MapType: String, Codable, CaseIterable, Identifiable {
        case standard
        case hybrid
        case satellite

        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .standard: return "标准"
            case .hybrid: return "混合"
            case .satellite: return "卫星"
            }
        }
    }
}
