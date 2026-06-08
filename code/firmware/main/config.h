#ifndef CONFIG_H
#define CONFIG_H

/*
 * config.h — KeepSafe Configuration (Placeholder-based)
 *
 * Replace all {{PLACEHOLDER_*}} with actual values before building.
 *
 * Hardware: ESP32-S3 + Air780E (4G+GNSS) + LIS3DH (Accelerometer)
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

/* ======================= Device Identity ======================= */

#define DEVICE_ID                   "KS-XXXXXXXX"       // {{PLACEHOLDER_DEVICE_ID}}
#define FIRMWARE_VERSION            "1.0.0"

/* ======================= UART Pin Definitions ======================= */

// UART0 — Console (USB JTAG, default)
// UART1 — Air780E (4G+GNSS module)
#define UART_AIR780E_NUM            UART_NUM_1
#define UART_AIR780E_TX_GPIO        GPIO_NUM_17         // ESP32-S3 TX -> Air780E RX
#define UART_AIR780E_RX_GPIO        GPIO_NUM_18         // ESP32-S3 RX <- Air780E TX
#define UART_AIR780E_BAUD           115200
#define UART_AIR780E_BUF_SIZE       (2 * 1024)
#define UART_AIR780E_TIMEOUT_MS     1000

/* ======================= I2C Pin Definitions (LIS3DH) ======================= */

#define I2C_MASTER_NUM              I2C_NUM_0
#define I2C_MASTER_SCL_GPIO         GPIO_NUM_8
#define I2C_MASTER_SDA_GPIO         GPIO_NUM_9
#define I2C_MASTER_FREQ_HZ          400000
#define LIS3DH_ADDR                 0x18                // SDO/SA0 tied low -> 0x18

/* ======================= Interrupt / GPIO Pins ======================= */

// LIS3DH INT1 — motion detection wake (connected to ESP32-S3 RTC_GPIO)
#define GPIO_LIS3DH_INT1            GPIO_NUM_6          // RTC_GPIO-capable for deep-sleep wake
// SOS button (external interrupt, also RTC_GPIO for wake-from-deep-sleep)
#define GPIO_SOS_BUTTON              GPIO_NUM_4
// Vibration motor feedback for SOS confirmation
#define GPIO_VIBRATOR                GPIO_NUM_5
// Battery ADC
#define GPIO_BAT_ADC                 GPIO_NUM_7          // ADC1_CHANNEL_6
// LED outputs (active high, use via led.c with PWM for pulsed operation)
#define GPIO_LED_BLUE                GPIO_NUM_10
#define GPIO_LED_GREEN               GPIO_NUM_11
#define GPIO_LED_RED                 GPIO_NUM_12

/* ======================= MQTT + Network Configuration ======================= */

// APN & PDP context (NB-IoT preferred for PSM, fallback to regular LTE)
#define APN_NAME                    "{{PLACEHOLDER_APN_NAME}}"   // e.g. "cmnbiot" (China Mobile NB-IoT)
#define PDP_CTX_ID                  1

// MQTT Broker
#define MQTT_BROKER_HOST            "43.163.5.90"  // VPS EMQX
#define MQTT_BROKER_PORT            1883
#define MQTT_CLIENT_ID              DEVICE_ID
#define MQTT_KEEPALIVE_S            300
#define MQTT_CLEAN_SESSION          1
// QoS: location/SOS/alert = 1, heartbeat = 0
#define MQTT_QOS_LOCATION           1
#define MQTT_QOS_HEARTBEAT          0
#define MQTT_QOS_SOS                1
#define MQTT_QOS_LOW_BATTERY        1

// Topic tree (prefixed with keepsafe/v1/{device_id}/...)
// Defined as macros — see mqtt.c for full topic string assembly
#define MQTT_TOPIC_LOCATION         "keepsafe/v1/" DEVICE_ID "/location"
#define MQTT_TOPIC_HEARTBEAT        "keepsafe/v1/" DEVICE_ID "/heartbeat"
#define MQTT_TOPIC_SOS              "keepsafe/v1/" DEVICE_ID "/sos"
#define MQTT_TOPIC_LOW_BATTERY      "keepsafe/v1/" DEVICE_ID "/alert/low_battery"

