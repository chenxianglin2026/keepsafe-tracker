/*
 * power.c — Power Management + Dynamic Location Frequency Implementation
 *
 * State machine controls:
 *   - GPS on/off based on motion state
 *   - Location reporting interval (5 min moving, 30 min stationary)
 *   - Deep sleep entry with configurable wake sources
 *   - Wake reason detection at boot
 *
 * Deep sleep wake sources:
 *   - RTC timer (periodic report)
 *   - GPIO (SOS button long press)
 *   - GPIO (LIS3DH INT1 motion detection)
 *
 * On wake, the device should:
 *   1. Check wake reason
 *   2. If TIMER: take fix, report, go back to sleep
 *   3. If MOTION: start GPS, monitor for SOS, report periodically
 *   4. If SOS_BUTTON: immediate SOS report
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "sdkconfig.h"
#include "power.h"
#include "config.h"

static const char *TAG = "POWER";

/* ======================= Internal State ======================= */

static power_management_t s_pm = {
    .state = POWER_STATE_STATIONARY,
    .wake_reason = WAKE_REASON_RESET,
    .gps_on = false,
    .lbs_fallback = false,
    .last_location_report_ms = 0,
    .last_heartbeat_ms = 0,
    .last_motion_detected_ms = 0,
    .stationary_start_ms = 0,
    .just_stopped_timeout_ms = 60000,       // 1 minute in JUST_STOPPED
    .deep_sleep_duration_ms = 30 * 60 * 1000, // 30 min default
    .uptime_ms = 0,
    .location_report_count = 0,
    .sos_trigger_count = 0,
};

static SemaphoreHandle_t s_power_mutex = NULL;

/* ======================= Static Helpers ======================= */

static const char *state_name(power_state_t s)
{
    switch (s) {
        case POWER_STATE_STATIONARY:   return "STATIONARY";
        case POWER_STATE_MOVING:       return "MOVING";
        case POWER_STATE_JUST_STOPPED: return "JUST_STOPPED";
        case POWER_STATE_SOS_ACTIVE:   return "SOS_ACTIVE";
        case POWER_STATE_DEEP_SLEEP:   return "DEEP_SLEEP";
        default:                       return "UNKNOWN";
    }
}

static const char *wake_reason_name(wake_reason_t r)
{
    switch (r) {
        case WAKE_REASON_NONE:        return "NONE";
        case WAKE_REASON_TIMER:       return "TIMER";
        case WAKE_REASON_MOTION:      return "MOTION";
        case WAKE_REASON_SOS_BUTTON:  return "SOS_BUTTON";
        case WAKE_REASON_RESET:       return "RESET";
        default:                      return "UNKNOWN";
    }
}

/* ======================= Wake Reason Detection ======================= */

/**
 * Detect wake reason at boot by examining ESP32-S3 wakeup cause registers.
 */
static wake_reason_t detect_wake_reason(void)
{
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();

    switch (cause) {
        case ESP_SLEEP_WAKEUP_EXT0:
        case ESP_SLEEP_WAKEUP_EXT1:
            // Check which GPIO woke us
        {
            uint64_t gpio_mask = esp_sleep_get_ext1_wakeup_status();
            if (gpio_mask & (1ULL << GPIO_SOS_BUTTON)) {
                return WAKE_REASON_SOS_BUTTON;
            }
            if (gpio_mask & (1ULL << GPIO_LIS3DH_INT1)) {
                return WAKE_REASON_MOTION;
            }
            return WAKE_REASON_SOS_BUTTON; // Default to SOS if unknown GPIO
        }

        case ESP_SLEEP_WAKEUP_TIMER:
            return WAKE_REASON_TIMER;

        case ESP_SLEEP_WAKEUP_UNDEFINED:
        default:
            return WAKE_REASON_RESET; // Cold boot
    }
}

/* ======================= Public API ======================= */

