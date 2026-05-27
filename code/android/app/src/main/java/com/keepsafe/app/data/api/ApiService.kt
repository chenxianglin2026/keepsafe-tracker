package com.keepsafe.app.data.api

import com.keepsafe.app.data.model.Alert
import com.keepsafe.app.data.model.ApiResponse
import com.keepsafe.app.data.model.Device
import com.keepsafe.app.data.model.DeviceStatus
import com.keepsafe.app.data.model.LocationData
import com.keepsafe.app.data.model.PaginatedAlertResponse
import com.keepsafe.app.data.model.UserProfile
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit API interface for KeepSafe backend.
 * Base URL: http://10.0.2.2:8000/api/v1 (Android emulator -> host machine)
 * All paths are relative to this base URL.
 */
interface ApiService {

    // ─── Auth ──────────────────────────────────────────────────

    @POST("users/login")
    suspend fun login(@Body body: Map<String, String>): LoginResponse

    @POST("users/register")
    suspend fun register(@Body body: Map<String, String>): MessageResponse

    // ─── User Profile ─────────────────────────────────────────

    @GET("users/profile")
    suspend fun getProfile(): ApiResponse<UserProfile>

    @PUT("users/profile")
    suspend fun updateProfile(@Body profile: UserProfile): ApiResponse<UserProfile>

    @POST("users/me/push-token")
    suspend fun registerPushToken(@Body body: Map<String, String>): ApiResponse<Unit>

    // ─── User's Devices (bound devices list) ───────────────────

    @GET("users/me/devices")
    suspend fun getDevices(): ApiResponse<List<Device>>

    // ─── Device Status & Location ──────────────────────────────

    @GET("devices/{device_id}/location")
    suspend fun getDeviceLocation(@Path("device_id") deviceId: String): ApiResponse<LocationData>

    @GET("devices/{device_id}/status")
    suspend fun getDeviceStatus(@Path("device_id") deviceId: String): ApiResponse<DeviceStatus>

    @GET("devices/{device_id}/history")
    suspend fun getDeviceHistory(
        @Path("device_id") deviceId: String,
        @Query("from") from: String? = null,
        @Query("to") to: String? = null,
        @Query("limit") limit: Int = 100
    ): ApiResponse<List<LocationData>>

    @GET("devices/{device_id}/sos/events")
    suspend fun getSosEvents(@Path("device_id") deviceId: String): ApiResponse<List<*>>

    // ─── Device Binding ────────────────────────────────────────

    @POST("devices/bind")
    suspend fun bindDevice(@Body body: Map<String, String>): ApiResponse<Unit>

    @DELETE("devices/{device_id}/bind")
    suspend fun unbindDevice(
        @Path("device_id") deviceId: String,
        @Query("user_id") userId: String
    ): ApiResponse<Unit>

    // ─── Alerts ────────────────────────────────────────────────

    @GET("alerts/")
    suspend fun getAlerts(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
        @Query("alert_type") alertType: String? = null,
        @Query("is_read") isRead: Boolean? = null
    ): PaginatedAlertResponse

    @PUT("alerts/{alert_id}/read")
    suspend fun markAlertRead(@Path("alert_id") alertId: Long): ApiResponse<Alert>

    @PUT("alerts/read-all")
    suspend fun markAllAlertsRead(): ApiResponse<Unit>
}
