package com.keepsafe.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberCameraPositionState
import com.keepsafe.app.data.model.Device
import com.keepsafe.app.data.model.LocationData
import com.keepsafe.app.ui.theme.StatusDanger
import com.keepsafe.app.ui.theme.StatusSafe
import com.keepsafe.app.ui.theme.StatusWarning

/**
 * MapScreen — Home tab showing device location on Google Maps
 * with a bottom status card for the selected device.
 */
@Composable
fun MapScreen(
    devices: List<Device> = emptyList(),
    isLoading: Boolean = false,
    onDeviceClick: (Device) -> Unit = {},
    // Optional additional data loaded from API
    deviceLocations: Map<String, LocationData> = emptyMap(),
    deviceBattery: Map<String, Int> = emptyMap()
) {
    // Default to Shanghai if no device location
    val defaultLatLng = LatLng(31.2304, 121.4737)

    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(defaultLatLng, 12f)
    }

    val selectedDevice = devices.firstOrNull()

    Box(modifier = Modifier.fillMaxSize()) {
        if (isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center)
            )
        } else {
            // Google Maps
            GoogleMap(
                modifier = Modifier.fillMaxSize(),
                cameraPositionState = cameraPositionState,
                onMapClick = {
                    // Could handle map click to add markers etc.
                }
            ) {
                // Markers for each device — use location from API or fallback to Shanghai
                devices.forEach { device ->
                    val loc = deviceLocations[device.id]
                    val position = if (loc != null) {
                        LatLng(loc.latitude, loc.longitude)
                    } else {
                        defaultLatLng
                    }
                    val batteryInfo = deviceBattery[device.id]?.let { "电池: $it%" } ?: ""
                    Marker(
                        state = MarkerState(position = position),
                        title = device.name,
                        snippet = batteryInfo
                    )
                }
            }

            // Bottom device status card
            if (selectedDevice != null) {
                DeviceStatusCard(
                    device = selectedDevice,
                    location = deviceLocations[selectedDevice.id],
                    battery = deviceBattery[selectedDevice.id],
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(16.dp)
                )
            } else {
                // Empty state card
                Card(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(16.dp)
                        .fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surface
                    )
                ) {
                    Text(
                        text = "暂无设备，请前往设置页面添加",
                        modifier = Modifier.padding(24.dp),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

/**
 * Bottom card showing the currently selected device's status.
 */
@Composable
private fun DeviceStatusCard(
    device: Device,
    location: LocationData?,
    battery: Int?,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Device name row
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                // Status dot
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(
                            if (device.isActive) StatusSafe else StatusDanger
                        )
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = device.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Location & battery info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                location?.let { loc ->
                    Column {
                        Text(
                            text = "位置",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = String.format("%.4f, %.4f", loc.latitude, loc.longitude),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                } ?: run {
                    Column {
                        Text(
                            text = "设备ID",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = device.id,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }

                battery?.let { bat ->
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "电量",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "$bat%",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                            color = when {
                                bat < 20 -> StatusDanger
                                bat < 50 -> StatusWarning
                                else -> StatusSafe
                            }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(4.dp))

            // Last updated
            device.lastSeen?.let { updated ->
                Text(
                    text = "更新于: $updated",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
