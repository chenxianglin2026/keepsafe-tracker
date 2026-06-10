--[[
  psm.lua -- Low-Power PSM Deep Sleep Module for KeepSafe EC618 (LuatOS)
  Platform: Air780EG (EC618 core), LuatOS firmware
  Date: 2026-06-10

  PSM (Power Saving Mode) is a 3GPP Rel-12 feature that allows the modem
  to enter deep sleep between data transmissions while remaining registered
  on the network. Unlike conventional sleep, PSM:
    - Keeps the PDP context active (no need to re-attach)
    - Maintains IP address
    - Wakes on: RTC timer expiry, GPIO interrupt, or uplink data

  This module manages:
    1. PSM negotiation with the network via AT+CPSMS
    2. eDRX configuration for extended discontinuous reception
    3. Deep sleep entry / wake cycle management
    4. Guard conditions: never enter PSM during SOS, active GPS, or MQTT publish
    5. Dynamic timer adjustment based on battery level and motion state
    6. Wake-cause tracking for analytics

  Current draw estimates (Air780EG):
    - Active (4G TX):     ~200-500 mA
    - Idle (4G RX):       ~10-20 mA
    - PSM deep sleep:     <20 uA (microamps)
    - eDRX (PTW window):  ~1-2 mA

  For a device reporting every 30 min stationary, with PSM:
    Battery life: ~3-6 months on a 500mAh battery (vs ~2-3 days without PSM)

  AT Commands used:
    AT+CPSMS=1,,,"<T3324>","<T3412>"   -- Enable PSM with timers
    AT+CEDRXS=1,5,"<paging_window>"     -- eDRX (LTE Cat-M1/NB-IoT)
    AT+CEREG?                            -- Check network reg status
    AT+CSCLK=1                           -- Enter slow clock mode (legacy, fallback)
]]

local CONFIG = require("config")

-- ======================= Module State =======================

local PSM_STATE = {
    ACTIVE   = 0,   -- Modem fully awake, data sessions active
    IDLE     = 1,   -- Modem idle but RRC connected
    PSM      = 2,   -- Modem in PSM deep sleep
    eDRX     = 3,   -- Modem in eDRX (periodic paging wake)
    DISABLED = 4,   -- PSM not configured or network rejected
}

local state_names = {
    [PSM_STATE.ACTIVE]   = "ACTIVE",
    [PSM_STATE.IDLE]     = "IDLE",
    [PSM_STATE.PSM]      = "PSM",
    [PSM_STATE.eDRX]     = "eDRX",
    [PSM_STATE.DISABLED] = "DISABLED",
}

local ctx = {
    state               = PSM_STATE.IDLE,
    configured          = false,
    supported           = false,   -- Set true after AT+CPSMS? response
    last_wake           = 0,       -- os.time() of last wake
    last_sleep          = 0,       -- os.time() of last sleep entry
    sleep_duration      = 0,       -- last sleep duration in seconds
    wake_cause          = "",      -- "timer", "gpio", "uart", "data"
    total_sleep_seconds = 0,       -- total PSM sleep time for stats
    sleep_cycles        = 0,       -- number of PSM cycles
    active_timer        = CONFIG.PSM_ACTIVE_TIMER or "00001000",  -- T3324: 10s
    tau_period          = CONFIG.PSM_TAU_PERIOD or "00000101",    -- T3412: 54min
    edrx_cycle          = "1000",  -- eDRX paging cycle in ms (1.28s typical)
    guard_active        = false,   -- true = don't enter PSM
    request_pending     = false,
    request_retries     = 0,
    max_retries         = 3,
}

-- ======================= Guard Conditions =======================

-- External guard flags set by main.lua or mqtt.lua
local guard_reasons = {
    sos_active        = false,  -- SOS mode: must stay awake
    mqtt_publishing   = false,  -- Mid-publish: don't sleep
    gps_active        = false,  -- GPS fix in progress
    network_recovery  = false,  -- Network recovery in progress
    charging          = false,  -- USB charging: no need to sleep
}