void power_init(void)
{
    if (s_power_mutex == NULL) {
        s_power_mutex = xSemaphoreCreateMutex();
    }

    // Detect wake reason
    s_pm.wake_reason = detect_wake_reason();
    ESP_LOGI(TAG, "Power management initialized");
    ESP_LOGI(TAG, "Wake reason: %s", wake_reason_name(s_pm.wake_reason));

    // Set initial state based on wake reason
    switch (s_pm.wake_reason) {
        case WAKE_REASON_MOTION:
            s_pm.state = POWER_STATE_MOVING;
            break;
        case WAKE_REASON_SOS_BUTTON:
            s_pm.state = POWER_STATE_SOS_ACTIVE;
            break;
        case WAKE_REASON_TIMER:
            // Stay in whatever state we were in before sleep
            // (stored in RTC memory, but for now default to STATIONARY)
            s_pm.state = POWER_STATE_STATIONARY;
            break;
        case WAKE_REASON_RESET:
        default:
            s_pm.state = POWER_STATE_STATIONARY;
            break;
    }

    s_pm.uptime_ms = 0;
    s_pm.last_location_report_ms = 0;
    s_pm.last_heartbeat_ms = 0;

    ESP_LOGI(TAG, "Initial state: %s", state_name(s_pm.state));

    // If SOS was triggered, handle immediately in main loop
    if (s_pm.wake_reason == WAKE_REASON_SOS_BUTTON) {
        ESP_LOGW(TAG, "Woke from SOS button!");
    }
}

power_state_t power_get_state(void)
{
    return s_pm.state;
}

void power_set_state(power_state_t new_state)
{
    if (s_power_mutex) xSemaphoreTake(s_power_mutex, portMAX_DELAY);

    power_state_t old_state = s_pm.state;
    s_pm.state = new_state;

    ESP_LOGI(TAG, "State: %s -> %s", state_name(old_state), state_name(new_state));

    // State transition actions
    switch (new_state) {
        case POWER_STATE_STATIONARY:
            // GPS is off; LBS only
            s_pm.gps_on = false;
            s_pm.lbs_fallback = true;
            s_pm.stationary_start_ms = esp_timer_get_time() / 1000;
            s_pm.deep_sleep_duration_ms = INTERVAL_STATIONARY_MS;
            break;

        case POWER_STATE_MOVING:
            // GPS on for high-frequency tracking
            s_pm.gps_on = true;
            s_pm.lbs_fallback = false;
            s_pm.deep_sleep_duration_ms = INTERVAL_MOVING_MS;
            break;

        case POWER_STATE_JUST_STOPPED:
            // Keep GPS on for one more fix, then transition
            s_pm.gps_on = true;
            s_pm.deep_sleep_duration_ms = 60000; // 1 minute
            break;

        case POWER_STATE_SOS_ACTIVE:
            s_pm.gps_on = true;
            s_pm.sos_trigger_count++;
            s_pm.deep_sleep_duration_ms = INTERVAL_SOS_REPEAT_MS;
            break;

        case POWER_STATE_DEEP_SLEEP:
            // Final state before entering deep sleep
            break;
    }

    if (s_power_mutex) xSemaphoreGive(s_power_mutex);
}

void power_on_motion_detected(void)
{
    if (s_pm.state == POWER_STATE_STATIONARY) {
        ESP_LOGI(TAG, "Motion detected -> MOVING");
        power_set_state(POWER_STATE_MOVING);
    }

    s_pm.last_motion_detected_ms = esp_timer_get_time() / 1000;
}

void power_on_stationary_timeout(void)
{
    if (s_pm.state == POWER_STATE_MOVING) {
        ESP_LOGI(TAG, "No motion for timeout -> JUST_STOPPED");
        power_set_state(POWER_STATE_JUST_STOPPED);
    }
}

void power_on_sos_triggered(void)
{
    ESP_LOGW(TAG, "SOS triggered -> SOS_ACTIVE");
    power_set_state(POWER_STATE_SOS_ACTIVE);
}

uint32_t power_get_next_report_interval(void)
{
    switch (s_pm.state) {
        case POWER_STATE_MOVING:       return INTERVAL_MOVING_MS;
        case POWER_STATE_STATIONARY:   return INTERVAL_STATIONARY_MS;
        case POWER_STATE_SOS_ACTIVE:   return INTERVAL_SOS_REPEAT_MS;
        case POWER_STATE_JUST_STOPPED: return 60000; // 1 minute
        default:                       return INTERVAL_STATIONARY_MS;
    }
}

