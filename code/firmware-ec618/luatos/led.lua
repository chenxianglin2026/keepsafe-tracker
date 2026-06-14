--[[
  led.lua -- LED Status Indication for KeepSafe (LuatOS GPIO)
  Platform: Air780EG (EC618), LuatOS-SoC

  LEDs:
    - STATUS LED (GPIO27, blue): device state (on in normal, flash on event)
    - NET LED   (GPIO24, green): network status (on=connected, flash=connecting, off=no net)

  Patterns (stored as Lua timers):
    SOLID:       always on
    SLOW_BLINK:  1s on / 1s off
    FAST_BLINK:  200ms on / 200ms off
    PULSE:       short 50ms flash every 2s (battery-saving visibility mode)
    OFF:         always off
]]

local CONFIG = require("config")

local led = {}
local status_timer = nil
local net_timer = nil
local status_on = false
local net_on = false

-- ======================= GPIO Helpers =======================

local function gpio_write(pin, state)
    pcall(function()
        gpio.setup(pin, state and 1 or 0, gpio.OUTPUT)
    end)
end

local function gpio_toggle(pin)
    pcall(function()
        local current = gpio.get(pin) or 0
        gpio.setup(pin, current == 0 and 1 or 0, gpio.OUTPUT)
    end)
end

-- ======================= Pattern Handlers =======================

local patterns = {
    solid = function(pin)
        gpio_write(pin, 1)  -- always on
    end,
    slow_blink = function(pin)
        if not status_timer then return end
        gpio_toggle(pin)
    end,
    fast_blink = function(pin)
        if not status_timer then return end
        gpio_toggle(pin)
    end,
    pulse = function(pin)
        -- Brief on, then off
        gpio_write(pin, 1)
        sys.timerStart(function()
            gpio_write(pin, 0)
        end, CONFIG.LED_PULSE_DUTY_MS)
    end,
    off = function(pin)
        gpio_write(pin, 0)
    end,
}

-- ======================= Public API =======================

--- STATUS LED: solid on (normal operation)
function led.status_solid()
    led._set_status("solid", nil)  -- no timer needed
end

--- STATUS LED: slow blink (waiting for network/GPS)
function led.status_slow_blink()
    led._set_status("slow_blink", 1000)
end

--- STATUS LED: fast blink (SOS mode)
function led.status_fast_blink()
    led._set_status("fast_blink", 200)
end

--- STATUS LED: pulse (battery-saving visibility)
function led.status_pulse()
    led._set_status("pulse", CONFIG.LED_PULSE_PERIOD_MS)
end

--- STATUS LED: off (deep sleep)
function led.status_off()
    led._set_status("off", nil)
end

--- NET LED: solid on (network OK)
function led.net_connected()
    net_on = true
    gpio_write(CONFIG.GPIO.LED_NET, 1)
end

--- NET LED: slow blink (connecting/registering)
function led.net_connecting()
    led._set_net_timer(1000)
end

--- NET LED: off (no network)
function led.net_off()
    led._set_net_timer(nil)
    net_on = false
    gpio_write(CONFIG.GPIO.LED_NET, 0)
end

-- ======================= Internal =======================

function led._set_status(pattern, interval_ms)
    -- Cancel existing status timer
    if status_timer then
        sys.timerStop(status_timer)
        status_timer = nil
    end
    
    if pattern == "solid" then
        patterns.solid(CONFIG.GPIO.LED_STATUS)
    elseif pattern == "off" then
        patterns.off(CONFIG.GPIO.LED_STATUS)
    elseif pattern == "pulse" then
        patterns.pulse(CONFIG.GPIO.LED_STATUS)
        if interval_ms then
            status_timer = sys.timerStart(function()
                patterns.pulse(CONFIG.GPIO.LED_STATUS)
            end, interval_ms, true)  -- repeat
        end
    elseif pattern == "slow_blink" or pattern == "fast_blink" then
        -- Start with LED on
        patterns.solid(CONFIG.GPIO.LED_STATUS)
        if interval_ms then
            status_timer = sys.timerStart(function()
                patterns[pattern](CONFIG.GPIO.LED_STATUS)
            end, interval_ms, true)  -- repeat
        end
    end
end

function led._set_net_timer(interval_ms)
    if net_timer then
        sys.timerStop(net_timer)
        net_timer = nil
    end
    
    if not interval_ms then
        return  -- off
    end
    
    -- Start with LED on
    gpio_write(CONFIG.GPIO.LED_NET, 1)
    net_timer = sys.timerStart(function()
        gpio_toggle(CONFIG.GPIO.LED_NET)
    end, interval_ms, true)  -- repeating toggle
end

--- Initialize both LEDs (off state)
function led.init()
    gpio_write(CONFIG.GPIO.LED_STATUS, 0)
    gpio_write(CONFIG.GPIO.LED_NET, 0)
    log.info("LED", "LEDs initialized (STATUS=GPIO" .. CONFIG.GPIO.LED_STATUS .. 
        ", NET=GPIO" .. CONFIG.GPIO.LED_NET .. ")")
end

return led
