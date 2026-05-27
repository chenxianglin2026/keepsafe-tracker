/*
 * sos.c — SOS Button + Low Battery Detection Implementation
 *
 * Hardware:
 *   - SOS button on GPIO 4 (RTC_GPIO, pull-up, active-low press).
 *   - Vibration motor on GPIO 5 (active high).
 *   - Battery ADC on GPIO 7 (ADC1_CH6, voltage divider).
 *
 * Power path notes:
 *   - SOS button ISR sets a flag; main loop processes timing.
 *   - Battery ADC read blocks for ~1 ms each call. Only read on-demand.
 *   - Vibration motor draws ~80 mA; pulse only 200 ms for feedback.
 *   - The ADC voltage divider draws ~1-5 µA continuously. For ultra-low
 *     power, a GPIO-controlled NMOS can disconnect the divider during sleep.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "esp_adc_cal.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "sos.h"
#include "config.h"

static const char *TAG = "SOS";

/* ======================= Internal State ======================= */

typedef struct {
    // SOS state
    sos_state_t     state;
    uint32_t        press_start_ms;     // When button was first pressed
    uint32_t        last_debounce_ms;   // Last debounce sample time
    int             last_button_level;  // Last stable button level

    // SOS trigger latch
    bool            triggered;
    sos_event_t     last_event;

    // Low battery
    battery_level_t battery;
    bool            low_battery_alert_pending;
    bool            low_battery_sent;   // Prevent repeat alerts until level changes

    // Callbacks
    sos_triggered_callback_t sos_cb;
    low_battery_callback_t   battery_cb;
    void                    *user_data;

    // ADC calibration
    esp_adc_cal_characteristics_t adc_chars;
    bool                         adc_calibrated;

    // Mutex
    SemaphoreHandle_t mutex;
} sos_context_t;

static sos_context_t s_sos = {0};

/* ======================= ADC Initialization ======================= */

static void init_adc(void)
{
    // ADC1 channel configuration
    adc1_config_width(ADC_WIDTH_BIT_12);  // 12-bit resolution (0-4095)
    adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_ATTEN_DB_12); // GPIO 7, 0-3.3V range

    // Calibration
    s_sos.adc_calibrated = esp_adc_cal_characterize(
        ADC_UNIT_1,
        ADC_ATTEN_DB_12,
        ADC_WIDTH_BIT_12,
        3300,   // Default Vref
        &s_sos.adc_chars
    );

    if (!s_sos.adc_calibrated) {
        ESP_LOGW(TAG, "ADC calibration not available (using default Vref)");
    }

    ESP_LOGI(TAG, "Battery ADC initialized (12-bit, 3.3V range)");
}

/* ======================= Battery Reading ======================= */

battery_level_t sos_read_battery(void)
{
    battery_level_t result = {0};

    // Read ADC multiple times and average for stability
    uint32_t adc_sum = 0;
    const int samples = 8;
    for (int i = 0; i < samples; i++) {
        adc_sum += adc1_get_raw(ADC1_CHANNEL_6);
        esp_rom_delay_us(100); // Small delay between samples
    }
    uint32_t adc_avg = adc_sum / samples;

    // Convert ADC raw to voltage in mV
    uint32_t voltage_mv = 0;
    if (s_sos.adc_calibrated) {
        voltage_mv = esp_adc_cal_raw_to_voltage(adc_avg, &s_sos.adc_chars);
    } else {
        // Approximate: 4095 -> 3300 mV
        voltage_mv = adc_avg * 3300 / 4095;
    }

    // Account for voltage divider (assume R1=R2, so multiply by 2)
    uint32_t bat_voltage_mv = (uint32_t)(voltage_mv * BAT_DIVIDER_RATIO);

    // Compute percentage (linear interpolation between EMPTY and FULL)
    uint8_t percent = 0;
    if (bat_voltage_mv >= BAT_VOLTAGE_FULL_MV) {
        percent = 100;
    } else if (bat_voltage_mv <= BAT_VOLTAGE_EMPTY_MV) {
        percent = 0;
    } else {
        uint32_t range = BAT_VOLTAGE_FULL_MV - BAT_VOLTAGE_EMPTY_MV;
        uint32_t offset = bat_voltage_mv - BAT_VOLTAGE_EMPTY_MV;
        percent = (uint8_t)(offset * 100 / range);
    }

    // Clamp
    if (percent > 100) percent = 100;

    result.percent = percent;
    result.voltage_mv = bat_voltage_mv;
    result.charging = false; // No charging detection circuit in this design

    // Update internal state
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, portMAX_DELAY)) {
        s_sos.battery = result;

        // Low battery check
        if (percent <= BAT_LOW_PERCENT && !s_sos.low_battery_sent) {
            s_sos.low_battery_alert_pending = true;
        } else if (percent > BAT_LOW_PERCENT) {
            s_sos.low_battery_alert_pending = false;
            s_sos.low_battery_sent = false; // Reset once battery recovers
        }

        xSemaphoreGive(s_sos.mutex);
    }

    ESP_LOGD(TAG, "Battery: %u mV, %u%%%s",
             bat_voltage_mv, percent,
             (percent <= BAT_LOW_PERCENT) ? " [LOW]" : "");

    return result;
}

