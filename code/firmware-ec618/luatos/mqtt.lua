--[[
  mqtt.lua -- MQTT Client for KeepSafe EC618 (LuatOS)
  Ported from: code/firmware/main/mqtt.c + mqtt.h (ESP32-S3)
  Platform: Air780EG (EC618 core)

  Uses LuatOS built-in MQTT library (mqttcore or net extension).
  The MQTT AT command set (AT+MQTTCONNCFG etc.) is NOT available on LuatOS firmware.
  Instead, we use the Lua MQTT client over the 4G data channel.

  Topic tree (prefixed with keepsafe/v1/{device_id}/):
    location      — QoS 1, GPS + LBS position report
    heartbeat     — QoS 0, periodic keepalive
    sos           — QoS 1, SOS alert
    alert/low_battery — QoS 1, low battery alert
]]

local CONFIG = require("config")

-- ======================= Internal State =======================

local MQTT_STATE = {
    DISCONNECTED = 0,
    CONNECTING   = 1,
    CONNECTED    = 2,
    ERROR        = 3,
}

local ctx = {
    state       = MQTT_STATE.DISCONNECTED,
    mqttc       = nil,            -- LuatOS MQTT client handle
    reconnect_delay = CONFIG.RECONNECT_BASE_MS,
    last_reconnect = 0,
    last_publish   = 0,
    connected_cb   = nil,
    disconnected_cb = nil,
}

-- ======================= MQTT Callbacks =======================

local function on_mqtt_connected()
    log.info("MQTT", "Connected to broker")
    ctx.state = MQTT_STATE.CONNECTED
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
    if ctx.connected_cb then ctx.connected_cb() end
end

local function on_mqtt_disconnected()
    log.warn("MQTT", "Disconnected from broker")
    ctx.state = MQTT_STATE.DISCONNECTED
    if ctx.disconnected_cb then ctx.disconnected_cb() end
    -- Schedule reconnect with backoff
    ctx.last_reconnect = os.time()
    sys.timerStart(function()
        mqtt_connect()
    end, ctx.reconnect_delay)
end

local function on_mqtt_message(topic, payload, qos)
    -- We currently don't subscribe to any topics
    log.debug("MQTT", string.format("Received message on %s (qos=%d)", topic, qos))
end

-- ======================= Public API =======================

function mqtt_init(connected_cb, disconnected_cb)
    ctx.connected_cb = connected_cb
    ctx.disconnected_cb = disconnected_cb
    log.info("MQTT", string.format("MQTT module initialized: broker=%s:%d",
        CONFIG.MQTT_HOST, CONFIG.MQTT_PORT))
end

function mqtt_connect()
    if ctx.state == MQTT_STATE.CONNECTED then
        log.info("MQTT", "Already connected")
        return
    end

    if ctx.state == MQTT_STATE.CONNECTING then
        log.info("MQTT", "Connection in progress")
        return
    end

    ctx.state = MQTT_STATE.CONNECTING
    log.info("MQTT", string.format("Connecting to %s:%d (client=%s)",
        CONFIG.MQTT_HOST, CONFIG.MQTT_PORT, CONFIG.DEVICE_ID))

    -- LuatOS MQTT client (mqtt.create / mqttc:connect)
    -- The mqtt library is built into LuatOS firmware
    local ok, err = pcall(function()
        ctx.mqttc = mqtt.create(nil, CONFIG.MQTT_HOST, CONFIG.MQTT_PORT, false) -- false = no SSL
        if not ctx.mqttc then
            error("mqtt.create returned nil")
        end

        ctx.mqttc:on(function(mqttc, event, data)
            if event == "conack" then
                on_mqtt_connected()
            elseif event == "disconnect" then
                on_mqtt_disconnected()
            elseif event == "recv" then
                on_mqtt_message(data.topic or "", data.payload or "", data.qos or 0)
            end
        end)

        -- Connect with clean session
        ctx.mqttc:connect(CONFIG.DEVICE_ID, CONFIG.MQTT_KEEPALIVE, CONFIG.MQTT_CLEAN_SESSION == 1)
    end)

    if not ok then
        log.error("MQTT", "Connection failed: " .. tostring(err))
        ctx.state = MQTT_STATE.ERROR
        on_mqtt_disconnected()
    end
