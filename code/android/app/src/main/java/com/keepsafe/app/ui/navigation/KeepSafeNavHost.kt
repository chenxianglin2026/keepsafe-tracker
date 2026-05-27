package com.keepsafe.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.keepsafe.app.data.model.Alert
import com.keepsafe.app.data.model.Device
import com.keepsafe.app.data.model.UserProfile
import com.keepsafe.app.ui.screens.AlertScreen
import com.keepsafe.app.ui.screens.MapScreen
import com.keepsafe.app.ui.screens.SettingsScreen

/**
 * Main navigation host with BottomNavigation bar and 3 tabs:
 * 1. Map (地图) — device location
 * 2. Alerts (告警) — alert list
 * 3. Settings (设置) — device management + profile
 */
@Composable
fun KeepSafeNavHost() {
    val navController = rememberNavController()

    // Placeholder data for MVP — will be replaced by ViewModel + API calls
    val sampleDevices = listOf(
        Device(
            id = "KS-001",
            name = "儿童手表",
            isActive = true,
            lastSeen = "2026-05-11 10:30:00"
        ),
        Device(
            id = "KS-002",
            name = "老人定位器",
            isActive = true,
            lastSeen = "2026-05-11 10:28:00"
        )
    )

    val sampleAlerts = listOf(
        Alert(
            id = 1,
            deviceId = "KS-001",
            type = "geo_fence_breach",
            payload = mapOf(
                "device_name" to "儿童手表",
                "message" to "儿童手表离开了安全区域 (学校)",
                "severity" to "warning"
            ),
            isRead = false,
            createdAt = "2026-05-11 10:15:00"
        ),
        Alert(
            id = 2,
            deviceId = "KS-002",
            type = "low_battery",
            payload = mapOf(
                "device_name" to "老人定位器",
                "message" to "老人定位器电量低于 20%，请及时充电",
                "severity" to "danger"
            ),
            isRead = false,
            createdAt = "2026-05-11 09:45:00"
        ),
        Alert(
            id = 3,
            deviceId = "KS-001",
            type = "sos",
            payload = mapOf(
                "device_name" to "儿童手表",
                "message" to "儿童手表发送了 SOS 求救信号！",
                "severity" to "danger",
                "lat" to 31.2304,
                "lng" to 121.4737
            ),
            isRead = true,
            createdAt = "2026-05-10 18:30:00"
        )
    )

    val sampleProfile = UserProfile(
        id = "u-1",
        username = "测试用户",
        email = "user@example.com",
        phone = "13800138000"
    )

    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 3.dp
            ) {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination

                Screen.bottomNavItems.forEach { screen ->
                    val selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true

                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = screen.icon,
                                contentDescription = screen.title
                            )
                        },
                        label = { Text(screen.title) },
                        selected = selected,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Map.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            // Tab 1: Map
            composable(Screen.Map.route) {
                MapScreen(
                    devices = sampleDevices,
                    isLoading = false,
                    onDeviceClick = { /* TODO: navigate to device detail */ }
                )
            }

            // Tab 2: Alerts
            composable(Screen.Alerts.route) {
                AlertScreen(
                    alerts = sampleAlerts,
                    isLoading = false,
                    onAlertClick = { /* TODO: navigate to alert detail */ }
                )
            }

            // Tab 3: Settings
            composable(Screen.Settings.route) {
                SettingsScreen(
                    devices = sampleDevices,
                    userProfile = sampleProfile,
                    isLoading = false,
                    onAddDevice = { /* TODO: show add device dialog */ },
                    onEditDevice = { /* TODO: navigate to device edit */ },
                    onDeleteDevice = { /* TODO: confirm delete */ },
                    onEditProfile = { /* TODO: navigate to profile edit */ }
                )
            }
        }
    }
}
