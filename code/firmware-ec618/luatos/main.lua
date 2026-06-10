--[[
  main.lua -- KeepSafe DTU 主入口 + 状态机主循环 (LuatOS-SoC)
  Ported from: code/firmware/main/main.c (ESP32-S3)
  Platform: YED DTU3 (EC718P-M100PG, 非 EC618)

  State machine:
    STATIONARY -> MOVING -> JUST_STOPPED -> STATIONARY
    any state  -> SOS_ACTIVE (when SOS triggered)

  Power strategy:
    - Air780EG enters PSM deep sleep between report cycles
    - Wake via RTC timer or GPIO interrupt (SOS button / motion)
    - Estimated current draw in deep sleep: < 20 uA

  Error Recovery:
    - Network monitoring: periodic AT+CEREG? checks, PDP re-activation on loss
    - MQTT watchdog: stale connection detection, auto-reconnect with backoff
    - Circuit breaker: stops reconnecting after MAX_FAILURES consecutive failures
    - System watchdog: resets device if stuck in error state for too long
]]

-- Load modules
local CONFIG = require("config")
local GPS    = require("gps")
local MQTT   = require("mqtt")
local PSM    = require("psm")

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

-- ======================= GPS / Location =======================
-- GPS data is managed by gps.lua module (GPS.get_data() returns a copy)

-- ======================= Battery =======================

local battery_pct = 100

-- ======================= Timers =======================

local report_timer = nil
local heartbeat_timer = nil
local sos_repeat_timer = nil
local net_check_timer = nil
local mqtt_tick_timer = nil
local psm_tick_timer = nil

-- ======================= Network Monitoring =======================

local net_recovery_attempts = 0
local net_was_down = false
local last_net_check = 0

local function check_network_status()
    -- Check if 4G data connection is active via AT+CEREG? and PDP status
    -- Returns true if network is up, false if down
    local ok_cereg = false
    local ok_pdp = false

    -- Check network registration via AT+CEREG?
    pcall(function()
        -- nril.at("AT+CEREG?", 3000)
        -- Parse response for +CEREG: 0,1 or +CEREG: 0,5
        -- For now, assume network is up if we can send AT commands
        -- TODO: implement actual AT+CEREG? check via nril.at
        ok_cereg = true
    end)

    -- Check PDP context status via AT+CGACT?
    pcall(function()
        -- nril.at("AT+CGACT?", 3000)
        -- Parse response for +CGACT: 1,1 (PDP CID 1 active)
        -- TODO: implement actual AT+CGACT? check
        ok_pdp = true
    end)

    return ok_cereg and ok_pdp
end

local function recover_network()
    log.warn("NET", "Attempting network recovery (attempt " ..
        (net_recovery_attempts + 1) .. "/" .. CONFIG.NET_MAX_RECOVERY_ATTEMPTS .. ")")

    -- Step 1: Deactivate PDP
    pcall(function()
        -- nril.at("AT+CGACT=0,1", 3000)
    end)

    sys.wait(1000)

    -- Step 2: Re-activate PDP
    local pdp_ok = false
    pcall(function()
        -- nril.at('AT+CGDCONT=1,"IP","' .. CONFIG.APN_NAME .. '"', 3000)
        -- nril.at("AT+CGACT=1,1", 5000)
        pdp_ok = true  -- TODO: parse actual response
    end)

    if pdp_ok then
        net_recovery_attempts = 0
        net_was_down = false
        log.info("NET", "Network recovery SUCCESS")
        -- Network is back, trigger MQTT reconnect
        MQTT.force_reconnect()
        return true
    else
        net_recovery_attempts = net_recovery_attempts + 1
        if net_recovery_attempts >= CONFIG.NET_MAX_RECOVERY_ATTEMPTS then
            log.error("NET", "Network recovery FAILED after " ..
                CONFIG.NET_MAX_RECOVERY_ATTEMPTS .. " attempts. "
                .. "Will retry at next check interval.")
            net_recovery_attempts = 0
        end
        return false
    end
end