bool power_is_time_for_location_report(uint32_t now_ms)
{
    uint32_t elapsed = now_ms - s_pm.last_location_report_ms;
    return (elapsed >= power_get_next_report_interval());
}

bool power_is_time_for_heartbeat(uint32_t now_ms)
{
    uint32_t elapsed = now_ms - s_pm.last_heartbeat_ms;
    return (elapsed >= INTERVAL_HEARTBEAT_MS);
}

void power_on_location_reported(uint32_t now_ms)
{
    s_pm.last_location_report_ms = now_ms;
    s_pm.location_report_count++;
}

void power_on_heartbeat_sent(uint32_t now_ms)
{
    s_pm.last_heartbeat_ms = now_ms;
}

wake_reason_t power_get_wake_reason(void)
{
    return s_pm.wake_reason;
}

void power_set_wake_reason(wake_reason_t reason)
{
    s_pm.wake_reason = reason;
}

uint32_t power_calculate_sleep_duration(void)
{
    // Calculate how long until the next event
    uint32_t now_ms = esp_timer_get_time() / 1000;
    uint32_t next_report = s_pm.last_location_report_ms + power_get_next_report_interval();
    uint32_t next_heartbeat = s_pm.last_heartbeat_ms + INTERVAL_HEARTBEAT_MS;

    uint32_t next_event = (next_report < next_heartbeat) ? next_report : next_heartbeat;
    uint32_t duration = (next_event > now_ms) ? (next_event - now_ms) : power_get_next_report_interval();

    // Cap at configured interval
    uint32_t max_sleep = power_get_next_report_interval();
    if (duration > max_sleep) duration = max_sleep;

    // Minimum sleep of 1 second to avoid busy-waiting
    if (duration < 1000) duration = 1000;

    ESP_LOGI(TAG, "Calculated sleep: %lu ms (next event in %lu ms)", duration, next_event - now_ms);
    return duration;
}

void power_gps_on(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) {
        ESP_LOGE(TAG, "Cannot power on GPS: no UART send function");
        return;
    }

    uart_send_func("AT+CGNSPWR=1\r\n");
    s_pm.gps_on = true;
    ESP_LOGI(TAG, "GPS powered ON");
}

void power_gps_off(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) {
        ESP_LOGE(TAG, "Cannot power off GPS: no UART send function");
        return;
    }

    uart_send_func("AT+CGNSPWR=0\r\n");
    s_pm.gps_on = false;
    s_pm.lbs_fallback = true;
    ESP_LOGI(TAG, "GPS powered OFF (falling back to LBS)");
}

void power_enter_deep_sleep(void)
{
    ESP_LOGI(TAG, "=== Entering Deep Sleep ===");
    ESP_LOGI(TAG, "State: %s, GPS: %s, Wake reason: %s",
             state_name(s_pm.state),
             s_pm.gps_on ? "ON" : "OFF",
             wake_reason_name(s_pm.wake_reason));

    // Configure wake-up sources

    // 1. Timer wake-up
    uint32_t sleep_us = power_calculate_sleep_duration() * 1000ULL;
    esp_sleep_enable_timer_wakeup(sleep_us);
    ESP_LOGI(TAG, "Timer wake: %lu us (%lu ms)", sleep_us, sleep_us / 1000);

    // 2. GPIO wake-up (EXT1) for SOS button + motion detection
    // Both are on RTC_GPIOs
    const uint64_t wake_pins = DEEP_SLEEP_WAKE_PINS_BITMASK;
    esp_sleep_enable_ext1_wakeup(wake_pins, ESP_EXT1_WAKEUP_ANY_HIGH);

    ESP_LOGI(TAG, "GPIO wake: pins=0x%llx", wake_pins);

    // 3. Ensure UART TX is complete before sleep
    vTaskDelay(pdMS_TO_TICKS(50));

    // Flush and enter sleep
    esp_deep_sleep_start();
}

void power_get_stats(uint32_t *location_count, uint32_t *sos_count)
{
    if (location_count) *location_count = s_pm.location_report_count;
    if (sos_count) *sos_count = s_pm.sos_trigger_count;
}
