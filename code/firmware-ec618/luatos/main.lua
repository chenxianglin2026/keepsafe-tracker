--[[
  main.lua -- KeepSafe 防丢器固件主入口 (LuatOS-SoC)
  Platform: 合宙 Air780EG (EC618 内核), LuatOS-SoC
  Date: 2026-06-13

  Architecture:
    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  accel   │   │   gps    │   │ battery  │   │   led    │
    │ LIS3DH   │   │  GNSS    │   │  ADC0    │   │ GPIO24/27│
    └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │              │
         └──────────────┼──────────────┼──────────────┘
                        │              │
                   ┌────┴──────────────┴─────┐
                   │       main.lua          │
                   │    State Machine        │
                   └────────────┬────────────┘
                                │
                   ┌────────────┴────────────┐
                   │         mqtt            │
                   │    EMQX @ VPS:1883      │
                   └─────────────────────────┘
                                │
                   ┌────────────┴────────────┐
                   │         psm             │
                   │  Deep Sleep <20µA       │
                   └─────────────────────────┘

  State Machine:
    INIT → STATIONARY ←→ MOVING
              ↓              ↓
           JUST_STOPPED  SOS_ACTIVE (from any state)

  Power strategy:
    - STATIONARY: PSM deep sleep between 30min reports
    - MOVING: 5min reports, no sleep
    - SOS_ACTIVE: 30s reports, no sleep, full brightness
]]

-- Load modules
local CONFIG  = require("config")
local GPS     = require("gps")
local MQTT    = require("mqtt")
local PSM     = require("psm")
local ACCEL   = require("accel")
local BATTERY = require("battery")
local LED     = require("led")

-- ======================= State Machine =======================

local STATE = {
    INIT         = -1,
    STATIONARY   = 0,
    MOVING       = 1,
    JUST_STOPPED = 2,
    SOS_ACTIVE   = 3,
}

local STATE_NAMES = {
    [STATE.INIT]         = "INIT",
    [STATE.STATIONARY]   = "STATIONARY",
    [STATE.MOVING]       = "MOVING",
    [STATE.JUST_STOPPED] = "JUST_STOPPED",
    [STATE.SOS_ACTIVE]   = "SOS_ACTIVE",
}

local current_state = STATE.INIT

-- ======================= Timers =======================

local report_timer      = nil
local heartbeat_timer   = nil
local sos_repeat_timer  = nil
local net_check_timer   = nil
local mqtt_tick_timer   = nil
local psm_tick_timer    = nil
local battery_timer     = nil
local accel_check_timer = nil

-- ======================= Network Monitoring =======================

local net_recovery_attempts = 0
local net_was_down = false
local last_net_check = 0

local function check_network_status()
    -- Check 4G network registration via AT+CEREG?
    -- EC618 returns +CEREG: 0,1 (registered) or 0,5 (registered, roaming)
    -- Simplified: rely on mobile.simid() and socket connectivity
    if mobile and mobile.status then
        local status = mobile.status()
        return status == 1  -- 1 = registered
    end
    -- Fallback: assume OK if we can reach this point
    return true
end

local function recover_network()
    log.warn("NET", "Attempting network recovery (" ..
        (net_recovery_attempts + 1) .. "/" .. CONFIG.NET_MAX_RECOVERY_ATTEMPTS .. ")")

    -- Deactivate + reactivate PDP context
    if mobile and mobile.apn then
        pcall(function() mobile.apn(0, CONFIG.PDP_CID) end)  -- deactivate
        sys.wait(1000)
        pcall(function() mobile.apn(1, CONFIG.PDP_CID, CONFIG.APN_NAME) end)  -- activate
    end

    -- Check if it worked
    local net_now = check_network_status()
    if net_now then
        net_recovery_attempts = 0
        net_was_down = false
        log.info("NET", "Recovery SUCCESS. Triggering MQTT reconnect...")
        MQTT.force_reconnect()
        return true
    end

    net_recovery_attempts = net_recovery_attempts + 1
    if net_recovery_attempts >= CONFIG.NET_MAX_RECOVERY_ATTEMPTS then
        log.error("NET", "Recovery FAILED after " .. CONFIG.NET_MAX_RECOVERY_ATTEMPTS ..
            " attempts. Will retry at next check.")
        net_recovery_attempts = 0
    end
    return false
