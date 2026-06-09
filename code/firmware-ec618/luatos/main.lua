--[[
  main.lua -- KeepSafe EC618 主入口 + 状态机主循环 (LuatOS)
  Ported from: code/firmware/main/main.c (ESP32-S3)
  Platform: Air780EG (EC618 core)

  State machine:
    STATIONARY -> MOVING -> JUST_STOPPED -> STATIONARY
    any state  -> SOS_ACTIVE (when SOS triggered)

  Power strategy:
    - Air780EG enters PSM deep sleep between report cycles
    - Wake via RTC timer or GPIO interrupt (SOS button / motion)
    - Estimated current draw in deep sleep: < 20 uA
]]

-- Load modules
local CONFIG = require("config")

-- ======================= State Machine =======================

local STATE = {
    STATIONARY  = 0,
    MOVING      = 1,
    JUST_STOPPED = 2,
    SOS_ACTIVE  = 3,
}

local state_names = {
    [STATE.STATIONARY]  = "STATIONARY",
    [STATE.MOVING]      = "MOVING",
    [STATE.JUST_STOPPED] = "JUST_STOPPED",
    [STATE.SOS_ACTIVE]  = "SOS_ACTIVE",
}

local current_state = STATE.STATIONARY

-- ======================= MQTT State =======================

local MQTT_STATE = {
    DISCONNECTED = 0,
    CONNECTING   = 1,
    CONNECTED    = 2,
    ERROR        = 3,
}

local mqtt_state = MQTT_STATE.DISCONNECTED

-- ======================= GPS / Location =======================

local gps_data = {
    latitude   = 0.0,
    longitude  = 0.0,
    altitude   = 0.0,
    speed      = 0.0,
    heading    = 0.0,
    satellites = 0,
    has_fix    = false,
    fix_type   = 0,
    hdop       = 99.9,
}

-- ======================= Battery =======================

local battery_pct = 100

-- ======================= Timers =======================

local report_timer = nil
local heartbeat_timer = nil
local sos_repeat_timer = nil

-- ======================= JSON Builders =======================
-- Ported from main.c build_location_json / build_heartbeat_json / build_sos_json

local function build_location_json()
    local json = require("json")
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        lat = gps_data.latitude,
        lng = gps_data.longitude,
        alt = gps_data.altitude,
        spd = gps_data.speed,
        hdg = gps_data.heading,
        sat = gps_data.satellites,
        fix = gps_data.fix_type,
        hdop = gps_data.hdop,
        bat = battery_pct,
    }
    return json.encode(data)
end

local function build_heartbeat_json()
    local json = require("json")
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        state = state_names[current_state],
        bat = battery_pct,
        mqtt = mqtt_state,
    }
    return json.encode(data)
end

local function build_sos_json()
    local json = require("json")
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        alert = "sos",
        lat = gps_data.latitude,
        lng = gps_data.longitude,
        bat = battery_pct,
    }
    return json.encode(data)
end

local function build_low_battery_json()
    local json = require("json")
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        alert = "low_battery",
        bat = battery_pct,
        threshold = CONFIG.BAT_LOW_PERCENT,
    }
    return json.encode(data)
end

-- ======================= Main Loop =======================

local function main_loop()
    log.info("KEEPSAFE", string.format("KeepSafe EC618 starting, device=%s, fw=%s",
        CONFIG.DEVICE_ID, CONFIG.FIRMWARE_VERSION))

    -- 1. Initialize network
    --    AT+CGDCONT=1,"IP","ctnet"  (PDP context)
    --    AT+CGACT=1,1               (activate PDP)
    --    Wait for IP via AT+CGPADDR=1
    log.info("KEEPSAFE", "Waiting for network registration...")
    -- TODO: call network_init()

    -- 2. Configure PSM
    --    AT+CPSMS=1,,,\"00001000\",\"00000101\"
    log.info("KEEPSAFE", "Configuring PSM...")
    -- TODO: call psm_configure()

    -- 3. Start MQTT client
    log.info("KEEPSAFE", "Starting MQTT client...")
    -- TODO: call mqtt_connect()

    -- 4. Enter main state machine loop
    log.info("KEEPSAFE", "Entering state machine loop")
    while true do
        -- Periodic tasks handled by LuatOS timers (sys.timerLoopStart/sys.timerStart)
        -- This loop is the event-driven idle; LuatOS sys.run() handles the event pump.
        -- The actual state transitions happen in callbacks triggered by:
        --   - Motion detection (accelerometer INT1 interrupt)
        --   - SOS button GPIO interrupt
        --   - MQTT publish timer
        --   - Heartbeat timer

        sys.wait(1000)  -- 1 second tick
    end
end

-- ======================= Boot =======================

sys.taskInit(main_loop)
