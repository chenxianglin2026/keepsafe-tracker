/*
 * accel.c — LIS3DH Accelerometer Driver Implementation
 *
 * I2C driver for LIS3DH ultra-low-power 3-axis accelerometer.
 *
 * Power path notes:
 *   - Low-power mode at 50 Hz ODR + all axes enabled: ~2 µA typical.
 *   - Power-down mode (sleep): <1 µA. Entered when device goes stationary.
 *   - Motion interrupt wakes ESP32-S3 from deep sleep via RTC_GPIO.
 *   - Normal mode (high-res): ~11 µA, only used during active GPS fix cycles.
 *
 * ESP-IDF I2C driver notes:
 *   - Uses ESP-IDF's I2C master driver in polled mode (no interrupts needed).
 *   - I2C clock stretching handled by hardware.
 *   - Single-byte register read/write uses I2C write-then-read combined transaction.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "accel.h"
#include "config.h"

static const char *TAG = "ACCEL";

/* ======================= Internal State ======================= */

static SemaphoreHandle_t s_accel_mutex = NULL;
static volatile bool s_motion_detected = false;
static accel_scale_t s_current_scale = ACCEL_SCALE_2G;
static bool s_initialized = false;

/* ======================= I2C Helper Functions ======================= */

/**
 * Write a single byte to a LIS3DH register.
 */