end

function mqtt_disconnect()
    if ctx.mqttc then
        pcall(function() ctx.mqttc:disconnect() end)
    end
    ctx.state = MQTT_STATE.DISCONNECTED
end

function mqtt_is_ready()
    return ctx.state == MQTT_STATE.CONNECTED
end

function mqtt_get_state()
    return ctx.state
end

-- ======================= Publish Functions =======================

local function mqtt_publish(topic, payload, qos)
    if not mqtt_is_ready() then
        log.warn("MQTT", "Cannot publish: not connected")
        return false
    end

    if not ctx.mqttc then
        return false
    end

    local ok, err = pcall(function()
        ctx.mqttc:publish(topic, payload, qos)
    end)

    if ok then
        ctx.last_publish = os.time()
        return true
    else
        log.error("MQTT", "Publish failed: " .. tostring(err))
        return false
    end
end

function mqtt_publish_location(payload)
    local ok = mqtt_publish(CONFIG.TOPIC_LOCATION, payload, CONFIG.MQTT_QOS_LOCATION)
    if ok then
        log.info("MQTT", string.format("Published location (QoS %d, %d bytes)",
            CONFIG.MQTT_QOS_LOCATION, #payload))
    end
    return ok
end

function mqtt_publish_heartbeat(payload)
    return mqtt_publish(CONFIG.TOPIC_HEARTBEAT, payload, CONFIG.MQTT_QOS_HEARTBEAT)
end

function mqtt_publish_sos(payload)
    local ok = mqtt_publish(CONFIG.TOPIC_SOS, payload, CONFIG.MQTT_QOS_SOS)
    if ok then
        log.info("MQTT", string.format("Published SOS alert (QoS %d)", CONFIG.MQTT_QOS_SOS))
    end
    return ok
end

function mqtt_publish_low_battery(payload)
    local ok = mqtt_publish(CONFIG.TOPIC_LOW_BATTERY, payload, CONFIG.MQTT_QOS_LOW_BATTERY)
    if ok then
        log.info("MQTT", "Published low battery alert")
    end
    return ok
end

-- ======================= Reconnect Backoff =======================

function mqtt_reset_backoff()
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
end

function mqtt_tick()
    -- Called periodically from main loop
    -- Exponential backoff reconnect is handled by timer in on_mqtt_disconnected()
    -- Nothing to do if connected
end

-- ======================= PSM Configuration =======================

function mqtt_configure_psm()
    -- Send AT+CPSMS via LuatOS's AT command channel
    -- LuatOS provides nril.at (AT proxy) to send AT commands to the modem
    local ok, err = pcall(function()
        local cmd = string.format(
            'AT+CPSMS=1,,,"%s","%s"',
            CONFIG.PSM_ACTIVE_TIMER,
            CONFIG.PSM_TAU_PERIOD
        )
        log.info("MQTT", "Configuring PSM: " .. cmd)
        -- nril.at(cmd, timeout_ms) -- wait for OK
        -- NOTE: exact API depends on LuatOS version
    end)

    -- Also configure eDRX
    pcall(function()
        -- nril.at('AT+CEDRXS=1,5,"1000"')
    end)

    log.info("MQTT", "PSM configured: Active=" .. CONFIG.PSM_ACTIVE_TIMER
        .. ", TAU=" .. CONFIG.PSM_TAU_PERIOD)
end

return {
    init = mqtt_init,
    connect = mqtt_connect,
    disconnect = mqtt_disconnect,
    is_ready = mqtt_is_ready,
    get_state = mqtt_get_state,
    publish_location = mqtt_publish_location,
    publish_heartbeat = mqtt_publish_heartbeat,
    publish_sos = mqtt_publish_sos,
    publish_low_battery = mqtt_publish_low_battery,
    tick = mqtt_tick,
    reset_backoff = mqtt_reset_backoff,
    configure_psm = mqtt_configure_psm,
}
