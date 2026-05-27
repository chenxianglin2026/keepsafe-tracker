import Foundation

/// REST API service for KeepSafe backend
actor APIService {
    static let shared = APIService()

    private let baseURL = "http://192.168.110.34:8000/api/v1"
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    // MARK: - Token Management

    private var authToken: String?

    func setAuthToken(_ token: String) {
        authToken = token
    }

    func clearAuthToken() {
        authToken = nil
    }

    // MARK: - Initialization

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        session = URLSession(configuration: config)

        decoder = JSONDecoder()
        encoder = JSONEncoder()
    }

    // MARK: - Auth Endpoints

    /// 用户登录（邮箱+密码）
    func login(email: String, password: String) async throws -> LoginResponse {
        let body: [String: String] = ["email": email, "password": password]
        let bodyData = try encoder.encode(body)
        let data = try await request(path: "/users/login", method: "POST", body: bodyData)
        let response = try decoder.decode(LoginResponse.self, from: data)
        return response
    }

    /// 用户注册
    func register(email: String, password: String, nickname: String? = nil) async throws -> MessageResponse {
        var body: [String: String] = ["email": email, "password": password]
        if let nickname = nickname { body["nickname"] = nickname }
        let bodyData = try encoder.encode(body)
        let data = try await request(path: "/users/register", method: "POST", body: bodyData)
        let response = try decoder.decode(MessageResponse.self, from: data)
        return response
    }

    // MARK: - Device Endpoints

    /// 获取当前用户绑定的设备列表
    func getDevices() async throws -> [Device] {
        let data = try await request(path: "/users/me/devices", method: "GET")
        let devices = try decoder.decode([Device].self, from: data)
        return devices
    }

    /// 获取单个设备详情
    func getDevice(id: String) async throws -> Device {
        let devices = try await getDevices()
        guard let device = devices.first(where: { $0.deviceId == id }) else {
            throw APIError.notFound
        }
        return device
    }

    /// 绑定设备
    func bindDevice(deviceId: String, token: String, userId: String, nickname: String? = nil) async throws -> BindResponse {
        var body: [String: String] = [
            "device_id": deviceId,
            "token": token,
            "user_id": userId
        ]
        if let nickname = nickname { body["nickname"] = nickname }
        let bodyData = try encoder.encode(body)
        let data = try await request(path: "/devices/bind", method: "POST", body: bodyData)
        let response = try decoder.decode(BindResponse.self, from: data)
        return response
    }

    /// 解绑设备
    func unbindDevice(id: String, userId: String) async throws {
        let data = try await request(path: "/devices/\(id)/bind?user_id=\(userId)", method: "DELETE")
        let response = try decoder.decode(BindResponse.self, from: data)
        guard response.success else {
            throw APIError.serverError(code: 400, message: response.message)
        }
    }

    /// 获取设备最新位置
    func getDeviceLocation(id: String) async throws -> DeviceLocation {
        let data = try await request(path: "/devices/\(id)/location", method: "GET")
        let location = try decoder.decode(DeviceLocation.self, from: data)
        return location
    }

    /// 获取设备状态
    func getDeviceStatus(id: String) async throws -> DeviceStatusResponse {
        let data = try await request(path: "/devices/\(id)/status", method: "GET")
        let status = try decoder.decode(DeviceStatusResponse.self, from: data)
        return status
    }

    /// 获取设备历史轨迹
    func getDeviceHistory(id: String, from: String? = nil, to: String? = nil, limit: Int = 100) async throws -> [DeviceLocation] {
        var path = "/devices/\(id)/history?limit=\(limit)"
        if let from = from { path += "&from=\(from)" }
        if let to = to { path += "&to=\(to)" }
        let data = try await request(path: path, method: "GET")
        let locations = try decoder.decode([DeviceLocation].self, from: data)
        return locations
    }

    /// 获取设备 SOS 事件
    func getSosEvents(deviceId: String) async throws -> [SosEvent] {
        let data = try await request(path: "/devices/\(deviceId)/sos/events", method: "GET")
        let events = try decoder.decode([SosEvent].self, from: data)
        return events
    }

    // MARK: - Alert Endpoints

    /// 获取告警列表
    func getAlerts(page: Int = 1, pageSize: Int = 20) async throws -> AlertListResponse {
        let data = try await request(path: "/alerts?page=\(page)&page_size=\(pageSize)", method: "GET")
        let response = try decoder.decode(AlertListResponse.self, from: data)
        return response
    }

    /// 标记告警已读
    func markAlertRead(id: Int) async throws {
        let data = try await request(path: "/alerts/\(id)/read", method: "PUT")
        _ = try decoder.decode(Alert.self, from: data)
    }

    /// 标记所有告警已读
    func markAllAlertsRead() async throws {
        let data = try await request(path: "/alerts/read-all", method: "PUT")
        _ = try decoder.decode(MessageResponse.self, from: data)
    }

    // MARK: - User Endpoints

    /// 获取用户信息
    func getUserProfile() async throws -> UserProfile {
        let data = try await request(path: "/users/profile", method: "GET")
        let profile = try decoder.decode(UserProfile.self, from: data)
        return profile
    }

    /// 更新用户信息
    func updateUserProfile(nickname: String? = nil, avatarUrl: String? = nil, phone: String? = nil) async throws -> UserProfile {
        var bodyDict: [String: String] = [:]
        if let nickname = nickname { bodyDict["nickname"] = nickname }
        if let avatarUrl = avatarUrl { bodyDict["avatar_url"] = avatarUrl }
        if let phone = phone { bodyDict["phone"] = phone }
        let bodyData = try encoder.encode(bodyDict)
        let data = try await request(path: "/users/profile", method: "PUT", body: bodyData)
        let profile = try decoder.decode(UserProfile.self, from: data)
        return profile
    }

    // MARK: - Push Notification

    /// 注册推送 Token (FCM / APNs)
    func registerPushToken(token: String, platform: String = "ios") async throws {
        let body: [String: String] = ["platform": platform, "token": token]
        let bodyData = try encoder.encode(body)
        let data = try await request(path: "/users/me/push-token", method: "POST", body: bodyData)
        _ = try decoder.decode(MessageResponse.self, from: data)
    }

    // MARK: - HTTP Request Core

    private func request(path: String, method: String, body: Data? = nil) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = method
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = authToken {
            urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            urlRequest.httpBody = body
        }

        let (data, response) = try await session.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return data
        case 401:
            throw APIError.unauthorized
        case 404:
            throw APIError.notFound
        case 409:
            throw APIError.conflict
        case 400...499:
            throw APIError.clientError(statusCode: httpResponse.statusCode)
        case 500...599:
            throw APIError.serverError(code: httpResponse.statusCode, message: "Server error")
        default:
            throw APIError.unknown
        }
    }
}

// MARK: - API Response Models

struct LoginResponse: Codable {
    let accessToken: String
    let tokenType: String
    let userId: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case userId = "user_id"
    }
}

struct MessageResponse: Codable {
    let message: String
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case notFound
    case conflict
    case clientError(statusCode: Int)
    case serverError(code: Int, message: String)
    case networkError(Error)
    case unknown

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "无效的 URL"
        case .invalidResponse:
            return "无效的服务器响应"
        case .unauthorized:
            return "未授权，请重新登录"
        case .notFound:
            return "请求的资源不存在"
        case .conflict:
            return "资源冲突"
        case .clientError(let statusCode):
            return "客户端错误 (\(statusCode))"
        case .serverError(_, let message):
            return "服务器错误: \(message)"
        case .networkError(let error):
            return "网络错误: \(error.localizedDescription)"
        case .unknown:
            return "未知错误"
        }
    }
}