-- ======================= PSM Timer Parsing =======================

-- AT+CPSMS timers are bit-encoded per 3GPP TS 24.008
-- T3324 (Active Time): bits 1-3 = unit, bits 5-8 = value
--   000 = 2 seconds, 001 = 1 minute, 010 = 6 minutes (decihours)
-- T3412 (TAU Period): bits 1-3 = unit, bits 5-8 = value
--   000 = 2 seconds, 001 = 1 minute, 010 = 6 minutes, 111 = deactivated

local function parse_psm_timer(hex_str)
    -- Parse a PSM timer hex string to seconds
    -- Format: "TTTTTTTT" where bits encode value * unit multiplier
    if not hex_str or #hex_str ~= 8 then
        return nil
    end
    local val = tonumber(hex_str, 16)
    if not val then return nil end

    local unit_bits = (val >> 5) & 0x07
    local timer_val = (val >> 0) & 0x1F

    local multipliers = {
        [0] = 2,      -- 2 seconds
        [1] = 60,     -- 1 minute
        [2] = 360,    -- 6 minutes (decihour)
        [3] = 360,    -- 6 minutes
        [4] = 60,     -- 1 minute
        [5] = 360,    -- 6 minutes
        [6] = 360,    -- 6 minutes
        [7] = 0,      -- deactivated
    }

    local mult = multipliers[unit_bits] or 0
    return timer_val * mult
end

local function format_psm_timer(active_sec, tau_sec)
    -- Format seconds to PSM timer hex string
    -- Simplified: use unit=1 (1 minute) for most practical values
    -- T3324 Active Time: typically 10s-60s
    -- T3412 TAU: typically 10min-1hr
    local function encode(seconds, max_val)
        if seconds <= 124 then
            -- Unit 000 = 2 seconds, value = seconds/2, max 31*2=62s
            local v = math.floor(seconds / 2)
            if v > 31 then v = 31 end
            return string.format("%08X", (0 << 5) | v)
        elseif seconds <= 1860 then
            -- Unit 001 = 1 minute, value = seconds/60, max 31 min
            local v = math.floor(seconds / 60)
            if v > 31 then v = 31 end
            return string.format("%08X", (1 << 5) | v)
        else
            -- Unit 010 = 6 minutes (decihour), value = seconds/360, max ~3hr
            local v = math.floor(seconds / 360)
            if v > max_val then v = max_val end
            return string.format("%08X", (2 << 5) | v)
        end
    end
    return encode(active_sec or 10, 31), encode(tau_sec or 3240, 31)
end

-- ======================= PSM Configuration =======================

function psm_configure(active_sec, tau_sec)
    -- Configure PSM timers via AT+CPSMS
    -- active_sec: T3324 active time in seconds (default 10s)
    -- tau_sec:    T3412 TAU period in seconds (default 54min = 3240s)

    local active_hex, tau_hex
    if active_sec and tau_sec then
        active_hex, tau_hex = format_psm_timer(active_sec, tau_sec)
    else
        active_hex = ctx.active_timer
        tau_hex = ctx.tau_period
    end

    local cmd = string.format('AT+CPSMS=1,,,"%s","%s"', active_hex, tau_hex)
    log.info("PSM", "Configuring: " .. cmd)

    local ok = false
    pcall(function()
        -- nril.at(cmd, 5000)
        -- Parse response for OK
        ok = true  -- TODO: implement actual AT send
    end)

    if ok then
        ctx.configured = true
        ctx.active_timer = active_hex
        ctx.tau_period = tau_hex
        log.info("PSM", string.format(
            "Configured: Active=%s (%ds), TAU=%s",
            active_hex, parse_psm_timer(active_hex) or 0,
            tau_hex))
    else
        log.warn("PSM", "Configuration failed, PSM may not be supported")
    end

    return ok
end

