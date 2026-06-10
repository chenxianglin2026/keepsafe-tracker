--[[
  config.lua -- KeepSafe EC618 Configuration (LuatOS)
  Ported from: code/firmware/main/config.h (ESP32-S3)
  Platform: Air780EG (EC618 core), LuatOS firmware
  Date: 2026-06-09
]]

-- ======================= Device Identity =======================
CONFIG = {}

CONFIG.DEVICE_ID       = "KS-XXXXXXXX"    -- {{PLACEHOLDER_DEVICE_ID}}
CONFIG.FIRMWARE_VERSION = "2.0.0"         -- EC618 firmware gen

-- ======================= MQTT Broker =======================
CONFIG.MQTT_HOST       = "43.163.5.90"    -- VPS EMQX
CONFIG.MQTT_PORT       = 1883
CONFIG.MQTT_KEEPALIVE  = 300              -- seconds
CONFIG.MQTT_CLEAN_SESSION = 1

-- QoS levels
CONFIG.MQTT_QOS_LOCATION    = 1
CONFIG.MQTT_QOS_HEARTBEAT   = 0
CONFIG.MQTT_QOS_SOS         = 1
CONFIG.MQTT_QOS_LOW_BATTERY = 1

-- Topic tree (prefixed with keepsafe/v1/{device_id}/)
CONFIG.TOPIC_LOCATION   = string.format("keepsafe/v1/%s/location", CONFIG.DEVICE_ID)
CONFIG.TOPIC_HEARTBEAT  = string.format("keepsafe/v1/%s/heartbeat", CONFIG.DEVICE_ID)
CONFIG.TOPIC_SOS        = string.format("keepsafe/v1/%s/sos", CONFIG.DEVICE_ID)
CONFIG.TOPIC_LOW_BATTERY = string.format("keepsafe/v1/%s/alert/low_battery", CONFIG.DEVICE_ID)

-- ======================= APN / PDP =======================
CONFIG.APN_NAME = "ctnet"          -- China Telecom APN (or cmnet for CMCC)
CONFIG.PDP_CID  = 1

-- ======================= PSM Power Saving =======================
-- Active Time (T3324): 10 seconds, TAU (T3412): 54 minutes
CONFIG.PSM_ACTIVE_TIMER = "00001000"   -- 10s
CONFIG.PSM_TAU_PERIOD   = "00000101"   -- 54min
CONFIG.PSM_MIN_ACTIVE_MS = 10000        -- minimum 10s awake after wake before sleep allowed

-- ======================= GPS / GNSS =======================
CONFIG.GPS_FIX_TIMEOUT_MS = 60000      -- max wait for 3D fix
CONFIG.GPS_TURN_ON_DELAY  = 2000       -- ms after AT+CGNSPWR=1

-- ======================= Dynamic Location Intervals =======================
CONFIG.INTERVAL_MOVING_MS     = 5 * 60 * 1000    -- 5 min moving
CONFIG.INTERVAL_STATIONARY_MS = 30 * 60 * 1000   -- 30 min stationary
CONFIG.INTERVAL_SOS_REPEAT_MS = 30 * 1000         -- 30 sec SOS repeat
CONFIG.INTERVAL_HEARTBEAT_MS  = 5 * 60 * 1000     -- 5 min heartbeat

-- ======================= Battery Thresholds =======================
CONFIG.BAT_VOLTAGE_FULL_MV  = 4200
CONFIG.BAT_VOLTAGE_EMPTY_MV = 3300
CONFIG.BAT_LOW_PERCENT      = 20

-- ======================= SOS =======================
CONFIG.SOS_LONG_PRESS_MS   = 3000      -- 3 second hold
CONFIG.SOS_VIBRATE_MS      = 200       -- motor feedback duration
CONFIG.SOS_MAX_DEBOUNCE_MS = 50

-- ======================= MQTT Reconnect Backoff =======================
CONFIG.RECONNECT_BASE_MS    = 1000     -- 1 second
CONFIG.RECONNECT_MAX_MS     = 300000   -- 5 minutes
CONFIG.RECONNECT_MULTIPLIER = 2        -- exponential: 1s, 2s, 4s, 8s...
CONFIG.RECONNECT_MAX_FAILURES = 10     -- circuit breaker: max consecutive failures

-- ======================= Network Monitoring =======================
CONFIG.NET_CHECK_INTERVAL_MS = 30000   -- 30 seconds between network status checks
CONFIG.NET_MAX_RECOVERY_ATTEMPTS = 5   -- max PDP re-activation attempts
CONFIG.NET_RECOVERY_DELAY_MS = 5000    -- 5 seconds between recovery attempts

-- ======================= LED Pulses =======================
CONFIG.LED_PULSE_DUTY_MS = 50          -- visibility pulse width
CONFIG.LED_PULSE_PERIOD_MS = 20000     -- 20ms period

-- ======================= GPIO Pins (Air780EG) =======================
-- TBD: mapped after Air780EG pinout confirmation
-- Air780EG typical GPIO mapping (LuatOS):
--   GPIO 4  -> I2C SDA (LIS3DH)
--   GPIO 5  -> I2C SCL (LIS3DH)
--   GPIO 27 -> LED Blue
--   GPIO 28 -> LED Green
--   GPIO 29 -> LED Red
--   GPIO 8  -> SOS Button (input, pull-up)
--   GPIO 9  -> Vibration Motor
--   GPIO 10 -> Battery ADC
--   GPIO 6  -> LIS3DH INT1 (motion interrupt)
CONFIG.GPIO = {
    I2C_SDA  = 4,
    I2C_SCL  = 5,
    LED_BLUE  = 27,
    LED_GREEN = 28,
    LED_RED   = 29,
    SOS_BTN   = 8,
    VIBRATOR  = 9,
    BAT_ADC   = 10,
    ACCEL_INT1 = 6,
}

-- LIS3DH accelerometer address
CONFIG.LIS3DH_ADDR = 0x18              -- SDO/SA0 tied low

return CONFIG
