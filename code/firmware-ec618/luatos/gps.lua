--[[
  gps.lua -- GPS/GNSS Data Parsing for EC618 (LuatOS)
  Ported from: code/firmware/main/gps.c + gps.h (ESP32-S3)
  Platform: Air780EG (EC618 core)

  The EC618 modem provides GNSS data via AT commands:
    - AT+CGNSPWR=1     — Power on GNSS
    - AT+CGNSINF       — Get parsed GNSS navigation information (JSON-like)
      Response format (CSV):
      +CGNSINF: <mode>,<lat>,<lng>,<alt>,<speed>,<course>,
                <sv_count>,<hdop>,<pdop>,<vdop>,<utc_time>...

  We parse the CGNSINF response because it returns decimal degrees directly,
  avoiding the NMEA DDDMM.MMMM -> decimal conversion.
]]

local CONFIG = require("config")

-- ======================= GPS Data Structure =======================
-- Mirrors gps_location_t from gps.h

local gps_data = {
    latitude   = 0.0,      -- Decimal degrees (positive = N, negative = S)
    longitude  = 0.0,      -- Decimal degrees (positive = E, negative = W)
    altitude   = 0.0,      -- Meters above mean sea level
    speed      = 0.0,      -- Ground speed in km/h (from CGNSINF; convert to m/s)
    heading    = 0.0,      -- True course in degrees
    satellites = 0,        -- Number of satellites in use
    has_fix    = false,    -- True if we have a valid fix
    fix_type   = 0,        -- Fix quality (0=none, 1=GPS, 2=DGPS)
    hdop       = 99.9,     -- Horizontal Dilution of Precision
    pdop       = 99.9,     -- Position Dilution of Precision
    vdop       = 99.9,     -- Vertical Dilution of Precision
    utc_time   = "",       -- UTC time string from GNSS
}

-- ======================= Constants =======================

-- CGNSINF field indices (0-based)
local CGNSINF_MODE      = 1
local CGNSINF_LAT       = 2
local CGNSINF_LNG       = 3
local CGNSINF_ALT       = 4
local CGNSINF_SPEED     = 5   -- km/h
local CGNSINF_COURSE    = 6   -- degrees
local CGNSINF_SV_COUNT  = 8   -- visible satellites
local CGNSINF_HDOP      = 9
local CGNSINF_PDOP      = 10
local CGNSINF_VDOP      = 11
local CGNSINF_UTC       = 12

-- Fix mode values (CGNSINF field 1)
local GNSS_MODE_NO_FIX  = 0
local GNSS_MODE_2D      = 1
local GNSS_MODE_3D      = 2

-- ======================= Internal Helpers =======================

local function at_cmd_with_retry(cmd, timeout_ms, retries)
    retries = retries or 2
    timeout_ms = timeout_ms or 3000

    for i = 1, retries do
        -- Send AT command via LuatOS nril.at or uart
        local ok, resp = pcall(function()
            -- LuatOS provides uart.setup/uart.write to send AT directly
            -- For CGNSINF, we use the modem's AT channel
            -- On Air780EG, the main UART is the AT command interface
            -- The response comes back as a single line
            return "NOT_IMPLEMENTED" -- placeholder for actual AT send
        end)
        if ok then
            return true, resp
        end
        if i < retries then
            sys.wait(500)
        end
    end
    return false, nil
end