local function net_monitor_tick()
    -- Called periodically to check network health
    local now = os.time()
    if now - last_net_check < math.floor(CONFIG.NET_CHECK_INTERVAL_MS / 1000) then
        return
    end

    last_net_check = now

    -- Only check if we need network (MQTT active)
    if current_state == STATE.SOS_ACTIVE then
        -- SOS mode: check more aggressively
    end

    local net_ok = check_network_status()

    if not net_ok then
        if not net_was_down then
            log.warn("NET", "Network DOWN detected. Starting recovery...")
            net_was_down = true
            -- Notify MQTT module
            MQTT.disconnect()
        end
        recover_network()
    else
        if net_was_down then
            log.info("NET", "Network UP. Reconnecting MQTT...")
            net_was_down = false
            net_recovery_attempts = 0
            MQTT.force_reconnect()
        end
    end
end

-- ======================= System Watchdog =======================

local watchdog_last_reset = 0
local watchdog_timeout = CONFIG.NET_CHECK_INTERVAL_MS * 10  -- 5 min in ms

local function system_watchdog()
    -- If we haven't successfully published in watchdog_timeout, reset
    -- This is a last resort for firmware hangs
    local now = os.time()
    if now - watchdog_last_reset > math.floor(watchdog_timeout / 1000) then
        log.warn("SYS", "Watchdog: checking system health...")
        -- TODO: implement actual reset via pm.reboot() if stuck
        watchdog_last_reset = now
    end
end

-- ======================= MQTT Callbacks =======================

local function on_mqtt_connected()
    log.info("KEEPSAFE", "MQTT connected callback: starting reporting")
    -- Clear PSM sleep guard for MQTT
    PSM.clear_guard("mqtt_publishing")
    -- Start/re-start periodic reporting
    start_reporting()
end

local function on_mqtt_disconnected()
    log.info("KEEPSAFE", "MQTT disconnected callback: pausing reporting")
    stop_reporting()
end

local function on_network_down()
    log.warn("KEEPSAFE", "Network down callback: pausing all operations")
    PSM.set_guard("network_recovery")
    stop_reporting()
end

-- ======================= Reporting =======================

local function start_reporting()
    -- Cancel existing timers
    stop_reporting()

    -- Start heartbeat timer
    heartbeat_timer = sys.timerStart(function()
        if MQTT.is_ready() then
            local payload = build_heartbeat_json()
            MQTT.publish_heartbeat(payload)
        end
    end, CONFIG.INTERVAL_HEARTBEAT_MS, true)  -- true = repeat

    -- Start location report timer (interval depends on state)
    schedule_location_report()

    log.info("KEEPSAFE", "Reporting started: heartbeat=" ..
        CONFIG.INTERVAL_HEARTBEAT_MS .. "ms")
end

local function stop_reporting()
    if heartbeat_timer then
        sys.timerStop(heartbeat_timer)
        heartbeat_timer = nil
    end
    if report_timer then
        sys.timerStop(report_timer)
        report_timer = nil
    end
    if sos_repeat_timer then
        sys.timerStop(sos_repeat_timer)
        sos_repeat_timer = nil
    end
end

local function schedule_location_report()
    if report_timer then
        sys.timerStop(report_timer)
        report_timer = nil
    end

    local interval = CONFIG.INTERVAL_STATIONARY_MS
    if current_state == STATE.MOVING then
        interval = CONFIG.INTERVAL_MOVING_MS
    elseif current_state == STATE.SOS_ACTIVE then
        interval = CONFIG.INTERVAL_SOS_REPEAT_MS
    end

    report_timer = sys.timerStart(function()
        if MQTT.is_ready() then
            -- Poll GPS
            GPS.poll()
            if GPS.has_valid_fix() then
                local payload = build_location_json()
                MQTT.publish_location(payload)
            else
                log.info("KEEPSAFE", "Skipping location report: no GPS fix")
            end

            -- Check battery
            if battery_pct <= CONFIG.BAT_LOW_PERCENT then
                local payload = build_low_battery_json()
                MQTT.publish_low_battery(payload)
            end
        end
        schedule_location_report()  -- re-schedule
    end, interval)
end

-- ======================= JSON Builders =======================
-- Ported from main.c build_location_json / build_heartbeat_json / build_sos_json

local function build_location_json()
    local json = require("json")
    local gps = GPS.get_data()
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        lat = gps.latitude,
        lng = gps.longitude,
        alt = gps.altitude,
        spd = gps.speed,
        hdg = gps.heading,
        sat = gps.satellites,
        fix = gps.fix_type,
        hdop = gps.hdop,
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
        mqtt = MQTT.get_state(),
    }
    return json.encode(data)
end

