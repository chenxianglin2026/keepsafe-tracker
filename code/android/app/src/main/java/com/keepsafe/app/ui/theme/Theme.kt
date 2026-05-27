package com.keepsafe.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = Blue40,
    onPrimary = Color.White,
    primaryContainer = Blue80,
    secondary = BlueGrey40,
    onSecondary = Color.White,
    secondaryContainer = BlueGrey80,
    tertiary = Teal40,
    onTertiary = Color.White,
    tertiaryContainer = Teal80,
    background = SurfaceLight,
    surface = CardBackground,
    error = StatusDanger
)

private val DarkColorScheme = darkColorScheme(
    primary = Blue80,
    onPrimary = Blue40,
    primaryContainer = Blue40,
    secondary = BlueGrey80,
    onSecondary = BlueGrey40,
    secondaryContainer = BlueGrey40,
    tertiary = Teal80,
    onTertiary = Teal40,
    tertiaryContainer = Teal40,
    background = SurfaceDark,
    surface = CardBackgroundDark,
    error = StatusDanger
)

@Composable
fun KeepSafeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