/* ======================= ISR Handler ======================= */

static void IRAM_ATTR sos_gpio_isr_handler(void *arg)
{
    int level = gpio_get_level(GPIO_SOS_BUTTON);
    sos_button_isr(level);
}

void sos_button_isr(int level)
{
    // In ISR context — just set the level; the tick handler does timing
    // We use a simple latch approach: the tick handler checks level periodically
    // This avoids complex ISR timing
    BaseType_t must_yield = pdFALSE;

    if (s_sos.mutex) {
        xSemaphoreTakeFromISR(s_sos.mutex, &must_yield);
        s_sos.last_button_level = level;
        if (level == 0) { // Pressed (active low)
            if (s_sos.state == SOS_IDLE) {
                s_sos.state = SOS_PRESSING;
                s_sos.press_start_ms = esp_timer_get_time() / 1000;
            }
        } else { // Released
            if (s_sos.state == SOS_PRESSING || s_sos.state == SOS_TRIGGERED) {
                s_sos.state = SOS_COOLDOWN;
                s_sos.last_debounce_ms = esp_timer_get_time() / 1000;
            }
        }
        xSemaphoreGiveFromISR(s_sos.mutex, &must_yield);
    }

    if (must_yield) {
        portYIELD_FROM_ISR();
    }
}

/* ======================= SOS Trigger ======================= */

void sos_trigger(void)
{
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, portMAX_DELAY)) {
        s_sos.triggered = true;

        // Fill event with best available data
        s_sos.last_event.timestamp_unix = 0; // Fill from main state
        s_sos.last_event.latitude = 0.0;
        s_sos.last_event.longitude = 0.0;
        s_sos.last_event.accuracy = 0.0f;
        s_sos.last_event.battery_percent = s_sos.battery.percent;
        s_sos.last_event.trigger_duration_ms =
            (esp_timer_get_time() / 1000) - s_sos.press_start_ms;

        xSemaphoreGive(s_sos.mutex);
    }

    ESP_LOGW(TAG, "SOS TRIGGERED! Duration: %lu ms",
             (esp_timer_get_time() / 1000) - s_sos.press_start_ms);

    // Vibrate feedback
    sos_vibrate_feedback(SOS_VIBRATE_MS);

    // Callback
    if (s_sos.sos_cb) {
        s_sos.sos_cb(&s_sos.last_event, s_sos.user_data);
    }
}

/* ======================= Vibration Feedback ======================= */

void sos_vibrate_feedback(uint32_t duration_ms)
{
    gpio_set_level(GPIO_VIBRATOR, 1);
    ESP_LOGI(TAG, "Vibration motor ON (%lu ms)", duration_ms);

    // Use a timer or simple delay for short pulse
    // In production, use a timer group or ledc for non-blocking operation.
    // For simplicity here, we use a small blocking delay (acceptable for
    // a 200 ms feedback pulse that happens infrequently).
    vTaskDelay(pdMS_TO_TICKS(duration_ms));

    gpio_set_level(GPIO_VIBRATOR, 0);
    ESP_LOGI(TAG, "Vibration motor OFF");
}

/* ======================= Public API ======================= */