/* ======================= PSM (Power Saving Mode) ======================= */

/*
 * PSM Configuration:
 *   AT+CPSMS=1,,,"00001000","00000101"
 *   - Active Time (T3324): 10 seconds = "00001000" (binary coded)
 *   - TAU period (T3412):  54 minutes  = "00000101" (binary coded)
 *
 * NOTE on operator compatibility:
 *   - PSM is an optional 3GPP Release 12 feature.
 *   - Supported by: China Mobile NB-IoT, Vodafone, Deutsche Telekom, T-Mobile US, etc.
 *   - NOT supported by: many LTE-only networks (e.g., Verizon LTE at time of writing).
 *   - On networks without PSM, the modem will ignore the request and stay in
 *     regular idle mode. The firmware will still function normally, just with
 *     higher average current draw (~0.4–1 mA instead of ~15 µA in PSM).
 *   - With PSM enabled, the device will be unreachable during deep-sleep periods.
 *     MQTT messages buffered in modem will be sent on next wake cycle.
 */

#define PSM_ACTIVE_TIMER            "00001000"          // T3324: 10 seconds
#define PSM_TAU_PERIOD              "00000101"          // T3412: 54 minutes

/* ======================= GPS / GNSS Configuration ======================= */

// Cold start takes ~35s, hot/warm start after AGPS ~5-15s
#define GPS_AGPS_ENABLE             true                // Enable assisted GPS via Air780E
#define GPS_TURN_ON_DELAY_MS        2000                // Wait after AT+CGNSPWR=1
#define GPS_FIX_TIMEOUT_MS          60000               // Max wait for 3D fix before fallback to LBS

/* ======================= Dynamic Location Frequency ======================= */

// State machine intervals (milliseconds)
#define INTERVAL_MOVING_MS          (5 * 60 * 1000)     // 5 minutes while moving
#define INTERVAL_STATIONARY_MS      (30 * 60 * 1000)    // 30 minutes while stationary
#define INTERVAL_SOS_REPEAT_MS      (30 * 1000)         // 30 seconds SOS repeat (first 5 times)
#define INTERVAL_HEARTBEAT_MS       (5 * 60 * 1000)     // 5 minutes

/* ======================= Battery & Thresholds ======================= */

// ADC reference voltage (mV) for battery measurement
#define BAT_ADC_REF_MV              3300
// Voltage divider: assume R1=R2, so Vbat = ADC * 2
#define BAT_DIVIDER_RATIO           2.0f
// LiPo full charge: 4.2V, safe cutoff: 3.3V (under load)
#define BAT_VOLTAGE_FULL_MV         4200
#define BAT_VOLTAGE_EMPTY_MV        3300
// Low battery threshold
#define BAT_LOW_PERCENT             20

/* ======================= SOS ======================= */

#define SOS_LONG_PRESS_MS           3000                // 3-second hold to trigger
#define SOS_VIBRATE_MS              200                 // Motor feedback duration
#define SOS_MAX_DEBOUNCE_MS         50                  // Debounce interval

/* ======================= MQTT Exponential Backoff Reconnect ======================= */

#define RECONNECT_BASE_MS           1000                // 1 second
#define RECONNECT_MAX_MS            300000              // 5 minutes max
#define RECONNECT_MULTIPLIER        2                   // Exponential: 1s -> 2s -> 4s -> 8s -> 32s -> 300s

/* ======================= LED Pulse Parameters ======================= */

// LEDs are pulsed at low duty to save power (~5 mA * 50 ms sighting)
#define LED_PULSE_DUTY_US           50                  // Pulse width for visibility
#define LED_PULSE_PERIOD_US         20000               // 20 ms period (50 Hz)

/* ======================= Deep Sleep ======================= */

// ESP32-S3 deep sleep draws ~8 µA with RTC timer + GPIO wake sources
// Wake sources: RTC timer, GPIO (SOS button), GPIO (LIS3DH INT1 motion)
#define DEEP_SLEEP_WAKE_PINS_BITMASK \
    ((1ULL << GPIO_SOS_BUTTON) | (1ULL << GPIO_LIS3DH_INT1))

#endif /* CONFIG_H */