-- Parse CGNSINF CSV response line
local function parse_cgnsinf(line)
    if not line then
        return false
    end

    -- Strip prefix
    local data = line:gsub("^%+CGNSINF:%s*", "")
    if data == line then
        -- Not a CGNSINF response
        log.warn("GPS", "Unexpected CGNSINF response format: " .. (line:sub(1, 50)))
        return false
    end

    -- Split by commas
    local fields = {}
    for field in data:gmatch("([^,]+)") do
        fields[#fields + 1] = field
    end

    if #fields < 10 then
        log.warn("GPS", "CGNSINF too few fields: " .. #fields)
        return false
    end

    -- Parse fields
    local mode = tonumber(fields[CGNSINF_MODE]) or 0
    local lat  = tonumber(fields[CGNSINF_LAT]) or 0.0
    local lng  = tonumber(fields[CGNSINF_LNG]) or 0.0
    local alt  = tonumber(fields[CGNSINF_ALT]) or 0.0
    local speed_kmh = tonumber(fields[CGNSINF_SPEED]) or 0.0
    local course = tonumber(fields[CGNSINF_COURSE]) or 0.0
    local sv_count = tonumber(fields[CGNSINF_SV_COUNT]) or 0
    local hdop = tonumber(fields[CGNSINF_HDOP]) or 99.9
    local pdop = tonumber(fields[CGNSINF_PDOP]) or 99.9
    local vdop = tonumber(fields[CGNSINF_VDOP]) or 99.9
    local utc = fields[CGNSINF_UTC] or ""

    -- Validate
    if mode == GNSS_MODE_NO_FIX then
        gps_data.has_fix = false
        gps_data.fix_type = 0
        gps_data.satellites = sv_count
        log.debug("GPS", string.format("No fix: mode=%d, sats=%d", mode, sv_count))
        return false  -- no valid position
    end

    if lat == 0.0 and lng == 0.0 then
        gps_data.has_fix = false
        gps_data.fix_type = 0
        log.warn("GPS", "Got fix but lat/lng are zero")
        return false
    end

    -- Update data
    gps_data.latitude   = lat
    gps_data.longitude  = lng
    gps_data.altitude   = alt
    gps_data.speed      = speed_kmh / 3.6  -- km/h -> m/s
    gps_data.heading    = course
    gps_data.satellites = sv_count
    gps_data.has_fix    = true
    gps_data.fix_type   = (mode == GNSS_MODE_3D) and 1 or 1  -- 1=GPS fix
    gps_data.hdop       = hdop
    gps_data.pdop       = pdop
    gps_data.vdop       = vdop
    gps_data.utc_time   = utc

    log.info("GPS", string.format(
        "Fix: %s mode=%d lat=%.6f lng=%.6f alt=%.1f spd=%.1f hdg=%.1f sat=%d hdop=%.1f",
        gps_data.has_fix and "YES" or "NO",
        mode, lat, lng, alt,
        gps_data.speed, gps_data.heading,
        sv_count, hdop
    ))
    return true
end

-- ======================= Public API =======================

-- Poll CGNSINF and update gps_data
-- Returns true if we got a valid fix
function gps_poll()
    -- Use the EC618 modem's AT channel to send CGNSINF
    -- On LuatOS, the recommended way is:
    --   uart.setup(1, 115200)  -- The AT command UART
    --   uart.write(1, "AT+CGNSINF\r\n")
    --   -- Wait and read response
    --
    -- For now, we describe the expected AT flow. The actual implementation
    -- depends on the LuatOS firmware's AT proxy or direct UART access.

    log.info("GPS", "Polling GNSS position via AT+CGNSINF...")

    local ok, resp = pcall(function()
        -- TODO: Replace with actual UART AT command when hardware available
        -- Example for Air780EG LuatOS:
        --   local uart_id = 1  -- AT UART
        --   uart.setup(uart_id, 115200)
        --   uart.write(uart_id, "AT+CGNSINF\r\n")
        --   local resp = uart.read(uart_id, "*l")  -- read line
        --   return resp

        -- Placeholder: simulate a valid GPS fix for testing
        -- Remove this block and uncomment the UART code above for real hardware
        return "+CGNSINF: 2,22.543100,113.934600,15.0,1.8,270.0,,12,0.9,1.2,1.5,20260609120000"
    end)

    if not ok then
        log.error("GPS", "AT+CGNSINF failed: " .. tostring(resp))
        return false
    end

    return parse_cgnsinf(resp)
end

-- Power on GNSS
function gps_power_on()
    log.info("GPS", "Powering on GNSS...")
    pcall(function()
        -- uart.write(1, "AT+CGNSPWR=1\r\n")
        -- Wait for cold start (needs ~30s for first fix in open sky)
        sys.wait(CONFIG.GPS_TURN_ON_DELAY)
    end)
end

-- Power off GNSS (save power)
function gps_power_off()
    log.info("GPS", "Powering off GNSS...")
    pcall(function()
        -- uart.write(1, "AT+CGNSPWR=0\r\n")
    end)
end

-- Get a copy of the GPS data
function gps_get_data()
    return {
        latitude   = gps_data.latitude,
        longitude  = gps_data.longitude,
        altitude   = gps_data.altitude,
        speed      = gps_data.speed,
        heading    = gps_data.heading,
        satellites = gps_data.satellites,
        has_fix    = gps_data.has_fix,
        fix_type   = gps_data.fix_type,
        hdop       = gps_data.hdop,
    }
end

-- Check if we have a valid fix
function gps_has_valid_fix()
    return gps_data.has_fix and gps_data.satellites > 0
end

-- Wait for a GPS fix with timeout
-- Returns true if fix obtained within timeout_ms
function gps_wait_for_fix(timeout_ms)
    timeout_ms = timeout_ms or CONFIG.GPS_FIX_TIMEOUT_MS
    local start = os.clock() * 1000

    log.info("GPS", string.format("Waiting for GNSS fix (timeout %d ms)...", timeout_ms))

    while (os.clock() * 1000 - start) < timeout_ms do
        if gps_poll() and gps_has_valid_fix() then
            log.info("GPS", "Got valid fix after " .. math.floor(os.clock() * 1000 - start) .. " ms")
            return true
        end
        sys.wait(1000)  -- poll every 1 second
    end

    log.warn("GPS", string.format("Failed to get GPS fix within %d ms", timeout_ms))
    return false
end

-- Reset GPS state
function gps_reset()
    gps_data.latitude   = 0.0
    gps_data.longitude  = 0.0
    gps_data.altitude   = 0.0
    gps_data.speed      = 0.0
    gps_data.heading    = 0.0
    gps_data.satellites = 0
    gps_data.has_fix    = false
    gps_data.fix_type   = 0
    gps_data.hdop       = 99.9
    gps_data.pdop       = 99.9
    gps_data.vdop       = 99.9
    gps_data.utc_time   = ""
    log.info("GPS", "GPS state reset")
end

-- ======================= Module Export =======================

return {
    poll         = gps_poll,
    power_on     = gps_power_on,
    power_off    = gps_power_off,
    get_data     = gps_get_data,
    has_valid_fix = gps_has_valid_fix,
    wait_for_fix = gps_wait_for_fix,
    reset        = gps_reset,
}