end

local function net_monitor_tick()
    local now = os.time()
    if now - last_net_check < math.floor(CONFIG.NET_CHECK_INTERVAL_MS / 1000) then
        return
    end
    last_net_check = now

    local net_ok = check_network_status()
    if not net_ok then
        if not net_was_down then
            log.warn("NET", "Network DOWN")
            net_was_down = true
            LED.net_off()
            MQTT.disconnect()
        end
        recover_network()
    else
        if net_was_down then
            log.info("NET", "Network UP")
            net_was_down = false
            net_recovery_attempts = 0
            LED.net_connected()
            MQTT.force_reconnect()
        end
    end
end

-- ======================= System Watchdog =======================

local watchdog_last_feed = 0

local function system_watchdog()
    -- If no successful MQTT publish in 30 min, reboot
    local now = os.time()
    if now - watchdog_last_feed > 1800 then
        log.warn("SYS", "Watchdog timeout! Last feed: " .. (now - watchdog_last_feed) .. "s ago")
        -- On Air780EG: rtos.reboot() or pm.reboot()
        if rtos and rtos.reboot then
            log.error("SYS", "Rebooting via watchdog...")
            sys.wait(1000)
            rtos.reboot()
        end
    end
end

function feed_watchdog()
    watchdog_last_feed = os.time()
end

-- ======================= MQTT Callbacks =======================

local function on_mqtt_connected()
    log.info("KEEPSAFE", "MQTT connected → starting reporting")
    PSM.clear_guard("mqtt_publishing")
    LED.status_solid()
    LED.net_connected()
    start_reporting()
end

local function on_mqtt_disconnected()
    log.info("KEEPSAFE", "MQTT disconnected → pausing reporting")
    LED.net_connecting()
    stop_reporting()
end

local function on_network_down()
    log.warn("KEEPSAFE", "Network down → pausing")
    PSM.set_guard("network_recovery")
    LED.net_off()
    stop_reporting()
end

-- ======================= Motion Callback =======================

local function on_motion()
    local now = os.time()
    if current_state == STATE.STATIONARY or current_state == STATE.JUST_STOPPED then
        log.info("KEEPSAFE", "Motion detected → MOVING")
        change_state(STATE.MOVING)
    elseif current_state == STATE.MOVING then
        -- Already moving, just refresh timestamp
        ACCEL.last_motion_time = now
    end
end

-- ======================= State Transitions =======================

function change_state(new_state)
    if new_state == current_state then return end
    
    local old_name = STATE_NAMES[current_state] or "?"
    local new_name = STATE_NAMES[new_state] or "?"
    log.info("KEEPSAFE", string.format("State: %s → %s", old_name, new_name))
    
    current_state = new_state
    
    -- Update reporting interval
    schedule_location_report()
    
    -- Update LED
    if new_state == STATE.SOS_ACTIVE then
        LED.status_fast_blink()
    elseif new_state == STATE.MOVING then
        LED.status_slow_blink()
    else
        LED.status_pulse()  -- battery-saving visibility
    end
end

-- ======================= Reporting =======================

local function start_reporting()
    stop_reporting()

    -- Heartbeat timer
    heartbeat_timer = sys.timerStart(function()
        if MQTT.is_ready() then
            local payload = build_heartbeat_json()
            MQTT.publish_heartbeat(payload)
            feed_watchdog()
        end
    end, CONFIG.INTERVAL_HEARTBEAT_MS, true)

    -- Location report timer (dynamic interval)
    schedule_location_report()

    log.info("KEEPSAFE", string.format("Reporting started: heartbeat=%ds",
        CONFIG.INTERVAL_HEARTBEAT_MS / 1000))
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

