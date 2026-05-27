/*
 * sos.h — SOS Button + Low Battery Detection
 *
 * SOS: Long press 3s on GPIO. Uses external interrupt + debounce.
 * On trigger: reports current location + press duration, vibro feedback.
 *
 * Low Battery: ADC reads battery voltage, converts to percentage.
 * Threshold at 20% triggers low battery alert topic.
 *
 * Power path note:
 *   - SOS button is on RTC_GPIO, can wake ESP32-S3 from deep sleep.
 *   - Battery ADC is read on-demand (not continuously) to save power.
 *   - A voltage divider consumes ~1-5 µA; we could add a control FET to
 *     disconnect it during deep sleep for further savings.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= SOS Event ======================= */
typedef struct {
    uint32_t timestamp_unix;      // When SOS was triggered
    double   latitude;
    double   longitude;
    float    accuracy;            // Estimated accuracy in meters
    uint8_t  battery_percent;
    uint32_t trigger_duration_ms; // How long button was held
} sos_event_t;

/* ======================= SOS State ======================= */
typedef enum {
    SOS_IDLE = 0,
    SOS_PRESSING,               // Button down, counting duration
    SOS_TRIGGERED,              // Long press confirmed, alert sent
    SOS_COOLDOWN,               // Debounce after release
} sos_state_t;

/* ======================= Battery Level ======================= */
typedef struct {
    uint8_t  percent;            // 0-100%
    uint16_t voltage_mv;         // Raw battery voltage in mV
    bool     charging;           // Is charging detected? (requires charging circuit)
} battery_level_t;

/* ======================= Callbacks ======================= */

/**
 * @brief Callback when SOS is triggered.
 * @param event  SOS event details (lat, lng, duration, battery)
 * @param user_data  User pointer (opaque)
 */
typedef void (*sos_triggered_callback_t)(const sos_event_t *event, void *user_data);

/**
 * @brief Callback when battery drops to/ below threshold.
 * @param battery  Current battery level
 * @param user_data  User pointer
 */
typedef void (*low_battery_callback_t)(const battery_level_t *battery, void *user_data);

/* ======================= Public API ======================= */

/**
 * @brief Initialize SOS button and battery ADC.
 * Configures GPIO interrupt for SOS button and ADC for battery reading.
 *
 * @param sos_cb       Callback on SOS trigger
 * @param battery_cb   Callback on low battery (≤20%)
 * @param user_data    User pointer passed to callbacks
 */
void sos_init(sos_triggered_callback_t sos_cb,
              low_battery_callback_t   battery_cb,
              void                    *user_data);

/**
 * @brief Call from GPIO ISR when SOS button state changes.
 * @param level 1 = pressed, 0 = released
 */
void sos_button_isr(int level);

/**
 * @brief Read battery voltage and compute percentage.
 * @return battery_level_t with voltage and percent.
 */
battery_level_t sos_read_battery(void);

/**
 * @brief Manually trigger SOS (e.g., from button ISR wake path).
 * Public API for the main state machine to call after button ISR.
 */
void sos_trigger(void);

/**
 * @brief Get current SOS state.
 */
sos_state_t sos_get_state(void);

/**
 * @brief Reset SOS state to idle.
 */
void sos_reset(void);

/**
 * @brief Feed vibration motor feedback.
 * Pulses the motor for a configured duration.
 */
void sos_vibrate_feedback(uint32_t duration_ms);

/**
 * @brief Periodic tick for SOS debounce and timing.
 * Call from main loop at ~10 Hz.
 */
void sos_tick(void);

/**
 * @brief Check if a low battery alert should be sent (latch cleared after send).
 * @return true if low battery alert is pending.
 */
bool sos_is_low_battery_alert_pending(void);

/**
 * @brief Mark low battery alert as sent.
 */
void sos_clear_low_battery_alert(void);

/**
 * @brief Check if SOS was just triggered (latch cleared after read).
 * @return true if SOS triggered since last check.
 */
bool sos_was_triggered(void);

/**
 * @brief Get the last SOS event data.
 */
const sos_event_t *sos_get_last_event(void);

#ifdef __cplusplus
}
#endif
