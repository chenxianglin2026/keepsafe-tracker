--[[
  battery.lua -- Battery Voltage/Percentage Monitoring for KeepSafe (LuatOS)
  Platform: Air780EG (EC618), LuatOS-SoC

  Hardware:
    - LiPo battery 200mAh, nominal 3.7V, full 4.2V, empty 3.3V
    - Voltage divider: R1=100kΩ, R2=33kΩ → V_adc = V_bat * 33/(100+33) = V_bat * 0.248
    - 4.2V → 1.04V at ADC, 3.3V → 0.82V at ADC
    - Air780EG ADC0 (GPIO10): 0-1.2V range
    - ADC resolution: 12-bit (0-4095)
  
  Percentage estimation: using LiPo discharge curve (non-linear)
    Model: piecewise linear interpolation from datasheet
]]

local CONFIG = require("config")

local battery = {}
local voltage_mv = 4200  -- default: assume full
local percentage = 100
local last_read_time = 0
local adc_id = 0  -- Air780EG ADC channel 0 (GPIO10)

-- Voltage divider ratio: R2 / (R1 + R2) = 33/133 = 0.248
local DIVIDER_RATIO = 33.0 / (100.0 + 33.0)  -- ~0.248

-- ADC reference voltage (Air780EG VBAT or external)
-- Air780EG typical: internal 1.2V reference for ADC0
local ADC_VREF_MV = 1200

-- ======================= LiPo Discharge Curve =======================
-- LiPo discharge table: voltage_mv → percentage
-- Based on typical 3.7V LiPo discharge curve
local discharge_curve = {
    {4200, 100}, {4150, 95},  {4100, 88},  {4050, 80},
    {4000, 72},  {3950, 64},  {3900, 56},  {3850, 48},
    {3800, 40},  {3750, 32},  {3700, 24},  {3650, 16},
    {3600, 10},  {3550, 6},   {3500, 3},   {3450, 1},
    {3400, 0},
}

--- Read raw ADC value and convert to battery voltage (mV)
local function read_adc_mv()
    -- LuatOS ADC API: adc.open(id), adc.read(id)
    if not adc.open then
        log.warn("BAT", "ADC API not available")
        return voltage_mv  -- return last known
    end

    local ok, raw = pcall(function()
        adc.open(adc_id)
        local val = adc.read(adc_id)
        adc.close(adc_id)
        return val
    end)

    if not ok or not raw or raw == 0 then
        return voltage_mv
    end

    -- Convert ADC reading → voltage at ADC pin
    local v_adc_mv = (raw / 4095.0) * ADC_VREF_MV
    
    -- Compensate for voltage divider: V_bat = V_adc / DIVIDER_RATIO
    local v_bat_mv = v_adc_mv / DIVIDER_RATIO

    return v_bat_mv
end

--- Convert voltage to percentage using discharge curve interpolation
local function voltage_to_percent(mv)
    if mv >= discharge_curve[1][1] then return 100 end
    
    for i = 2, #discharge_curve do
        local v_high, p_high = discharge_curve[i-1][1], discharge_curve[i-1][2]
        local v_low, p_low   = discharge_curve[i][1], discharge_curve[i][2]
        
        if mv >= v_low then
            -- Linear interpolation between points
            local ratio = (mv - v_low) / (v_high - v_low)
            return math.floor(p_low + ratio * (p_high - p_low))
        end
    end
    
    return 0
end

--- Read battery voltage and update state
function battery.read()
    local mv = read_adc_mv()
    voltage_mv = mv
    percentage = voltage_to_percent(mv)
    last_read_time = os.time()

    log.info("BAT", string.format("Voltage=%dmV, %d%%", mv, percentage))
    
    -- Alert on critically low battery
    if percentage <= CONFIG.BAT_LOW_PERCENT and percentage > 0 then
        log.warn("BAT", string.format("LOW BATTERY: %d%% (%dmV)", percentage, mv))
    end
    
    return voltage_mv, percentage
end

--- Get last known values (no new ADC read)
function battery.get_voltage_mv()  return voltage_mv end
function battery.get_percent()     return percentage end
function battery.is_low()          return percentage <= CONFIG.BAT_LOW_PERCENT end
function battery.is_critical()     return percentage <= 5 end

--- Initialize battery monitoring
function battery.init()
    log.info("BAT", "Battery monitoring initialized (ADC0, divider=1:" .. 
        string.format("%.0f", 1/DIVIDER_RATIO) .. ")")
    battery.read()  -- initial read
    return true
end

return battery