function schedule_location_report()
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
        if not MQTT.is_ready() then
            schedule_location_report()
            return
        end

        -- Read sensors
        GPS.poll()
        BATTERY.read()

        -- Report location if GPS fix valid
        if GPS.has_valid_fix() then
            local payload = build_location_json()
            MQTT.publish_location(payload)
            feed_watchdog()
        end

        -- Report low battery
        if BATTERY.is_low() then
            local payload = build_low_battery_json()
            MQTT.publish_low_battery(payload)
        end

        -- Check for motion state transitions
        if ACCEL.has_motion() and current_state ~= STATE.MOVING then
            on_motion()
        end

        -- Idle check: if MOVING but no motion for 5 min → JUST_STOPPED
        if current_state == STATE.MOVING then
            local idle_time = os.time() - ACCEL.last_motion()
            if idle_time > 300 then  -- 5 min
                change_state(STATE.JUST_STOPPED)
                -- After one cycle in JUST_STOPPED → STATIONARY
                sys.timerStart(function()
                    if current_state == STATE.JUST_STOPPED then
                        change_state(STATE.STATIONARY)
                    end
                end, interval)
            end
        end

        schedule_location_report()  -- re-schedule
    end, interval)
end

-- ======================= SOS Handler =======================

function trigger_sos()
    if current_state == STATE.SOS_ACTIVE then return end

    log.warn("SOS", "SOS TRIGGERED!")
    change_state(STATE.SOS_ACTIVE)
    PSM.set_guard("sos_active")

    -- Wake from PSM if sleeping
    PSM.wake_from_sleep("gpio")

    -- Immediate publish
    GPS.poll()
    sys.wait(2000)  -- wait for GPS fix
    if MQTT.is_ready() then
        local payload = build_sos_json()
        MQTT.publish_sos(payload)
        feed_watchdog()
    end

    -- Vibrate feedback
    if gpio and CONFIG.GPIO.VIBRATOR then
        gpio.setup(CONFIG.GPIO.VIBRATOR, 1, gpio.OUTPUT)
        sys.timerStart(function()
            gpio.setup(CONFIG.GPIO.VIBRATOR, 0, gpio.OUTPUT)
        end, CONFIG.SOS_VIBRATE_MS)
    end

    -- Repeat SOS every 30s
    if sos_repeat_timer then
        sys.timerStop(sos_repeat_timer)
    end
    sos_repeat_timer = sys.timerStart(function()
        if MQTT.is_ready() then
            GPS.poll()
            local payload = build_sos_json()
            MQTT.publish_sos(payload)
            feed_watchdog()
        end
    end, CONFIG.INTERVAL_SOS_REPEAT_MS, true)

    schedule_location_report()
end

function cancel_sos()
    if current_state ~= STATE.SOS_ACTIVE then return end

    log.info("SOS", "SOS cancelled")
    change_state(STATE.STATIONARY)
    PSM.clear_guard("sos_active")

    if sos_repeat_timer then
        sys.timerStop(sos_repeat_timer)
        sos_repeat_timer = nil
    end
    schedule_location_report()
end

-- ======================= SOS Button GPIO Handler =======================

local sos_press_start = 0
local sos_pressed = false

local function sos_btn_callback(val)
    if val == 0 then  -- pressed (active low with pull-up)
        if not sos_pressed then
            sos_pressed = true
            sos_press_start = os.time()
            log.info("SOS", "Button pressed...")
        end
    else  -- released
        if sos_pressed then
            sos_pressed = false
            local hold_time = (os.time() - sos_press_start) * 1000
            if hold_time >= CONFIG.SOS_LONG_PRESS_MS then
                trigger_sos()
            else
                log.info("SOS", "Short press ignored (" .. hold_time .. "ms)")
            end
        end
    end
end

-- ======================= JSON Builders =======================

local function build_location_json()
    local json = require("json")
    local gps = GPS.get_data()
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        lat = gps.latitude,
        lng = gps.longitude,
        alt = gps.altitude or 0,
        spd = gps.speed or 0,
        hdg = gps.heading or 0,
        sat = gps.satellites or 0,
        fix = gps.fix_type or 0,
        hdop = gps.hdop or 99.9,
        bat = BATTERY.get_percent(),
        state = STATE_NAMES[current_state],
    }
    return json.encode(data)
end