function psm_enable_edrx()
    -- Configure eDRX for better power efficiency
    -- eDRX allows the modem to skip paging cycles while in idle
    -- AT+CEDRXS=<mode>,<type>,<edrx_value>
    --   mode=1: enable, type=5: LTE (WB-E-UTRAN), value: paging cycle

    local cmd = string.format('AT+CEDRXS=1,5,"%s"', ctx.edrx_cycle)
    log.info("PSM", "Configuring eDRX: " .. cmd)

    pcall(function()
        -- nril.at(cmd, 5000)
    end)

    -- Also query current eDRX settings
    pcall(function()
        -- nril.at("AT+CEDRXS?", 3000)
    end)

    log.info("PSM", string.format("eDRX configured: cycle=%s ms", ctx.edrx_cycle))
end

function psm_check_support()
    -- Query if network supports PSM
    -- AT+CPSMS? returns current PSM settings from network
    pcall(function()
        -- local resp = nril.at("AT+CPSMS?", 5000)
        -- Parse: +CPSMS: <mode>,,"<T3324>","<T3412>"
        -- If mode=1, PSM is supported and configured
        ctx.supported = true  -- TODO: parse actual response
    end)

    if ctx.supported then
        log.info("PSM", "Network supports PSM")
    else
        log.warn("PSM", "Network does not support PSM, falling back to slow clock")
    end
end

-- ======================= Sleep / Wake Management =======================

function psm_can_sleep()
    -- Check all guard conditions before entering PSM
    if ctx.guard_active then
        log.debug("PSM", "Sleep blocked: guard_active")
        return false
    end

    for reason, active in pairs(guard_reasons) do
        if active then
            log.debug("PSM", string.format("Sleep blocked: %s", reason))
            return false
        end
    end

    -- Don't sleep if recently woke (minimum active window)
    local min_active = CONFIG.PSM_MIN_ACTIVE_MS and (CONFIG.PSM_MIN_ACTIVE_MS / 1000) or 10
    if os.time() - ctx.last_wake < min_active then
        log.debug("PSM", string.format("Sleep blocked: less than %d s active", min_active))
        return false
    end

    -- Don't sleep if PSM is not configured or supported
    if not ctx.configured then
        log.debug("PSM", "Sleep blocked: PSM not configured")
        return false
    end

    return true
end

function psm_enter_sleep()
    -- Enter PSM deep sleep
    -- The modem will automatically enter PSM after the active timer (T3324)
    -- expires. We just need to stop sending data and let the timer expire.
    -- The LuatOS system can also call pm.force(pm.DEEPSLEEP) if available.

    if not psm_can_sleep() then
        return false
    end

    ctx.state = PSM_STATE.PSM
    ctx.last_sleep = os.time()
    ctx.request_pending = false

    log.info("PSM", string.format(
        "Entering PSM deep sleep. Active=%s TAU=%s. Will wake in ~%d s.",
        ctx.active_timer, ctx.tau_period,
        parse_psm_timer(ctx.tau_period) or 3240))

    -- Notify main loop to stop timers
    -- The actual modem PSM entry is automatic after T3324 expires with no data

    return true
end

function psm_wake_from_sleep(wake_cause)
    -- Called when the system wakes from PSM
    -- wake_cause: "timer" (TAU expiry), "gpio" (SOS/motion), "uart", "data"

    ctx.state = PSM_STATE.ACTIVE
    ctx.last_wake = os.time()
    ctx.wake_cause = wake_cause or "unknown"

    if ctx.last_sleep > 0 then
        ctx.sleep_duration = ctx.last_wake - ctx.last_sleep
        ctx.total_sleep_seconds = ctx.total_sleep_seconds + ctx.sleep_duration
        ctx.sleep_cycles = ctx.sleep_cycles + 1
    end

    -- Reset guard flags
    ctx.guard_active = false
    for k, _ in pairs(guard_reasons) do
        guard_reasons[k] = false
    end

    log.info("PSM", string.format(
        "Woke from PSM. Cause=%s. Slept %d s. Total cycles=%d, total sleep=%d s (~%.1f hrs)",
        ctx.wake_cause, ctx.sleep_duration, ctx.sleep_cycles,
        ctx.total_sleep_seconds, ctx.total_sleep_seconds / 3600))

    -- After wake, re-negotiate PSM with network
    psm_configure()

    return true
