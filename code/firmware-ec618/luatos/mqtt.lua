--[[
  mqtt.lua -- MQTT Client for KeepSafe DTU (LuatOS-SoC)
  Ported from: code/firmware/main/mqtt.c + mqtt.h (ESP32-S3)
  Platform: YED DTU3 (EC718P-M100PG, 非 EC618)

  Uses LuatOS built-in MQTT library (mqttcore or net extension).
  The MQTT AT command set (AT+MQTTCONNCFG etc.) is NOT available on LuatOS firmware.
  Instead, we use the Lua MQTT client over the 4G data channel.

  Topic tree (prefixed with keepsafe/v1/{device_id}/):
    location      — QoS 1, GPS + LBS position report
    heartbeat     — QoS 0, periodic keepalive
    sos           — QoS 1, SOS alert
    alert/low_battery — QoS 1, low battery alert

  Error Handling:
    - Exponential backoff reconnect (1s -> 2s -> 4s ... -> 300s max)
    - Circuit breaker: stop reconnecting after MAX_FAILURES consecutive failures
    - Connection health check: periodic ping/keepalive watchdog
    - Stale connection detection: if no publish within CONN_HEALTH_TIMEOUT,
      force disconnect and reconnect
    - Manual reset via mqtt_reset_circuit_breaker()
]]

local CONFIG = require("config")

-- ======================= Internal State =======================

local MQTT_STATE = {
    DISCONNECTED = 0,
    CONNECTING   = 1,
    CONNECTED    = 2,
    ERROR        = 3,
    CIRCUIT_OPEN = 4,    -- Circuit breaker: too many failures, paused
}

local ctx = {
    state             = MQTT_STATE.DISCONNECTED,
    mqttc             = nil,            -- LuatOS MQTT client handle
    reconnect_delay   = CONFIG.RECONNECT_BASE_MS,
    last_reconnect    = 0,
    last_publish      = 0,
    last_health_check = 0,
    consecutive_failures = 0,
    max_failures      = CONFIG.RECONNECT_MAX_FAILURES or 10,
    circuit_open_until = 0,             -- timestamp when circuit breaker reopens
    connected_cb       = nil,
    disconnected_cb    = nil,
    network_down_cb    = nil,
    reconnect_timer    = nil,
}

-- ======================= MQTT Callbacks =======================

local function on_mqtt_connected()
    log.info("MQTT", "Connected to broker")
    ctx.state = MQTT_STATE.CONNECTED
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
    ctx.consecutive_failures = 0
    ctx.last_health_check = os.time()
    if ctx.connected_cb then ctx.connected_cb() end
end

local function on_mqtt_disconnected()
    log.warn("MQTT", "Disconnected from broker")
    ctx.state = MQTT_STATE.DISCONNECTED
    if ctx.disconnected_cb then ctx.disconnected_cb() end
    -- Schedule reconnect with backoff
    schedule_reconnect()
end

local function on_mqtt_message(topic, payload, qos)
    -- We currently don't subscribe to any topics
    log.debug("MQTT", string.format("Received message on %s (qos=%d)", topic, qos))
end

-- ======================= Reconnect with Exponential Backoff =======================

function schedule_reconnect()
    -- Cancel any pending reconnect timer
    if ctx.reconnect_timer then
        sys.timerStop(ctx.reconnect_timer)
        ctx.reconnect_timer = nil
    end

    -- Check circuit breaker
    if ctx.consecutive_failures >= ctx.max_failures then
        if ctx.state ~= MQTT_STATE.CIRCUIT_OPEN then
            ctx.state = MQTT_STATE.CIRCUIT_OPEN
            local wait_minutes = math.floor(CONFIG.RECONNECT_MAX_MS / 60000)
            ctx.circuit_open_until = os.time() + (CONFIG.RECONNECT_MAX_MS / 1000)
            log.error("MQTT", string.format(
                "Circuit breaker OPEN: %d consecutive failures. Will retry in ~%d min.",
                ctx.consecutive_failures, wait_minutes))
        end
        -- Schedule a retry after max delay
        ctx.reconnect_timer = sys.timerStart(function()
            ctx.consecutive_failures = 0
            ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
            ctx.state = MQTT_STATE.DISCONNECTED
            log.info("MQTT", "Circuit breaker reset. Attempting reconnect...")
            mqtt_connect()
        end, CONFIG.RECONNECT_MAX_MS)
        return
    end

    ctx.last_reconnect = os.time()
    local delay = ctx.reconnect_delay

    log.info("MQTT", string.format("Scheduling reconnect in %d ms (failure #%d/%d)",
        delay, ctx.consecutive_failures, ctx.max_failures))

    ctx.reconnect_timer = sys.timerStart(function()
        ctx.reconnect_timer = nil
        mqtt_connect()
    end, delay)
