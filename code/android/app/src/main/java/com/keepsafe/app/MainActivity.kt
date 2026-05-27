package com.keepsafe.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.keepsafe.app.ui.navigation.KeepSafeNavHost
import com.keepsafe.app.ui.theme.KeepSafeTheme

/**
 * Main entry point for KeepSafe Android App.
 * Renders the Jetpack Compose UI with BottomNavigation (3 tabs).
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            KeepSafeTheme {
                KeepSafeNavHost()
            }
        }
    }
}
