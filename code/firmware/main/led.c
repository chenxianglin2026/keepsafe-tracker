/*
 * led.c — LED Status Indicators Implementation
 *
 * Uses ESP-IDF's LEDC (PWM) peripheral for power-efficient LED driving.
 * LEDs are pulsed with a very short duty cycle:
 *   - Pulse width: 50 µs (visible flash)
 *   - Period: 20 ms (50 Hz, avoids visible flicker)
 *   - Duty: 50 µs / 20 ms = 0.25% -> ~12.5 µA average at 5 mA peak
 *
 * For blink patterns, the PWM is gated on/off at the desired frequency.
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "led.h"
#include "config.h"

static const char *TAG = "LED";

/* ======================= Internal State ======================= */

#define LEDC_TIMER              LEDC_TIMER_0
#define LEDC_MODE               LEDC_LOW_SPEED_MODE
#define LEDC_DUTY_RES           LEDC_TIMER_8_BIT    // 8-bit resolution (0-255)
#define LEDC_FREQ_HZ            50                  // 50 Hz PWM period

static bool s_led_enabled = true;
static led_state_t s_leds[LED_COUNT];

// LEDC channel assignments
static const ledc_channel_t s_led_channels[LED_COUNT] = {
    LEDC_CHANNEL_0,  // BLUE
    LEDC_CHANNEL_1,  // GREEN
    LEDC_CHANNEL_2,  // RED
};

// GPIO pin mapping
static const gpio_num_t s_led_gpios[LED_COUNT] = {
    GPIO_LED_BLUE,
    GPIO_LED_GREEN,
    GPIO_LED_RED,
};

/* ======================= LEDC PWM Setup ======================= */

void led_init(void)
{
    // Configure LEDC timer
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_MODE,
        .timer_num        = LEDC_TIMER,
        .duty_resolution  = LEDC_DUTY_RES,
        .freq_hz          = LEDC_FREQ_HZ,
        .clk_cfg          = LEDC_AUTO_CLK,
    };
    ledc_timer_config(&ledc_timer);

    // Configure each LED channel
    for (int i = 0; i < LED_COUNT; i++) {
        ledc_channel_config_t ledc_ch = {
            .channel    = s_led_channels[i],
            .duty       = 0,  // Start OFF
            .gpio_num   = s_led_gpios[i],
            .speed_mode = LEDC_MODE,
            .hpoint     = 0,
            .timer_sel  = LEDC_TIMER,
        };
        ledc_channel_config(&ledc_ch);

        // Initialize state
        s_leds[i].id = (led_id_t)i;
        s_leds[i].mode = LED_MODE_OFF;
        s_leds[i].last_toggle_ms = 0;
        s_leds[i].current_on = false;
    }

    ESP_LOGI(TAG, "LED driver initialized (PWM, %d Hz, %d-bit)", LEDC_FREQ_HZ, 8);
}

/* ======================= Internal Helper ======================= */

/**
 * Set LED PWM duty. Duty 0 = OFF, 255 = full on.
 * But we never use full duty — we pulse at ~50 µs.
 * At 50 Hz, period = 20,000 µs. 50 µs / 20,000 µs * 256 ≈ 0.64 -> duty=1
 * We'll use a fixed duty of 1 for "on" (barely visible but power-efficient).
 */
static void led_set_duty(led_id_t led, uint8_t duty)
{
    if (!s_led_enabled) {
        duty = 0;
    }
    ledc_set_duty(LEDC_MODE, s_led_channels[led], duty);
    ledc_update_duty(LEDC_MODE, s_led_channels[led]);

    s_leds[led].current_on = (duty > 0);
}

/* ======================= Public API ======================= */

void led_set_mode(led_id_t led, led_mode_t mode)
{
    if (led >= LED_COUNT) return;

    s_leds[led].mode = mode;
    s_leds[led].last_toggle_ms = esp_timer_get_time() / 1000; // ms

    // Immediate action for OFF and SOLID
    if (mode == LED_MODE_OFF) {
        led_set_duty(led, 0);
    } else if (mode == LED_MODE_SOLID) {
        led_set_duty(led, 1); // Pulse-width "on"
    } else if (mode == LED_MODE_PULSE_ONCE) {
        led_set_duty(led, 1);
    }

    ESP_LOGD(TAG, "LED %d mode -> %d", led, mode);
}

led_mode_t led_get_mode(led_id_t led)
{
    if (led >= LED_COUNT) return LED_MODE_OFF;
    return s_leds[led].mode;
}

void led_update(void)
{
    uint32_t now_ms = esp_timer_get_time() / 1000;

    for (int i = 0; i < LED_COUNT; i++) {
        led_state_t *l = &s_leds[i];

        switch (l->mode) {
            case LED_MODE_OFF:
                // Already off from set_mode
                break;

            case LED_MODE_SOLID:
                // PWM is already set; no update needed
                break;

            case LED_MODE_BLINK_1HZ: {
                // 1 Hz = 500 ms on, 500 ms off
                uint32_t period = 1000;
                uint32_t half = 500;
                if (((now_ms - l->last_toggle_ms) % period) < half) {
                    if (!l->current_on) led_set_duty((led_id_t)i, 1);
                } else {
                    if (l->current_on) led_set_duty((led_id_t)i, 0);
                }
                break;
            }

            case LED_MODE_BLINK_0_5HZ: {
                // 0.5 Hz = 1000 ms on, 1000 ms off
                uint32_t period = 2000;
                uint32_t half = 1000;
                if (((now_ms - l->last_toggle_ms) % period) < half) {
                    if (!l->current_on) led_set_duty((led_id_t)i, 1);
                } else {
                    if (l->current_on) led_set_duty((led_id_t)i, 0);
                }
                break;
            }

            case LED_MODE_BLINK_5HZ: {
                // 5 Hz = 100 ms on, 100 ms off
                uint32_t period = 200;
                uint32_t half = 100;
                if (((now_ms - l->last_toggle_ms) % period) < half) {
                    if (!l->current_on) led_set_duty((led_id_t)i, 1);
                } else {
                    if (l->current_on) led_set_duty((led_id_t)i, 0);
                }
                break;
            }

            case LED_MODE_PULSE_ONCE: {
                // Single pulse: on for 50 ms then revert to previous mode or off
                if (l->current_on && (now_ms - l->last_toggle_ms) > 50) {
                    led_set_duty((led_id_t)i, 0);
                    l->mode = LED_MODE_OFF; // Revert to off after pulse
                }
                break;
            }

            default:
                break;
        }
    }
}

void led_blip(led_id_t led)
{
    if (led >= LED_COUNT) return;
    led_set_mode(led, LED_MODE_PULSE_ONCE);
}

void led_all_off(void)
{
    for (int i = 0; i < LED_COUNT; i++) {
        led_set_mode((led_id_t)i, LED_MODE_OFF);
    }
}

void led_set_enabled(bool enabled)
{
    s_led_enabled = enabled;
    if (!enabled) {
        for (int i = 0; i < LED_COUNT; i++) {
            led_set_duty((led_id_t)i, 0);
        }
    }
    ESP_LOGI(TAG, "LED master %s", enabled ? "enabled" : "disabled");
}
