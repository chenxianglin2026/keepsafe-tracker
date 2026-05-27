/*
 * power.h — Power Management + Dynamic Location Frequency
 *
 * Implements the motion state machine:
 *   Stationary -> Moving -> Just-Stopped -> Stationary
 *
 * Controls GPS on/off, location reporting interval, and deep sleep.
 *
 * Power path notes:
 *   - MCU deep sleep: ~8 µA (ESP32-S3 with RTC timer + GPIO wake).
 *   - Modem PSM: ~15 µA (Air780E in power saving mode).
 *   - Accelerometer LP: ~2 µA (LIS3DH at 1 Hz low-power).
 *   - GPS active: ~35-75 mA (Air780E GNSS receiver ON).
 *   - GPS off (LBS only): ~0.4 mA (modem idle).
 *   - Total deep sleep: ~25 µA (MCU 8 + modem 15 + accel 2).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= Power State Machine ======================= */
typedef enum {
    POWER_STATE_STATIONARY = 0,     // GPS OFF, LBS only, 30-min interval
    POWER_STATE_MOVING,             // GPS ON, 5-min interval
    POWER_STATE_JUST_STOPPED,       // GPS ON, one more fix, then transition to STATIONARY
    POWER_STATE_SOS_ACTIVE,         // SOS mode: GPS ON, high-frequency reporting
    POWER_STATE_DEEP_SLEEP,         // Entering deep sleep (all devices powered down)
} power_state_t;

/* ======================= Wake-up Reasons ======================= */
typedef enum {
    WAKE_REASON_NONE = 0,
    WAKE_REASON_TIMER,              // RTC timer expired (periodic report)
    WAKE_REASON_MOTION,             // LIS3DH motion interrupt
    WAKE_REASON_SOS_BUTTON,         // SOS button long press
    WAKE_REASON_RESET,              // Power-on or software reset
} wake_reason_t;

/* ======================= Power Management Config ======================= */
typedef struct {
    // Current state
    power_state_t       state;
    wake_reason_t       wake_reason;

    // Timing
    uint32_t            last_location_report_ms;
    uint32_t            last_heartbeat_ms;
    uint32_t            last_motion_detected_ms;
    uint32_t            stationary_start_ms;   // When we entered stationary
    uint32_t            just_stopped_timeout_ms; // How long to stay in JUST_STOPPED

    // GPS control
    bool                gps_on;
    bool                lbs_fallback;           // Using LBS instead of GPS

    // Deep sleep
    uint32_t            deep_sleep_duration_ms; // Next deep sleep duration

    // Statistics
    uint32_t            uptime_ms;
    uint32_t            location_report_count;
    uint32_t            sos_trigger_count;
} power_management_t;

/* ======================= Public API ======================= */

/**
 * @brief Initialize power management state machine.
 */
void power_init(void);

/**
 * @brief Get current power state.
 */
power_state_t power_get_state(void);

/**
 * @brief Transition to a new state.
 * Handles GPS on/off, LED updates, and deep sleep configuration.
 */
void power_set_state(power_state_t new_state);

/**
 * @brief Called when motion is detected by LIS3DH.
 * Transitions to MOVING state if currently STATIONARY.
 */
void power_on_motion_detected(void);

/**
 * @brief Called when device has been stationary for a configurable timeout.
 * Transitions STATIONARY if currently MOVING with no motion detected.
 */
void power_on_stationary_timeout(void);

/**
 * @brief Called when SOS is triggered.
 * Transitions to SOS_ACTIVE state.
 */
void power_on_sos_triggered(void);

/**
 * @brief Get the interval until the next location report, in ms.
 * Depends on current state:
 *   MOVING:     5 minutes
 *   STATIONARY: 30 minutes
 *   SOS:        30 seconds (first 5, then normal)
 */
uint32_t power_get_next_report_interval(void);

/**
 * @brief Check if it's time for a location report.
 * @param now_ms Current time in milliseconds.
 * @return true if a report should be sent now.
 */
bool power_is_time_for_location_report(uint32_t now_ms);

/**
 * @brief Check if it's time for a heartbeat.
 * @param now_ms Current time in milliseconds.
 * @return true if heartbeat should be sent.
 */
bool power_is_time_for_heartbeat(uint32_t now_ms);

/**
 * @brief Called after a location report is sent.
 * Updates internal timestamps.
 */
void power_on_location_reported(uint32_t now_ms);

/**
 * @brief Called after heartbeat is sent.
 */
void power_on_heartbeat_sent(uint32_t now_ms);

/**
 * @brief Get current wake reason.
 */
wake_reason_t power_get_wake_reason(void);

/**
 * @brief Set wake reason (called at boot from wake stub).
 */
void power_set_wake_reason(wake_reason_t reason);

/**
 * @brief Configure and enter deep sleep.
 * Sets RTC timer for next wake, configures GPIO wake sources.
 * This function does not return.
 */
void power_enter_deep_sleep(void) __attribute__((noreturn));

/**
 * @brief Calculate deep sleep duration based on current state.
 * @return Sleep duration in milliseconds.
 */
uint32_t power_calculate_sleep_duration(void);

/**
 * @brief Power up Air780E GNSS (GPS).
 * Sends AT+CGNSPWR=1 via UART function.
 */
void power_gps_on(void (*uart_send_func)(const char *cmd));

/**
 * @brief Power down Air780E GNSS (GPS off).
 * Sends AT+CGNSPWR=0 via UART function.
 */
void power_gps_off(void (*uart_send_func)(const char *cmd));

/**
 * @brief Get power management statistics.
 */
void power_get_stats(uint32_t *location_count, uint32_t *sos_count);

#ifdef __cplusplus
}
#endif