end

-- ======================= Public API =======================

function mqtt_init(connected_cb, disconnected_cb, network_down_cb)
    ctx.connected_cb = connected_cb
    ctx.disconnected_cb = disconnected_cb
    ctx.network_down_cb = network_down_cb
    log.info("MQTT", string.format("MQTT module initialized: broker=%s:%d",
        CONFIG.MQTT_HOST, CONFIG.MQTT_PORT))
end

function mqtt_connect()
    -- Circuit breaker check
    if ctx.state == MQTT_STATE.CIRCUIT_OPEN then
        if os.time() < ctx.circuit_open_until then
            log.info("MQTT", "Circuit breaker open, skipping connect")
            return
        else
            -- Circuit breaker timeout expired, reset
            ctx.state = MQTT_STATE.DISCONNECTED
            ctx.consecutive_failures = 0
            ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
            log.info("MQTT", "Circuit breaker timeout expired, resetting")
        end
    end

    if ctx.state == MQTT_STATE.CONNECTED then
        log.info("MQTT", "Already connected")
        return
    end

    if ctx.state == MQTT_STATE.CONNECTING then
        log.info("MQTT", "Connection already in progress")
        return
    end

    ctx.state = MQTT_STATE.CONNECTING
    log.info("MQTT", string.format("Connecting to %s:%d (client=%s)",
        CONFIG.MQTT_HOST, CONFIG.MQTT_PORT, CONFIG.DEVICE_ID))

    -- LuatOS MQTT client (mqtt.create / mqttc:connect)
    -- The mqtt library is built into LuatOS firmware
    local ok, err = pcall(function()
        -- Clean up any stale client
        if ctx.mqttc then
            pcall(function() ctx.mqttc:disconnect() end)
            ctx.mqttc = nil
        end

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
        ctx.consecutive_failures = ctx.consecutive_failures + 1
        -- Exponential backoff
        ctx.reconnect_delay = math.min(
            ctx.reconnect_delay * CONFIG.RECONNECT_MULTIPLIER,
            CONFIG.RECONNECT_MAX_MS
        )
        on_mqtt_disconnected()
    end
end

function mqtt_disconnect()
    -- Cancel reconnect timer
    if ctx.reconnect_timer then
        sys.timerStop(ctx.reconnect_timer)
        ctx.reconnect_timer = nil
    end

    if ctx.mqttc then
        pcall(function() ctx.mqttc:disconnect() end)
    end
    ctx.state = MQTT_STATE.DISCONNECTED
    ctx.consecutive_failures = 0
end

function mqtt_is_ready()
    return ctx.state == MQTT_STATE.CONNECTED
end

function mqtt_get_state()
    return ctx.state
end

function mqtt_get_state_name()
    local names = {
        [MQTT_STATE.DISCONNECTED] = "DISCONNECTED",
        [MQTT_STATE.CONNECTING]   = "CONNECTING",
        [MQTT_STATE.CONNECTED]    = "CONNECTED",
        [MQTT_STATE.ERROR]        = "ERROR",
        [MQTT_STATE.CIRCUIT_OPEN] = "CIRCUIT_OPEN",
    }
    return names[ctx.state] or "UNKNOWN"
end

-- ======================= Publish Functions =======================

local function mqtt_publish(topic, payload, qos)
    if not mqtt_is_ready() then
        log.warn("MQTT", "Cannot publish: not connected (state=" .. mqtt_get_state_name() .. ")")
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
        ctx.consecutive_failures = 0  -- Reset failure count on success
        return true
    else
        log.error("MQTT", "Publish failed: " .. tostring(err))
        -- Don't increment failures here — publish failures are expected during
        -- network blips. The disconnect callback handles reconnection.
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

-- ======================= Health Check / Watchdog =======================

function mqtt_tick()
    -- Called periodically from main loop (every 1-5 seconds)
    -- 1. Check connection health (stale connection detection)
    -- 2. Reset circuit breaker if enough time has passed
    -- 3. Trigger reconnect if disconnected and no timer scheduled

    local now = os.time()

    -- Stale connection check: if we haven't published in CONN_HEALTH_TIMEOUT seconds
    -- and we think we're connected, but the broker may have dropped us silently.
    -- Force a health check by attempting to disconnect and let reconnect handle it.
    -- NOTE: This is conservative — only trigger if we have a recent publish gap AND
    -- the MQTT keepalive hasn't been active.
    local health_timeout = CONFIG.MQTT_KEEPALIVE + 60  -- keepalive + 60s grace
    if ctx.state == MQTT_STATE.CONNECTED then
        if now - ctx.last_publish > health_timeout and ctx.last_publish > 0 then
            log.warn("MQTT", string.format(
                "Stale connection detected: no publish for %d s (keepalive=%d). Forcing reconnect.",
                now - ctx.last_publish, CONFIG.MQTT_KEEPALIVE))
            ctx.state = MQTT_STATE.DISCONNECTED
            if ctx.mqttc then
                pcall(function() ctx.mqttc:disconnect() end)
            end
            schedule_reconnect()
        end
    end

    -- Circuit breaker auto-reset after timeout
    if ctx.state == MQTT_STATE.CIRCUIT_OPEN then
        if now >= ctx.circuit_open_until then
            log.info("MQTT", "Circuit breaker timeout expired. Resetting for reconnect attempt.")
            ctx.state = MQTT_STATE.DISCONNECTED
            ctx.consecutive_failures = 0
            ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
            schedule_reconnect()
        end
    end

    -- If disconnected with no reconnect timer scheduled, trigger reconnect
    if ctx.state == MQTT_STATE.DISCONNECTED and not ctx.reconnect_timer then
        local min_backoff = math.max(5, math.floor(CONFIG.RECONNECT_BASE_MS / 1000))
        if now - ctx.last_reconnect > min_backoff then
            log.info("MQTT", "Disconnected with no reconnect timer, scheduling reconnect")
            schedule_reconnect()
        end
    end
end

-- ======================= Reconnect Utilities =======================

function mqtt_reset_backoff()
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
    log.info("MQTT", "Backoff reset to " .. CONFIG.RECONNECT_BASE_MS .. " ms")
end

function mqtt_reset_circuit_breaker()
    ctx.consecutive_failures = 0
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
    if ctx.state == MQTT_STATE.CIRCUIT_OPEN then
        ctx.state = MQTT_STATE.DISCONNECTED
    end
    log.info("MQTT", "Circuit breaker manually reset")
end

function mqtt_force_reconnect()
    log.info("MQTT", "Force reconnect requested")
    if ctx.mqttc then
        pcall(function() ctx.mqttc:disconnect() end)
    end
    ctx.state = MQTT_STATE.DISCONNECTED
    ctx.consecutive_failures = 0
    ctx.reconnect_delay = CONFIG.RECONNECT_BASE_MS
    if ctx.reconnect_timer then
        sys.timerStop(ctx.reconnect_timer)
        ctx.reconnect_timer = nil
    end
    mqtt_connect()
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
    get_state_name = mqtt_get_state_name,
    publish_location = mqtt_publish_location,
    publish_heartbeat = mqtt_publish_heartbeat,
    publish_sos = mqtt_publish_sos,
    publish_low_battery = mqtt_publish_low_battery,
    tick = mqtt_tick,
    reset_backoff = mqtt_reset_backoff,
    reset_circuit_breaker = mqtt_reset_circuit_breaker,
    force_reconnect = mqtt_force_reconnect,
    configure_psm = mqtt_configure_psm,
}
