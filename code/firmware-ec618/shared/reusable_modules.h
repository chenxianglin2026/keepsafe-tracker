/*
 * shared/reusable_modules.h — Reference: Reusable Modules from ESP32-S3 Firmware
 *
 * This header documents which modules from code/firmware/main/ can be
 * directly reused (or translated) for the EC618 LuatOS firmware.
 *
 * Do NOT compile this file — it serves as documentation only.
 */

/* ================================================================
 * LOW difficulty — directly translatable to Lua (8 modules)
 * ================================================================ */

/* power.h — Power state machine enums, directly -> Lua table */
/* mqtt.h — MQTT interface definitions, directly -> Lua module API */
/* gps.h — GPS data structures, directly -> Lua table */
/* gps.c — NMEA parser logic, translate to Lua OR use CGNSINF */
/* lbs.h — LBS cell info structure, directly -> Lua table */
/* sos.h — SOS event + battery structures, directly -> Lua table */
/* led.h — LED mode enums, directly -> Lua table */
/* accel.h — LIS3DH register addresses, directly reusable */

/* ================================================================
 * MEDIUM difficulty — logic translatable, API needs adaptation (5 modules)
 * ================================================================ */

/* config.h — Most macros translatable; GPIO macros need remapping */
/* power.c — State machine logic translatable to Lua event-driven */
/* main.c — JSON builders translatable; UART/GPIO needs new API */
/* lbs.c — AT response parser logic translatable; verify EC618 AT format */

/* ================================================================
 * HIGH difficulty — needs full rewrite for LuatOS API (5 modules)
 * ================================================================ */

/* mqtt.c — ESP-IDF UART AT wrapper -> LuatOS socket MQTT library */
/* accel.c — ESP-IDF I2C driver -> LuatOS I2C API */
/* sos.c — ESP-IDF GPIO/ADC -> LuatOS GPIO/ADC API */
/* led.c — ESP-IDF LEDC PWM -> LuatOS PWM API */

/* ================================================================
 * Key Porting Patterns
 * ================================================================
 *
 * ESP-IDF (C)           ->  LuatOS (Lua)
 * ────────────────────────────────────────────
 * xSemaphoreCreateMutex  ->  (Lua is single-threaded, no mutex needed)
 * FreeRTOS tasks         ->  sys.taskInit() coroutines
 * vTaskDelay(ms)         ->  sys.wait(ms)
 * esp_timer_get_time()   ->  os.time() / os.clock()
 * ESP_LOGx(TAG, fmt, ..) ->  log.info/log.warn/log.error(TAG, msg)
 * driver/uart.h          ->  uart.setup() / uart.write()
 * driver/i2c.h           ->  i2c.setup() / i2c.send() / i2c.recv()
 * driver/gpio.h          ->  gpio.setup() / gpio.set() / gpio.get()
 * driver/ledc.h          ->  pwm.open() / pwm.duty()
 * esp_sleep.h            ->  pm.dtimerSleep() / pm.power(pm.DEEPSLEEP)
 */