local function build_heartbeat_json()
    local json = require("json")
    local data = {
        device_id = CONFIG.DEVICE_ID,
        fw = CONFIG.FIRMWARE_VERSION,
        ts = os.time(),
        state = STATE_NAMES[current_state],
        bat = BATTERY.get_percent(),
        mqtt = MQTT.get_state_name(),
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
        bat = BATTERY.get_percent(),
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
        bat = BATTERY.get_percent(),
        voltage_mv = BATTERY.get_voltage_mv(),
        threshold = CONFIG.BAT_LOW_PERCENT,
    }
    return json.encode(data)
end

-- ======================= Main Loop =======================

local function main_loop()
    log.info("KEEPSAFE", "════════════════════════════════════")
    log.info("KEEPSAFE", "KeepSafe DTU v" .. CONFIG.FIRMWARE_VERSION)
    log.info("KEEPSAFE", "Device: " .. CONFIG.DEVICE_ID)
    log.info("KEEPSAFE", "Platform: Air780EG (EC618)")
    log.info("KEEPSAFE", "════════════════════════════════════")

    -- 1. Init LEDs
    LED.init()
    LED.status_slow_blink()  -- blinking = initializing
    LED.net_connecting()

    -- 2. Init battery
    BATTERY.init()

    -- 3. Init GPS (cold start, may take 1-2 min)
    log.info("KEEPSAFE", "Starting GNSS...")
    GPS.power_on()

    -- 4. Init accelerometer (motion detection)
    log.info("KEEPSAFE", "Initializing LIS3DH accelerometer...")
    local accel_ok = ACCEL.init(on_motion)
    if not accel_ok then
        log.warn("KEEPSAFE", "LIS3DH not available, motion detection disabled")
    end

    -- 5. Init SOS button
    if gpio then
        gpio.setup(CONFIG.GPIO.SOS_BTN, sos_btn_callback, gpio.INT, gpio.PULLUP)
        log.info("KEEPSAFE", "SOS button configured (GPIO" .. CONFIG.GPIO.SOS_BTN .. ")")
    end

    -- 6. Wait for network registration
    log.info("KEEPSAFE", "Waiting for network registration...")
    local net_wait_start = os.time()
    while not check_network_status() do
        if os.time() - net_wait_start > 60 then
            log.error("KEEPSAFE", "Network registration timeout. Will retry via monitor.")
            break
        end
        sys.wait(2000)
    end
    LED.net_connected()

    -- 7. Init MQTT
    log.info("KEEPSAFE", "Starting MQTT client...")
    MQTT.init(on_mqtt_connected, on_mqtt_disconnected, on_network_down)
    MQTT.connect()

    -- 8. Init PSM
    log.info("KEEPSAFE", "Configuring PSM power saving...")
    PSM.init()
    PSM.set_guard("init")  -- block sleep during init

    -- 9. Start periodic timers
    mqtt_tick_timer = sys.timerStart(function()
        MQTT.tick()
    end, 5000, true)  -- every 5s

    net_check_timer = sys.timerStart(function()
        net_monitor_tick()
    end, CONFIG.NET_CHECK_INTERVAL_MS, true)

    psm_tick_timer = sys.timerStart(function()
        PSM.tick()
        -- Dynamic timer adjustment
        local moving = (current_state == STATE.MOVING or current_state == STATE.SOS_ACTIVE)
        PSM.adjust_timers(BATTERY.get_percent(), moving)
    end, 30000, true)  -- every 30s

    battery_timer = sys.timerStart(function()
        BATTERY.read()
    end, 60000, true)  -- every 60s

    -- 10. Release init guard → allow PSM sleep
    sys.timerStart(function()
        PSM.clear_guard("init")
        log.info("KEEPSAFE", "Init complete. PSM sleep enabled.")
    end, 10000)  -- 10s delay for MQTT to connect

    -- 11. Transition to STATIONARY (initial state)
    change_state(STATE.STATIONARY)

    -- 12. Main event loop
    log.info("KEEPSAFE", "Entering main event loop")
    while true do
        system_watchdog()
        sys.wait(1000)  -- 1s tick
    end
end

-- ======================= Boot =======================

sys.taskInit(main_loop)
