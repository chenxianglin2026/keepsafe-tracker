--[[
  config.lua -- KeepSafe 防丢器配置 (LuatOS-SoC)
  Platform: 合宙 Air780EG (EC618 内核), LuatOS-SoC
  Date: 2026-06-13
]]

-- ======================= Device Identity =======================
CONFIG = {}

CONFIG.DEVICE_ID       = "KS-PROTO-001"    -- 原型机 #1. 量产用 IMEI
CONFIG.FIRMWARE_VERSION = "2.1.0"          -- EC618 LuatOS firmware

-- ======================= MQTT Broker =======================
CONFIG.MQTT_HOST       = "43.163.5.90"     -- VPS EMQX
CONFIG.MQTT_PORT       = 1883
CONFIG.MQTT_KEEPALIVE  = 300               -- seconds
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
CONFIG.APN_NAME = "ctnet"          -- China Telecom APN. 移动用 cmnet
CONFIG.PDP_CID  = 1

-- ======================= PSM Power Saving =======================
-- Active Time (T3324): 10 seconds, TAU (T3412): 54 minutes
CONFIG.PSM_ACTIVE_TIMER = "00000100"    -- 10s (bit-encoded)
CONFIG.PSM_TAU_PERIOD   = "00000101"    -- 54min (bit-encoded)
CONFIG.PSM_MIN_ACTIVE_MS = 10000         -- minimum 10s awake after wake

-- ======================= GPS / GNSS =======================
-- Air780EG 内置 GNSS (GPS+BDS+GLONASS), AT+CGNSPWR=1 开启
CONFIG.GPS_FIX_TIMEOUT_MS  = 120000     -- max 2min wait for first fix
CONFIG.GPS_HOT_START_MS    = 5000       -- hot start typically <5s
CONFIG.GPS_TURN_ON_DELAY_MS = 2000      -- ms after AT+CGNSPWR=1 before query

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
CONFIG.SOS_LONG_PRESS_MS   = 3000       -- 3 second hold
CONFIG.SOS_VIBRATE_MS      = 200        -- motor feedback duration
CONFIG.SOS_MAX_DEBOUNCE_MS = 50

-- ======================= MQTT Reconnect Backoff =======================
CONFIG.RECONNECT_BASE_MS    = 1000     -- 1 second
CONFIG.RECONNECT_MAX_MS     = 300000   -- 5 minutes
CONFIG.RECONNECT_MULTIPLIER = 2        -- exponential: 1s, 2s, 4s, 8s...
CONFIG.RECONNECT_MAX_FAILURES = 10     -- circuit breaker threshold

-- ======================= Network Monitoring =======================
CONFIG.NET_CHECK_INTERVAL_MS = 30000    -- 30 seconds between network checks
CONFIG.NET_MAX_RECOVERY_ATTEMPTS = 5    -- max PDP re-activation attempts
CONFIG.NET_RECOVERY_DELAY_MS = 5000     -- 5 seconds between recovery attempts

-- ======================= LED Pulses =======================
CONFIG.LED_PULSE_DUTY_MS   = 50        -- visibility pulse width
CONFIG.LED_PULSE_PERIOD_MS = 2000      -- 2s between pulses (visibility mode)

-- ======================= GPIO Pins (合宙 Air780EG 开发板) =======================
-- 基于合宙 Air780EG 开发板 V1.2 引脚定义:
--   详细: https://wiki.luatos.com/chips/air780eg/index.html
--
--   GPIO 1  -> LCD_DC / 通用 GPIO (板上丝印 GP1)
--   GPIO 4  -> I2C SDA (板上丝印 GP4)
--   GPIO 5  -> I2C SCL (板上丝印 GP5)
--   GPIO 8  -> 通用 GPIO (板上丝印 GP8)
--   GPIO 9  -> 通用 GPIO (板上丝印 GP9)
--   GPIO 10 -> ADC0 (板上丝印 ADC0, 0-1.2V 量程)
--   GPIO 11 -> ADC1 (板上丝印 ADC1)
--   GPIO 12 -> 通用 GPIO (板上丝印 GP12)
--   GPIO 13 -> 通用 GPIO (板上丝印 GP13)
--   GPIO 16 -> 通用 GPIO (板上丝印 GP16)
--   GPIO 17 -> 通用 GPIO (板上丝印 GP17)
--   GPIO 18 -> 通用 GPIO (板上丝印 GP18)
--   GPIO 19 -> I2S / 通用 GPIO
--   GPIO 23 -> UART2 TX (板上丝印 232)
--   GPIO 24 -> NET LED (板上丝印 NET)
--   GPIO 27 -> STATUS LED (板上丝印 STA)
--   GPIO 28 -> 通用 GPIO (板上丝印 GP28)
--   GPIO 29 -> 通用 GPIO (板上丝印 GP29)
--   GPIO 31 -> 通用 GPIO (板上丝印 GP31)
--   GPIO 32 -> 通用 GPIO (板上丝印 GP32)
--   GPIO 33 -> 通用 GPIO (板上丝印 GP33)
--   GPIO 34 -> 通用 GPIO (板上丝印 GP34)
--   GPIO 35 -> 通用 GPIO (板上丝印 GP35)
--
-- KeepSafe 分配:
CONFIG.GPIO = {
    I2C_SDA    = 4,     -- LIS3DH 加速度计 SDA
    I2C_SCL    = 5,     -- LIS3DH SCL
    LED_STATUS = 27,    -- STA LED (蓝色, 状态指示)
    LED_NET    = 24,    -- NET LED (绿色, 网络状态)
    SOS_BTN    = 8,     -- SOS 按键 (输入, 内部上拉)
    VIBRATOR   = 9,     -- 振动马达
    BAT_ADC    = 10,    -- 电池电压 (ADC0, 需分压: 4.2V→1.2V)
    ACCEL_INT1 = 12,    -- LIS3DH INT1 (运动唤醒)
    ACCEL_INT2 = 13,    -- LIS3DH INT2 (备用)
}

-- LIS3DH 加速度计 I2C 地址
CONFIG.LIS3DH_ADDR = 0x18              -- SDO/SA0 拉低

return CONFIG
