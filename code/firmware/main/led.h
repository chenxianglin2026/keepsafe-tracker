/*
 * led.h — LED Status Indicators
 *
 * Three LEDs: Blue (network), Green (GPS), Red (alerts)
 * All LEDs use pulsed-on driving to save power (~5 mA * 50 us sighting).
 *
 * States:
 *   - Blue solid ON     : Network connected
 *   - Green blink 1Hz   : GPS fix acquired
 *   - Red blink 0.5Hz   : Low battery
 *   - Red blink 5Hz     : SOS triggered
 *   - All OFF           : Sleep / uninitialized
 *
 * Power path note:
 *   LEDs are driven with a PWM duty cycle of ~0.25% (50 µs on, 20 ms period),
 *   yielding ~12.5 µA average at 5 mA peak — negligible for battery life.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= LED Indices ======================= */
typedef enum {
    LED_BLUE = 0,
    LED_GREEN,
    LED_RED,
    LED_COUNT,
} led_id_t;

/* ======================= LED Pattern Modes ======================= */
typedef enum {
    LED_MODE_OFF = 0,
    LED_MODE_SOLID,          // Always on (pulsed, appears constant)
    LED_MODE_BLINK_1HZ,      // Green: GPS fix
    LED_MODE_BLINK_0_5HZ,    // Red: low battery
    LED_MODE_BLINK_5HZ,      // Red: SOS
    LED_MODE_PULSE_ONCE,     // Single pulse (for button press feedback)
} led_mode_t;

/* ======================= LED State ======================= */
typedef struct {
    led_id_t   id;
    led_mode_t mode;
    uint32_t   last_toggle_ms;
    bool       current_on;
} led_state_t;

/* ======================= Public API ======================= */

/**
 * @brief Initialize LED GPIOs and PWM timer.
 * Sets up timer-based pulsing for all three LEDs.
 */
void led_init(void);

/**
 * @brief Set a specific LED's mode.
 * @param led  Which LED (BLUE, GREEN, RED)
 * @param mode LED mode (OFF, SOLID, BLINK_*)
 */
void led_set_mode(led_id_t led, led_mode_t mode);

/**
 * @brief Get current LED mode.
 */
led_mode_t led_get_mode(led_id_t led);

/**
 * @brief Periodic LED update — call from main loop at ~50 Hz.
 * Handles blink patterns and pulsing.
 */
void led_update(void);

/**
 * @brief Quick blip — pulse an LED once for user feedback.
 * Non-blocking, runs asynchronously.
 */
void led_blip(led_id_t led);

/**
 * @brief Turn all LEDs off immediately.
 */
void led_all_off(void);

/**
 * @brief Set the overall LED enable (master kill for deep sleep).
 * When disabled, all LEDs are off regardless of their mode.
 */
void led_set_enabled(bool enabled);

#ifdef __cplusplus
}
#endif
