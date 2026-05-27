/*
 * accel.h — LIS3DH Accelerometer Driver Interface
 *
 * I2C-based driver for the ST LIS3DH ultra-low-power accelerometer.
 * Supports:
 *   - Low-power mode @ 2 µA (normal mode ~11 µA)
 *   - Wake-on-motion interrupt via INT1 pin
 *   - Free-fall / activity detection
 *   - Deep-sleep wake-up source for ESP32-S3
 *
 * Hardware: LIS3DH on I2C bus with INT1 connected to ESP32-S3 RTC_GPIO.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= LIS3DH Register Map ======================= */
#define LIS3DH_REG_WHO_AM_I         0x0F    // Should return 0x33
#define LIS3DH_REG_CTRL1            0x20    // ODR, LPen, Z/Y/X enable
#define LIS3DH_REG_CTRL2            0x21    // HPF settings
#define LIS3DH_REG_CTRL3            0x22    // Interrupt config
#define LIS3DH_REG_CTRL4            0x23    // Full-scale, HR, BDU
#define LIS3DH_REG_CTRL5            0x24    // FIFO, int latch
#define LIS3DH_REG_CTRL6            0x25    // INT2 config
#define LIS3DH_REG_STATUS           0x27
#define LIS3DH_REG_OUT_X_L          0x28
#define LIS3DH_REG_OUT_X_H          0x29
#define LIS3DH_REG_OUT_Y_L          0x2A
#define LIS3DH_REG_OUT_Y_H          0x2B
#define LIS3DH_REG_OUT_Z_L          0x2C
#define LIS3DH_REG_OUT_Z_H          0x2D
#define LIS3DH_REG_FIFO_CTRL        0x2E
#define LIS3DH_REG_FIFO_SRC         0x2F
#define LIS3DH_REG_INT1_CFG         0x30
#define LIS3DH_REG_INT1_SRC         0x31
#define LIS3DH_REG_INT1_THS         0x32
#define LIS3DH_REG_INT1_DURATION    0x33
#define LIS3DH_REG_CLICK_CFG        0x38
#define LIS3DH_REG_CLICK_SRC        0x39
#define LIS3DH_REG_CLICK_THS        0x3A
#define LIS3DH_REG_TIME_LIMIT       0x3B
#define LIS3DH_REG_TIME_LATENCY     0x3C
#define LIS3DH_REG_TIME_WINDOW      0x3D
#define LIS3DH_REG_ACT_THS          0x3E
#define LIS3DH_REG_ACT_DUR          0x3F

/* ======================= Accelerometer Data ======================= */
typedef struct {
    int16_t x;                  // Raw X-axis value (mg or LSB depending on range)
    int16_t y;                  // Raw Y-axis value
    int16_t z;                  // Raw Z-axis value
    float   x_g;                // X-axis in g
    float   y_g;                // Y-axis in g
    float   z_g;                // Z-axis in g
    bool    motion_detected;    // Set by ISR when INT1 triggers
} accel_data_t;

/* ======================= Full Scale ======================= */
typedef enum {
    ACCEL_SCALE_2G  = 0,    // ±2g  (1 mg/LSB)
    ACCEL_SCALE_4G  = 1,    // ±4g  (2 mg/LSB)
    ACCEL_SCALE_8G  = 2,    // ±8g  (4 mg/LSB)
    ACCEL_SCALE_16G = 3,    // ±16g (12 mg/LSB)
} accel_scale_t;

/* ======================= Public API ======================= */

/**
 * @brief Initialize LIS3DH over I2C.
 * Configures:
 *   - Low-power mode, 50 Hz ODR
 *   - ±2g full-scale
 *   - Interrupt on motion on INT1
 *
 * @return true if initialization and WHO_AM_I check succeeded.
 */
bool accel_init(void);

/**
 * @brief Configure motion detection interrupt.
 * Sets up INT1 to trigger when acceleration exceeds the threshold
 * on any axis.
 *
 * @param threshold_mg  Threshold in milligravities (1-127, typical: 50)
 * @param duration_ms   Minimum duration in ms (1-127, typical: 20)
 * @return true on success.
 */
bool accel_configure_motion_interrupt(uint8_t threshold_mg, uint8_t duration_ms);

/**
 * @brief Enter low-power mode (2 µA typical).
 * Sets ODR to 1 Hz LP mode with all axes enabled.
 */
void accel_low_power_mode(void);

/**
 * @brief Exit low-power mode, set normal operation.
 * @param odr_hz Output data rate in Hz (1, 10, 25, 50, 100, 200, 400, 1344, 5376)
 */
void accel_normal_mode(uint16_t odr_hz);

/**
 * @brief Read current acceleration values.
 * Returns X, Y, Z in raw LSB and in g.
 */
accel_data_t accel_read(void);

/**
 * @brief Get the INT1 source register to clear the interrupt.
 * @return 0xFF on error, otherwise INT1_SRC value.
 */
uint8_t accel_get_int1_source(void);

/**
 * @brief Set the INT1 interrupt polarity and latch.
 * @param active_high true = high on interrupt, false = open drain
 * @param latch      true = latch INT1 until source read, false = pulsed
 */
void accel_set_int1_mode(bool active_high, bool latch);

/**
 * @brief Software reset the LIS3DH (reboot memory content).
 */
void accel_reset(void);

/**
 * @brief Get the WHO_AM_I value (should be 0x33).
 */
uint8_t accel_get_device_id(void);

/**
 * @brief Set the full-scale range.
 */
void accel_set_scale(accel_scale_t scale);

/**
 * @brief Get current scale.
 */
accel_scale_t accel_get_scale(void);

/**
 * @brief Motion detection ISR callback — called from GPIO interrupt context.
 * Interrupt-safe, just sets a flag.
 */
void accel_isr_handler(void);

/**
 * @brief Check if motion was detected since last check.
 * Resets the flag.
 */
bool accel_was_motion_detected(void);

#ifdef __cplusplus
}
#endif