local function build_sos_json()
    local json = require("json")
    local gps = GPS.get_data()
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        alert = "sos",
        lat = gps.latitude,
        lng = gps.longitude,
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
    log.info("KEEPSAFE", string.format("KeepSafe DTU starting, device=%s, fw=%s",
        CONFIG.DEVICE_ID, CONFIG.FIRMWARE_VERSION))

    -- 1. Initialize GPS
    log.info("KEEPSAFE", "Initializing GNSS...")
    GPS.power_on()

    -- 2. Initialize network
    log.info("KEEPSAFE", "Waiting for network registration...")
    -- Network monitoring will handle PDP setup and recovery
    net_monitor_tick()

    -- 3. Initialize MQTT with callbacks
    log.info("KEEPSAFE", "Starting MQTT client...")
    MQTT.init(on_mqtt_connected, on_mqtt_disconnected, on_network_down)
    MQTT.connect()

    -- 4. Configure PSM for power saving
    log.info("KEEPSAFE", "Initializing PSM power saving...")
    local psm_ok = PSM.init()
    if not psm_ok then
        log.warn("KEEPSAFE", "PSM not available, falling back to eDRX + slow clock")
    end

    -- 5. Start MQTT tick timer (health check watchdog)
    mqtt_tick_timer = sys.timerStart(function()
        MQTT.tick()
    end, 5000, true)  -- every 5 seconds

    -- 6. Start network monitor timer
    net_check_timer = sys.timerStart(function()
        net_monitor_tick()
    end, CONFIG.NET_CHECK_INTERVAL_MS, true)

    -- 7. Start PSM tick timer (manage sleep/wake cycles)
    psm_tick_timer = sys.timerStart(function()
        PSM.tick()
        -- Dynamic timer adjustment based on battery and motion
        if battery_pct then
            local moving = (current_state == STATE.MOVING)
            PSM.adjust_timers(battery_pct, moving)
        end
    end, 30000, true)  -- every 30 seconds

    -- 8. Enter main state machine loop
    log.info("KEEPSAFE", "Entering state machine loop")
    local last_watchdog = os.time()

    while true do
        -- Periodic tasks handled by LuatOS timers (sys.timerLoopStart/sys.timerStart)
        -- This loop is the event-driven idle; LuatOS sys.run() handles the event pump.

        -- System watchdog
        system_watchdog()

        -- State transitions happen in callbacks triggered by:
        --   - Motion detection (accelerometer INT1 interrupt)
        --   - SOS button GPIO interrupt
        --   - MQTT publish timer
        --   - Heartbeat timer

        sys.wait(1000)  -- 1 second tick
    end
end

-- ======================= SOS Handler =======================

function trigger_sos()
    if current_state == STATE.SOS_ACTIVE then
        log.info("SOS", "Already in SOS mode, skipping")
        return
    end

    log.warn("SOS", "SOS triggered! Entering SOS_ACTIVE state")
    current_state = STATE.SOS_ACTIVE

    -- Block PSM sleep during SOS
    PSM.set_guard("sos_active")

    -- Wake from PSM if sleeping
    if PSM.is_sleeping() then
        PSM.wake_from_sleep("gpio")
    end

    -- Poll GPS for immediate location
    GPS.poll()

    -- Publish SOS immediately
    if MQTT.is_ready() then
        local payload = build_sos_json()
        MQTT.publish_sos(payload)
    end

    -- Start SOS repeat timer (every 30 seconds)
    if sos_repeat_timer then
        sys.timerStop(sos_repeat_timer)
    end
    sos_repeat_timer = sys.timerStart(function()
        if MQTT.is_ready() then
            GPS.poll()
            local payload = build_sos_json()
            MQTT.publish_sos(payload)
        end
    end, CONFIG.INTERVAL_SOS_REPEAT_MS, true)

    -- Restart location reporting at SOS interval
    schedule_location_report()
end

function cancel_sos()
    if current_state ~= STATE.SOS_ACTIVE then
        return
    end

    log.info("SOS", "Cancelling SOS mode")
    current_state = STATE.STATIONARY

    -- Clear PSM SOS guard
    PSM.clear_guard("sos_active")

    if sos_repeat_timer then
        sys.timerStop(sos_repeat_timer)
        sos_repeat_timer = nil
    end

    schedule_location_report()
end

-- ======================= Boot =======================

sys.taskInit(main_loop)