static esp_err_t accel_write_reg(uint8_t reg, uint8_t val)
{
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (LIS3DH_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_write_byte(cmd, val, true);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

/**
 * Read a single byte from a LIS3DH register.
 */
static esp_err_t accel_read_reg(uint8_t reg, uint8_t *val)
{
    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (LIS3DH_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (LIS3DH_ADDR << 1) | I2C_MASTER_READ, true);
    i2c_master_read_byte(cmd, val, I2C_MASTER_NACK);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

/**
 * Read multiple bytes from LIS3DH (auto-increment address).
 */
static esp_err_t accel_read_multi(uint8_t reg, uint8_t *buf, size_t len)
{
    if (len == 0) return ESP_OK;
    reg |= 0x80; // Set MSB for multiple-byte read (auto-increment)

    i2c_cmd_handle_t cmd = i2c_cmd_link_create();
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (LIS3DH_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_write_byte(cmd, reg, true);
    i2c_master_start(cmd);
    i2c_master_write_byte(cmd, (LIS3DH_ADDR << 1) | I2C_MASTER_READ, true);
    if (len > 1) {
        i2c_master_read(cmd, buf, len - 1, I2C_MASTER_ACK);
    }
    i2c_master_read_byte(cmd, buf + len - 1, I2C_MASTER_NACK);
    i2c_master_stop(cmd);
    esp_err_t ret = i2c_master_cmd_begin(I2C_MASTER_NUM, cmd, pdMS_TO_TICKS(100));
    i2c_cmd_link_delete(cmd);
    return ret;
}

/* ======================= Public API ======================= */

bool accel_init(void)
{
    if (s_initialized) return true;

    if (s_accel_mutex == NULL) {
        s_accel_mutex = xSemaphoreCreateMutex();
    }

    // Verify device identity
    uint8_t whoami = 0;
    esp_err_t ret = accel_read_reg(LIS3DH_REG_WHO_AM_I, &whoami);
    if (ret != ESP_OK || whoami != 0x33) {
        ESP_LOGE(TAG, "LIS3DH not found! WHO_AM_I=0x%02X (expected 0x33), ret=%d", whoami, ret);
        return false;
    }
    ESP_LOGI(TAG, "LIS3DH detected, WHO_AM_I=0x%02X", whoami);

    // Reset device
    accel_reset();
    vTaskDelay(pdMS_TO_TICKS(10));

    // CTRL1: ODR=50Hz (0111), LPen=1 (low-power), all axes enabled
    // 0111 0 111 => 0x77
    // Bit 7: 0 (not low-power mode enable bit; that's CTRL4)
    // Bits 7-4: ODR=0111=50Hz
    // Bit 3: LPen=1 (low-power mode enable)
    // Bits 2-0: Z/Y/X enable = 111
    accel_write_reg(LIS3DH_REG_CTRL1, 0x77);

    // CTRL4: Full-scale ±2g (00), HR=0 (low-power mode), BDU=1
    // BDU (Block Data Update) ensures we don't read partial data
    // 0 0 0 0 0 0 1 0 => 0x08? No:
    // Bit 7: BDU=1? Actually BDU is bit 7 in CTRL4? Let me check:
    // CTRL4: BDU(7) | BLE(6) | FS1(5) | FS0(4) | HR(3) | 0 | ST2(1) | ST1(0)
    // BDU=1, FS=00 (±2g), HR=0 (LP), no self-test
    // => 1 0 0 0 0 0 0 0 = 0x80
    accel_write_reg(LIS3DH_REG_CTRL4, 0x80);

    // CTRL5: No FIFO, no interrupt latches
    accel_write_reg(LIS3DH_REG_CTRL5, 0x00);

    // Default to ±2g
    s_current_scale = ACCEL_SCALE_2G;

    s_initialized = true;
    ESP_LOGI(TAG, "LIS3DH initialized (LP mode, 50Hz, ±2g)");

    return true;
}

bool accel_configure_motion_interrupt(uint8_t threshold_mg, uint8_t duration_ms)
{
    if (!s_initialized) return false;

    // INT1_CFG: enable OR-combination of X/Y/Z high (movement)
    // Bit 7: AOI=0 (OR combination)
    // Bit 6: 6D=0 (not 6D orientation detection)
    // Bits 5-0: ZHIE(5) | ZLIE(4) | YHIE(3) | YLIE(2) | XHIE(1) | XLIE(0)
    // We want: ZHIE | YHIE | XHIE (movement on any axis above threshold)
    // => 0b00101010 = 0x2A
    accel_write_reg(LIS3DH_REG_INT1_CFG, 0x2A);

    // INT1_THS: threshold in multiples of FS/127
    // For ±2g, FS=2*2=4g range, 1 LSB = 4000/127 ≈ 31.5 mg
    // threshold_mg / 31.5 = register value
    uint8_t ths_val = (threshold_mg * 127) / (4000);
    if (ths_val < 1) ths_val = 1;
    if (ths_val > 127) ths_val = 127;
    accel_write_reg(LIS3DH_REG_INT1_THS, ths_val);
    ESP_LOGD(TAG, "Motion interrupt threshold: %d mg (reg=0x%02X)", threshold_mg, ths_val);

    // INT1_DURATION: minimum duration in 1/ODR samples
    // At 50Hz ODR, 1 sample = 20ms. duration_ms / 20 = register value
    uint8_t dur_val = (duration_ms * 50) / 1000;
    if (dur_val < 1) dur_val = 1;
    if (dur_val > 127) dur_val = 127;
    accel_write_reg(LIS3DH_REG_INT1_DURATION, dur_val);

    // CTRL3: Enable INT1 on interrupt pin
    // I1_IA1: bit 6
    // Also set I1_IA1 (bit 6) and I1_LIR1 (bit 4) for latched interrupt
    accel_write_reg(LIS3DH_REG_CTRL3, 0x40); // I1_IA1 = 1

    ESP_LOGI(TAG, "Motion interrupt configured: threshold=%d mg, duration=%d ms",
             threshold_mg, duration_ms);
    return true;
}

void accel_low_power_mode(void)
{
    if (!s_initialized) return;

    // Set ODR=1Hz LP mode: CTRL1 = 0001 0 111 = 0x17
    // ODR=0001=1Hz, LPen=1, all axes on
    accel_write_reg(LIS3DH_REG_CTRL1, 0x17);
    ESP_LOGI(TAG, "LIS3DH: low-power mode (1 Hz, ~2 µA)");
}

void accel_normal_mode(uint16_t odr_hz)
{
    if (!s_initialized) return;

    uint8_t odr_bits;
    switch (odr_hz) {
        case 1:     odr_bits = 0x10; break; // 0001
        case 10:    odr_bits = 0x20; break; // 0010
        case 25:    odr_bits = 0x30; break; // 0011
        case 50:    odr_bits = 0x70; break; // 0111
        case 100:   odr_bits = 0x80; break; // 1000
        case 200:   odr_bits = 0x90; break; // 1001
        case 400:   odr_bits = 0xA0; break; // 1010
        case 1344:  odr_bits = 0xB0; break; // 1011 (low-power)
        case 5376:  odr_bits = 0xC0; break; // 1100 (low-power)
        default:    odr_bits = 0x70; break; // default 50Hz
    }

    // Keep LPen=1 (low-power) for normal mode in our use case
    // If high-res needed, switch HR bit in CTRL4
    accel_write_reg(LIS3DH_REG_CTRL1, odr_bits | 0x07); // odds | LPen=0? Actually LPen=0 for normal
    // For low-power mode: odr_bits | 0x07 (LPen=1 gives low-power, LPen=0 gives normal)

    ESP_LOGI(TAG, "LIS3DH: normal mode (%d Hz)", odr_hz);
}

accel_data_t accel_read(void)
{
    accel_data_t data = {0};

    if (!s_initialized || !s_accel_mutex) return data;

    if (xSemaphoreTake(s_accel_mutex, pdMS_TO_TICKS(50))) {
        uint8_t buf[6] = {0};
        esp_err_t ret = accel_read_multi(LIS3DH_REG_OUT_X_L, buf, 6);
        if (ret == ESP_OK) {
            data.x = (int16_t)(buf[0] | (buf[1] << 8));
            data.y = (int16_t)(buf[2] | (buf[3] << 8));
            data.z = (int16_t)(buf[4] | (buf[5] << 8));

            // Convert to g based on scale
            float scale_factor;
            switch (s_current_scale) {
                case ACCEL_SCALE_2G:  scale_factor = 0.001f;  break; // 1 mg/LSB
                case ACCEL_SCALE_4G:  scale_factor = 0.002f;  break; // 2 mg/LSB
                case ACCEL_SCALE_8G:  scale_factor = 0.004f;  break; // 4 mg/LSB
                case ACCEL_SCALE_16G: scale_factor = 0.012f;  break; // 12 mg/LSB
                default: scale_factor = 0.001f; break;
            }

            data.x_g = (float)data.x * scale_factor;
            data.y_g = (float)data.y * scale_factor;
            data.z_g = (float)data.z * scale_factor;
        }
        data.motion_detected = s_motion_detected;
        xSemaphoreGive(s_accel_mutex);
    }

    return data;
}

uint8_t accel_get_int1_source(void)
{
    uint8_t src = 0xFF;
    if (s_initialized) {
        accel_read_reg(LIS3DH_REG_INT1_SRC, &src);
    }
    return src;
}

void accel_set_int1_mode(bool active_high, bool latch)
{
    if (!s_initialized) return;

    uint8_t ctrl3 = 0;
    accel_read_reg(LIS3DH_REG_CTRL3, &ctrl3);

    if (active_high) {
        ctrl3 |= 0x02; // I1_INT1 = active high (default)
    } else {
        ctrl3 &= ~0x02;
    }

    if (latch) {
        ctrl3 |= 0x40; // I1_IA1 = enable
        ctrl3 |= 0x10; // I1_LIR1 = latch
    }

    accel_write_reg(LIS3DH_REG_CTRL3, ctrl3);
}

void accel_reset(void)
{
    // Reboot memory content
    uint8_t ctrl5 = 0;
    accel_read_reg(LIS3DH_REG_CTRL5, &ctrl5);
    accel_write_reg(LIS3DH_REG_CTRL5, ctrl5 | 0x80); // BOOT bit
    vTaskDelay(pdMS_TO_TICKS(5));
    accel_write_reg(LIS3DH_REG_CTRL5, ctrl5 & ~0x80);
    ESP_LOGI(TAG, "LIS3DH reset");
}

uint8_t accel_get_device_id(void)
{
    uint8_t id = 0;
    accel_read_reg(LIS3DH_REG_WHO_AM_I, &id);
    return id;
}

void accel_set_scale(accel_scale_t scale)
{
    if (!s_initialized) return;

    uint8_t ctrl4 = 0;
    accel_read_reg(LIS3DH_REG_CTRL4, &ctrl4);
    ctrl4 &= ~0x30;   // Clear FS bits
    ctrl4 |= (scale & 0x03) << 4; // Set FS bits
    accel_write_reg(LIS3DH_REG_CTRL4, ctrl4);
    s_current_scale = scale;
    ESP_LOGD(TAG, "LIS3DH scale set to ±%dg", (s_current_scale == 0) ? 2 : (s_current_scale == 1) ? 4 : (s_current_scale == 2) ? 8 : 16);
}

accel_scale_t accel_get_scale(void)
{
    return s_current_scale;
}

void accel_isr_handler(void)
{
    s_motion_detected = true;
    // The INT1_SRC register will be read later in interrupt context
    // to clear the latch. We set a flag here for the main loop.
}

bool accel_was_motion_detected(void)
{
    bool detected = false;
    if (s_accel_mutex && xSemaphoreTake(s_accel_mutex, pdMS_TO_TICKS(10))) {
        detected = s_motion_detected;
        s_motion_detected = false; // Clear flag
        xSemaphoreGive(s_accel_mutex);
    }
    return detected;
}
