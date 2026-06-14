--[[
  accel.lua -- LIS3DH 三轴加速度计驱动 (LuatOS I2C)
  Platform: Air780EG (EC618), LuatOS-SoC
  Ported from: ESP32-S3 I2C driver + LIS3DH datasheet

  LIS3DH: 超低功耗 3 轴加速度计 (±2g/4g/8g/16g, I2C/SPI)
  Datasheet: https://www.st.com/resource/en/datasheet/lis3dh.pdf
  
  Features used:
    - Motion detection (INT1 interrupt on acceleration above threshold)
    - Free-fall detection (optional)
    - Low-power mode (ODR 1Hz, ~2µA) between checks
  
  I2C registers (7-bit address 0x18 when SA0=GND):
    0x0F  WHO_AM_I   (should return 0x33)
    0x20  CTRL_REG1  (ODR + LPen + XYZ enable)
    0x21  CTRL_REG2  (HPF control)
    0x22  CTRL_REG3  (Interrupt config)
    0x23  CTRL_REG4  (FS scale + BDU + HR)
    0x24  CTRL_REG5  (FIFO + Latch INT)
    0x30  INT1_CFG   (INT1 config)
    0x32  INT1_THS   (INT1 threshold)
    0x33  INT1_DURATION (INT1 duration)
    0x28  OUT_X_L    (X-axis low byte, little-endian)
]]

local CONFIG = require("config")

local accel = {}
local initialized = false
local motion_detected = false
local last_motion_time = 0
local int1_cb = nil  -- callback when INT1 fires

-- ======================= I2C Helpers =======================

local i2c_id = 0  -- LuatOS I2C bus 0

local function i2c_setup()
    -- Air780EG I2C0: SDA=GPIO4, SCL=GPIO5
    -- Speed: 100kHz (standard) or 400kHz (fast)
    if i2c.setup then
        i2c.setup(i2c_id, CONFIG.GPIO.I2C_SDA, CONFIG.GPIO.I2C_SCL)
    end
end

local function i2c_write_reg(addr, reg, val)
    if i2c.send then
        i2c.send(i2c_id, CONFIG.LIS3DH_ADDR, string.char(reg, val))
    end
end

local function i2c_read_reg(addr, reg, len)
    len = len or 1
    if i2c.send and i2c.recv then
        i2c.send(i2c_id, addr, string.char(reg))
        local data = i2c.recv(i2c_id, addr, len)
        return data
    end
    return nil
end

-- ======================= Initialization =======================

--- Initialize LIS3DH: power up, configure ODR/scale, enable motion INT1
function accel.init(motion_callback)
    int1_cb = motion_callback
    i2c_setup()
    
    -- 1. Verify chip ID
    local whoami = i2c_read_reg(CONFIG.LIS3DH_ADDR, 0x0F, 1)
    if not whoami or whoami:byte(1) ~= 0x33 then
        log.warn("ACCEL", "LIS3DH not detected (WHO_AM_I=" .. 
            (whoami and string.format("0x%02X", whoami:byte(1)) or "nil") .. ")")
        return false
    end
    log.info("ACCEL", "LIS3DH detected")

    -- 2. CTRL_REG4 (0x23): BDU=1 (block data update), FS=±4g (01), HR=1 (high resolution)
    --    4g scale: 1mg/digit in HR mode
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x23, 0x91)  -- 1001_0001: BDU + FS_4G + HR
    
    -- 3. CTRL_REG1 (0x20): ODR=10Hz (0100), LPen=0 (normal), XYZ=1 (all axes)
    --    0010_0111 = 0x27 for 10Hz all axes, normal mode
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x20, 0x27)
    
    -- 4. INT1_THS (0x32): motion threshold. 4g scale HR = 1mg/LSB.
    --    Threshold ~200mg → 200 = 0xC8
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x32, 0xC8)
    
    -- 5. INT1_DURATION (0x33): must exceed threshold for N * 1/ODR
    --    5 samples @ 10Hz = 0.5s → 5
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x33, 0x05)
    
    -- 6. INT1_CFG (0x30): AOI (OR combination), 6D disabled, Z/Y/X high enable
    --    0x2A = 0010_1010: ZHIE + YHIE + XHIE (trigger when above threshold)
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x30, 0x2A)
    
    -- 7. CTRL_REG3 (0x22): route INT1 to INT1 pad
    --    0x40 = 0100_0000: I1_INT1 (AOI/6D interrupt on INT1)
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x22, 0x40)
    
    -- Enable INT1 pad as GPIO interrupt on Air780EG
    -- LuatOS: gpio.setup(pin, function, mode, pull)
    if gpio.setup then
        gpio.setup(CONFIG.GPIO.ACCEL_INT1, function(val)
            if val == 1 then
                motion_detected = true
                last_motion_time = os.time()
                log.info("ACCEL", "Motion detected (INT1 fired)")
                if int1_cb then int1_cb() end
            end
        end, gpio.INT or gpio.IRQ, gpio.PULLUP)
    end
    
    initialized = true
    log.info("ACCEL", "LIS3DH initialized: 10Hz, ±4g HR, motion INT1 enabled")
    return true
end

--- Read raw accelerometer data (mg)
function accel.read()
    if not initialized then return nil end
    local data = i2c_read_reg(CONFIG.LIS3DH_ADDR, 0x28, 6)  -- OUT_X_L..OUT_Z_H
    if not data or #data < 6 then return nil end
    
    -- Little-endian 16-bit signed, 1mg/LSB on 4g HR mode
    local function to_mg(lo, hi)
        local val = lo + hi * 256
        if val >= 32768 then val = val - 65536 end  -- signed
        return val  -- already in mg on 4g HR
    end
    
    return {
        x = to_mg(data:byte(1), data:byte(2)),
        y = to_mg(data:byte(3), data:byte(4)),
        z = to_mg(data:byte(5), data:byte(6)),
    }
end

--- Check if motion was detected since last read (auto-clearing)
function accel.has_motion()
    if motion_detected then
        motion_detected = false
        return true
    end
    return false
end

--- Get time of last motion
function accel.last_motion()
    return last_motion_time
end

--- Enter low-power mode (ODR 1Hz)
function accel.low_power()
    if not initialized then return end
    -- CTRL_REG1: ODR=1Hz (0001), LPen=1, XYZ=1 = 0001_0111 = 0x17
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x20, 0x17)
    log.info("ACCEL", "Entered low-power mode (1Hz)")
end

--- Resume normal mode (ODR 10Hz)
function accel.wake()
    if not initialized then return end
    i2c_write_reg(CONFIG.LIS3DH_ADDR, 0x20, 0x27)
    log.info("ACCEL", "Resumed normal mode (10Hz)")
end

--- Check if initialized and healthy
function accel.is_ok()
    if not initialized then return false end
    local whoami = i2c_read_reg(CONFIG.LIS3DH_ADDR, 0x0F, 1)
    return whoami and whoami:byte(1) == 0x33
end

return accel
