package com.keepsafe.app.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Navigation route constants for BottomNavigation tabs.
 */
sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector
) {
    data object Map : Screen(
        route = "map",
        title = "地图",
        icon = Icons.Default.LocationOn
    )

    data object Alerts : Screen(
        route = "alerts",
        title = "告警",
        icon = Icons.Default.Notifications
    )

    data object Settings : Screen(
        route = "settings",
        title = "设置",
        icon = Icons.Default.Settings
    )

    companion object {
        val bottomNavItems = listOf(Map, Alerts, Settings)
    }
}