void sos_init(sos_triggered_callback_t sos_cb,
              low_battery_callback_t   battery_cb,
              void                    *user_data)
{
    memset(&s_sos, 0, sizeof(s_sos));

    s_sos.mutex = xSemaphoreCreateMutex();
    s_sos.state = SOS_IDLE;
    s_sos.sos_cb = sos_cb;
    s_sos.battery_cb = battery_cb;
    s_sos.user_data = user_data;
    s_sos.last_button_level = 1; // Released (pull-up)

    // Configure SOS button GPIO with pull-up
    gpio_config_t btn_cfg = {
        .pin_bit_mask = (1ULL << GPIO_SOS_BUTTON),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    gpio_config(&btn_cfg);
    gpio_set_intr_type(GPIO_SOS_BUTTON, GPIO_INTR_ANYEDGE);

    // Configure vibration motor GPIO
    gpio_config_t vib_cfg = {
        .pin_bit_mask = (1ULL << GPIO_VIBRATOR),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&vib_cfg);
    gpio_set_level(GPIO_VIBRATOR, 0); // Initially off

    // Install GPIO ISR
    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_SOS_BUTTON, sos_gpio_isr_handler, NULL);

    // Initialize ADC
    init_adc();

    // Initial battery reading
    sos_read_battery();

    ESP_LOGI(TAG, "SOS+Button initialized (GPIO %d, active-low, pull-up)",
             GPIO_SOS_BUTTON);
    ESP_LOGI(TAG, "Battery: %u mV, %u%%",
             s_sos.battery.voltage_mv, s_sos.battery.percent);
}

sos_state_t sos_get_state(void)
{
    return s_sos.state;
}

void sos_reset(void)
{
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, portMAX_DELAY)) {
        s_sos.state = SOS_IDLE;
        s_sos.triggered = false;
        xSemaphoreGive(s_sos.mutex);
    }
}

bool sos_was_triggered(void)
{
    bool was = false;
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, pdMS_TO_TICKS(10))) {
        was = s_sos.triggered;
        s_sos.triggered = false; // Clear latch
        xSemaphoreGive(s_sos.mutex);
    }
    return was;
}

bool sos_is_low_battery_alert_pending(void)
{
    bool pending = false;
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, pdMS_TO_TICKS(10))) {
        pending = s_sos.low_battery_alert_pending;
        xSemaphoreGive(s_sos.mutex);
    }
    return pending;
}

void sos_clear_low_battery_alert(void)
{
    if (s_sos.mutex && xSemaphoreTake(s_sos.mutex, portMAX_DELAY)) {
        s_sos.low_battery_alert_pending = false;
        s_sos.low_battery_sent = true;
        xSemaphoreGive(s_sos.mutex);
    }
}

const sos_event_t *sos_get_last_event(void)
{
    return &s_sos.last_event;
}

void sos_tick(void)
{
    uint32_t now_ms = esp_timer_get_time() / 1000;

    if (!s_sos.mutex) return;

    if (xSemaphoreTake(s_sos.mutex, pdMS_TO_TICKS(10))) {
        switch (s_sos.state) {
            case SOS_PRESSING: {
                uint32_t elapsed = now_ms - s_sos.press_start_ms;
                if (elapsed >= SOS_LONG_PRESS_MS) {
                    s_sos.state = SOS_TRIGGERED;
                    s_sos.triggered = true;

                    // Build event
                    s_sos.last_event.timestamp_unix = now_ms / 1000;
                    s_sos.last_event.latitude = 0.0; // Filled by caller
                    s_sos.last_event.longitude = 0.0;
                    s_sos.last_event.accuracy = 0.0f;
                    s_sos.last_event.battery_percent = s_sos.battery.percent;
                    s_sos.last_event.trigger_duration_ms = elapsed;

                    ESP_LOGW(TAG, "SOS triggered! Hold: %lu ms", elapsed);

                    // Vibrate
                    // We release mutex before blocking vibrate, then re-acquire
                    xSemaphoreGive(s_sos.mutex);
                    sos_vibrate_feedback(SOS_VIBRATE_MS);
                    // Callback
                    if (s_sos.sos_cb) {
                        s_sos.sos_cb(&s_sos.last_event, s_sos.user_data);
                    }
                    return; // Already gave mutex
                }
                break;
            }

            case SOS_COOLDOWN: {
                // Debounce after release: 50 ms
                if ((now_ms - s_sos.last_debounce_ms) >= SOS_MAX_DEBOUNCE_MS) {
                    s_sos.state = SOS_IDLE;
                }
                break;
            }

            default:
                break;
        }

        xSemaphoreGive(s_sos.mutex);
    }
}