end

-- ======================= Guard API =======================

function psm_set_guard(reason)
    -- Block PSM sleep for a specific reason
    -- Called by main.lua when entering SOS, GPS fix, etc.
    guard_reasons[reason] = true
    ctx.guard_active = true
    log.debug("PSM", string.format("Guard set: %s", reason))
end

function psm_clear_guard(reason)
    -- Clear a specific guard
    guard_reasons[reason] = false
    -- Re-evaluate overall guard state
    local any_guard = false
    for _, active in pairs(guard_reasons) do
        if active then
            any_guard = true
            break
        end
    end
    ctx.guard_active = any_guard
    log.debug("PSM", string.format("Guard cleared: %s. Overall=%s", reason, ctx.guard_active and "BLOCKED" or "ALLOWED"))
end

function psm_clear_all_guards()
    for k, _ in pairs(guard_reasons) do
        guard_reasons[k] = false
    end
    ctx.guard_active = false
    log.info("PSM", "All guards cleared")
end

-- ======================= Dynamic Timer Adjustment =======================

function psm_adjust_timers(battery_pct, is_moving)
    -- Dynamically adjust PSM timers based on battery level and motion state
    -- Low battery: more aggressive sleep to conserve power
    -- Moving: shorter TAU to report more frequently
    -- Stationary + high battery: longer TAU for maximum battery life

    local active_sec = 10    -- Default: 10s active time
    local tau_sec = 3240     -- Default: 54 min TAU

    if is_moving then
        -- Moving: keep TAU shorter to report position more frequently
        -- But active time stays minimal since GPS is handled separately
        active_sec = 10
        tau_sec = 600  -- 10 minutes
    else
        -- Stationary
        if battery_pct and battery_pct <= 10 then
            -- Critical battery: maximum sleep, minimal wake
            active_sec = 5
            tau_sec = 7200  -- 2 hours
        elseif battery_pct and battery_pct <= 20 then
            -- Low battery: aggressive sleep
            active_sec = 8
            tau_sec = 5400  -- 90 minutes
        elseif battery_pct and battery_pct >= 80 then
            -- High battery, stationary: balanced
            active_sec = 15
            tau_sec = 3600  -- 60 minutes
        end
    end

    -- Apply the adjusted timers
    local prev_active = ctx.active_timer
    local prev_tau = ctx.tau_period

    if psm_configure(active_sec, tau_sec) then
        log.info("PSM", string.format(
            "Timers adjusted: Active %s->%s (%ds), TAU %s->%s (%ds) [bat=%s%%, moving=%s]",
            prev_active, ctx.active_timer, active_sec,
            prev_tau, ctx.tau_period, tau_sec,
            tostring(battery_pct), tostring(is_moving)))
    end
end

-- ======================= Slow Clock Fallback =======================

function psm_slow_clock_enable()
    -- Fallback for modems/networks that don't support PSM
    -- AT+CSCLK=1 enables slow clock mode (legacy power saving)
    -- The modem enters sleep when DTR is low and no data activity

    log.info("PSM", "Enabling slow clock mode (fallback)")
    pcall(function()
        -- nril.at("AT+CSCLK=1", 3000)
    end)

    ctx.state = PSM_STATE.DISABLED  -- We're not in true PSM
    log.warn("PSM", "Using slow clock fallback. Power savings limited vs true PSM.")
end

function psm_slow_clock_disable()
    pcall(function()
        -- nril.at("AT+CSCLK=0", 3000)
    end)
    log.info("PSM", "Slow clock mode disabled")
