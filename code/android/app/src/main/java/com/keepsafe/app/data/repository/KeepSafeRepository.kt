package com.keepsafe.app.data.repository

import com.keepsafe.app.data.api.RetrofitClient
import com.keepsafe.app.data.model.Alert
import com.keepsafe.app.data.model.ApiResponse
import com.keepsafe.app.data.model.Device
import com.keepsafe.app.data.model.DeviceStatus
import com.keepsafe.app.data.model.LocationData
import com.keepsafe.app.data.model.PaginatedAlertResponse
import com.keepsafe.app.data.model.UserProfile

/**
 * Repository layer abstracting API calls for KeepSafe.
 * Provides clean interface for ViewModels.
 */
class KeepSafeRepository {

    private val api = RetrofitClient.apiService

    // ─── Auth ──────────────────────────────────────────────────

    suspend fun login(email: String, password: String): LoginResponse {
        return api.login(mapOf("email" to email, "password" to password))
    }

    suspend fun register(email: String, password: String, nickname: String? = null): MessageResponse {
        val body = mapOf("email" to email, "password" to password) +
            if (nickname != null) mapOf("nickname" to nickname) else emptyMap()
        return api.register(body)
    }

    // ─── User Profile ─────────────────────────────────────────

    suspend fun getProfile(): ApiResponse<UserProfile> {
        return api.getProfile()
    }

    suspend fun updateProfile(profile: UserProfile): ApiResponse<UserProfile> {
        return api.updateProfile(profile)
    }

    suspend fun registerPushToken(platform: String, token: String): ApiResponse<Unit> {
        return api.registerPushToken(mapOf("platform" to platform, "token" to token))
    }

    // ─── Devices ────────────────────────────────────────────────

    suspend fun getDevices(): ApiResponse<List<Device>> {
        return api.getDevices()
    }

    suspend fun getDeviceStatus(deviceId: String): ApiResponse<DeviceStatus> {
        return api.getDeviceStatus(deviceId)
    }

    suspend fun getDeviceLocation(deviceId: String): ApiResponse<LocationData> {
        return api.getDeviceLocation(deviceId)
    }

    suspend fun getDeviceHistory(
        deviceId: String,
        from: String? = null,
        to: String? = null,
        limit: Int = 100
    ): ApiResponse<List<LocationData>> {
        return api.getDeviceHistory(deviceId, from, to, limit)
    }

    suspend fun bindDevice(userId: String, deviceId: String, token: String, nickname: String? = null): ApiResponse<Unit> {
        val body = mapOf(
            "user_id" to userId,
            "device_id" to deviceId,
            "token" to token
        ) + if (nickname != null) mapOf("nickname" to nickname) else emptyMap()
        return api.bindDevice(body)
    }

    suspend fun unbindDevice(deviceId: String, userId: String): ApiResponse<Unit> {
        return api.unbindDevice(deviceId, userId)
    }

    // ─── Alerts ─────────────────────────────────────────────────

    suspend fun getAlerts(
        page: Int = 1,
        pageSize: Int = 20,
        alertType: String? = null,
        isRead: Boolean? = null
    ): PaginatedAlertResponse {
        return api.getAlerts(page, pageSize, alertType, isRead)
    }

    suspend fun markAlertRead(alertId: Long): ApiResponse<Alert> {
        return api.markAlertRead(alertId)
    }

    suspend fun markAllAlertsRead(): ApiResponse<Unit> {
        return api.markAllAlertsRead()
    }
}
