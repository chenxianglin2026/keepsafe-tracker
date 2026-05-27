package com.keepsafe.app.data.model

import com.google.gson.annotations.SerializedName

/**
 * A device bound to the current user (returned by GET /users/me/devices).
 */
data class Device(
    @SerializedName("device_id")
    val id: String = "",
    @SerializedName("nickname")
    val name: String = "",
    @SerializedName("bound_at")
    val boundAt: String = "",
    @SerializedName("is_active")
    val isActive: Boolean = true,
    @SerializedName("last_seen")
    val lastSeen: String? = null
)

/**
 * Summarized device status (returned by GET /devices/{id}/status).
 */
data class DeviceStatus(
    @SerializedName("device_id")
    val deviceId: String = "",
    @SerializedName("online")
    val online: Boolean = false,
    @SerializedName("battery")
    val battery: Int? = null,
    @SerializedName("charging")
    val charging: Boolean? = null,
    @SerializedName("rssi")
    val rssi: Int? = null,
    @SerializedName("last_seen")
    val lastSeen: String? = null,
    @SerializedName("lat")
    val lat: Double? = null,
    @SerializedName("lng")
    val lng: Double? = null
)

/**
 * Location data point from a device (returned by GET /devices/{id}/location).
 */
data class LocationData(
    @SerializedName("lat")
    val latitude: Double = 0.0,
    @SerializedName("lng")
    val longitude: Double = 0.0,
    @SerializedName("accuracy")
    val accuracy: Float? = null,
    @SerializedName("ts")
    val timestamp: String? = null,
    @SerializedName("alt")
    val altitude: Double? = null,
    @SerializedName("speed")
    val speed: Double? = null,
    @SerializedName("heading")
    val heading: Double? = null,
    @SerializedName("satellites")
    val satellites: Int? = null,
    @SerializedName("fix_type")
    val fixType: Int? = null,
    @SerializedName("battery")
    val battery: Int? = null,
    @SerializedName("charging")
    val charging: Boolean? = null,
    @SerializedName("rssi")
    val rssi: Int? = null
)

/**
 * Alert from a device (returned by alerts API).
 * The payload field contains nested data: message, severity, device_name, location, etc.
 */
data class Alert(
    @SerializedName("id")
    val id: Long = 0,
    @SerializedName("device_id")
    val deviceId: String = "",
    @SerializedName("alert_type")
    val type: String = "",
    @SerializedName("payload")
    val payload: Map<String, Any>? = null,
    @SerializedName("is_read")
    val isRead: Boolean = false,
    @SerializedName("ts")
    val createdAt: String = ""
) {
    /** Convenience accessors for common payload fields */
    val deviceName: String get() = payload?.get("device_name") as? String ?: deviceId
    val message: String get() = payload?.get("message") as? String ?: ""
    val severity: String get() = payload?.get("severity") as? String ?: "info"
    val location: LocationData? get() {
        val lat = payload?.get("lat") as? Double ?: return null
        val lng = payload?.get("lng") as? Double ?: return null
        return LocationData(latitude = lat, longitude = lng)
    }
}

/**
 * User profile (returned by users/profile).
 */
data class UserProfile(
    @SerializedName("user_id")
    val id: String = "",
    @SerializedName("email")
    val email: String = "",
    @SerializedName("nickname")
    val username: String = "",
    @SerializedName("phone")
    val phone: String? = null,
    @SerializedName("avatar_url")
    val avatarUrl: String? = null,
    @SerializedName("created_at")
    val createdAt: String? = null
)

/**
 * Generic API response wrapper.
 */
data class ApiResponse<T>(
    @SerializedName("success")
    val success: Boolean = false,
    @SerializedName("data")
    val data: T? = null,
    @SerializedName("message")
    val message: String? = null
)

/**
 * Login response from POST /users/login.
 */
data class LoginResponse(
    @SerializedName("access_token")
    val accessToken: String = "",
    @SerializedName("token_type")
    val tokenType: String = "bearer",
    @SerializedName("user_id")
    val userId: String = ""
)

/**
 * Generic message response (e.g., register, mark-all-read).
 */
data class MessageResponse(
    @SerializedName("message")
    val message: String = ""
)

/**
 * Paginated alert response from backend — uses items/total/page/page_size.
 */
data class PaginatedAlertResponse(
    @SerializedName("items")
    val items: List<Alert> = emptyList(),
    @SerializedName("total")
    val total: Int = 0,
    @SerializedName("page")
    val page: Int = 1,
    @SerializedName("page_size")
    val pageSize: Int = 20
)