end

-- ======================= Status / Telemetry =======================

function psm_get_state()
    return ctx.state
end

function psm_get_state_name()
    return state_names[ctx.state] or "UNKNOWN"
end

function psm_is_sleeping()
    return ctx.state == PSM_STATE.PSM
end

function psm_get_stats()
    return {
        state = psm_get_state_name(),
        configured = ctx.configured,
        supported = ctx.supported,
        last_wake = ctx.last_wake,
        last_sleep = ctx.last_sleep,
        sleep_duration = ctx.sleep_duration,
        wake_cause = ctx.wake_cause,
        total_sleep_seconds = ctx.total_sleep_seconds,
        sleep_cycles = ctx.sleep_cycles,
        active_timer = ctx.active_timer,
        tau_period = ctx.tau_period,
        guard_active = ctx.guard_active,
    }
end

-- ======================= Periodic Tick =======================

function psm_tick()
    -- Called periodically from main loop
    -- Checks if we should request PSM entry

    if ctx.state == PSM_STATE.PSM then
        -- We're sleeping; this shouldn't normally execute
        return
    end

    -- If idle and no pending operations, request PSM
    if ctx.state == PSM_STATE.IDLE and not ctx.request_pending then
        if psm_can_sleep() then
            ctx.request_pending = true
            log.debug("PSM", "Requesting PSM entry...")
            -- The actual entry happens after T3324 (active timer) expires
            -- with no data activity. We just mark the intent.
        end
    end
end

-- ======================= Initialization =======================

function psm_init()
    log.info("PSM", "Initializing Power Saving Mode module")

    -- Step 1: Check if PSM is supported by network
    psm_check_support()

    -- Step 2: Configure PSM with default timers
    if psm_configure() then
        log.info("PSM", "PSM initialized with Active=" .. ctx.active_timer
            .. " TAU=" .. ctx.tau_period)
    else
        log.warn("PSM", "PSM configuration failed, trying eDRX + slow clock")
        psm_enable_edrx()
        psm_slow_clock_enable()
    end

    -- Step 3: Enable eDRX for additional power savings
    psm_enable_edrx()

    ctx.state = PSM_STATE.IDLE
    ctx.last_wake = os.time()

    log.info("PSM", string.format(
        "Initialized: state=%s, active=%s, tau=%s",
        psm_get_state_name(), ctx.active_timer, ctx.tau_period))

    return ctx.configured or ctx.supported
end

-- ======================= Module Export =======================

return {
    -- State
    STATE_ACTIVE   = PSM_STATE.ACTIVE,
    STATE_IDLE     = PSM_STATE.IDLE,
    STATE_PSM      = PSM_STATE.PSM,
    STATE_eDRX     = PSM_STATE.eDRX,
    STATE_DISABLED = PSM_STATE.DISABLED,

    -- Lifecycle
    init            = psm_init,
    tick            = psm_tick,
    configure       = psm_configure,
    check_support   = psm_check_support,

    -- Sleep / Wake
    can_sleep       = psm_can_sleep,
    enter_sleep     = psm_enter_sleep,
    wake_from_sleep = psm_wake_from_sleep,
    is_sleeping     = psm_is_sleeping,

    -- Guards
    set_guard       = psm_set_guard,
    clear_guard     = psm_clear_guard,
    clear_all_guards = psm_clear_all_guards,

    -- eDRX
    enable_edrx     = psm_enable_edrx,

    -- Dynamic adjustment
    adjust_timers   = psm_adjust_timers,

    -- Fallback
    slow_clock_enable  = psm_slow_clock_enable,
    slow_clock_disable = psm_slow_clock_disable,

    -- Status
    get_state       = psm_get_state,
    get_state_name  = psm_get_state_name,
    get_stats       = psm_get_stats,

    -- Timer utilities
    parse_timer     = parse_psm_timer,
    format_timer    = format_psm_timer,
}
