/*
 * main.c — KeepSafe Tracker Main Entry Point + State Machine Loop
 *
 * Hardware: ESP32-S3 + Air780E (4G+GNSS) + LIS3DH (Accelerometer)
 * Battery: 703048 800mAh LiPo
 *
 * Power path (deep sleep total ~25 µA):
 *   MCU deep sleep:   ~8 µA  (ESP32-S3, RTC timer + GPIO wake)
 *   Modem PSM:        ~15 µA (Air780E power saving mode)
 *   Accelerometer LP:  ~2 µA (LIS3DH 1Hz low-power mode)
 *
 * Wake sources:
 *   - RTC timer (periodic location report / heartbeat)
 *   - LIS3DH INT1 (motion detected)
 *   - SOS button GPIO (long press)
 *
 * State machine:
 *   STATIONARY -> MOVING -> JUST_STOPPED -> STATIONARY
 *   any state  -> SOS_ACTIVE (when SOS triggered)
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "driver/gpio.h"

#include "config.h"
#include "power.h"
#include "gps.h"
#include "mqtt.h"
#include "lbs.h"
#include "led.h"
#include "sos.h"
#include "accel.h"

static const char *TAG = "KEEPSAFE";

/* ======================= Forward Declarations ======================= */
static void uart_send_line(const char *cmd);
static void uart_rx_task(void *arg);
static void report_location(void);
static void report_heartbeat(void);
static void report_sos(void);
static void report_low_battery(void);
static void on_sos_triggered(const sos_event_t *event, void *user_data);
static void on_low_battery(const battery_level_t *battery, void *user_data);
static char *build_location_json(const gps_location_t *gps, const lbs_cell_info_t *lbs,
                                 uint8_t battery_pct);
static char *build_heartbeat_json(void);
static char *build_sos_json(const sos_event_t *event);

/* ======================= UART Send (Air780E Command Dispatch) ======================= */

/**
 * Send an AT command string to Air780E via UART1.
 * Called by power_gps_on/off, mqtt_configure_psm, lbs_query_* via function pointer.
 */
static void uart_send_line(const char *cmd)
{
    if (!cmd) return;

    size_t len = strlen(cmd);
    int written = uart_write_bytes(UART_AIR780E_NUM, cmd, len);
    if (written != len) {
        ESP_LOGW(TAG, "UART write partial: %d/%zu bytes", written, len);
    }

    /* Power-path: flush TX immediately to enter sleep faster */
    uart_wait_tx_done(UART_AIR780E_NUM, pdMS_TO_TICKS(100));
}

/* ======================= GPS Fix Acquisition (Blocking) ======================= */

/**
 * Attempt to acquire a GPS fix within GPS_FIX_TIMEOUT_MS.
 * Powers on GNSS, feeds NMEA lines from UART RX buffer into parser.
 *
 * Power-path: GPS_ON draws ~35-75 mA. Minimize time by checking
 * has_fix() early. Fall back to LBS if timeout.
 *
 * @return true if valid fix acquired.
 */
static bool acquire_gps_fix(void)
{
    /* Power on GNSS */
    power_gps_on(uart_send_line);
    vTaskDelay(pdMS_TO_TICKS(GPS_TURN_ON_DELAY_MS));

    /* Feed NMEA from UART RX ring buffer for up to GPS_FIX_TIMEOUT_MS */
    uint32_t deadline = esp_timer_get_time() / 1000 + GPS_FIX_TIMEOUT_MS;
    uint8_t buf[256];

    while ((esp_timer_get_time() / 1000) < deadline) {
        int len = uart_read_bytes(UART_AIR780E_NUM, buf, sizeof(buf) - 1,
                                  pdMS_TO_TICKS(100));
        if (len > 0) {
            buf[len] = '\0';
            /* Split on newlines and feed each NMEA sentence */
            char *line = strtok((char *)buf, "\r\n");
            while (line) {
                gps_parse_line(line);
                line = strtok(NULL, "\r\n");
            }
        }

        /* Early exit if we have a valid 3D fix */
        if (gps_has_valid_fix()) {
            ESP_LOGI(TAG, "GPS fix acquired in %lu ms",
                     GPS_FIX_TIMEOUT_MS - (deadline - esp_timer_get_time() / 1000));
            return true;
        }

        taskYIELD();
    }

    /* Timeout — fall back to LBS */
    ESP_LOGW(TAG, "GPS fix timeout (%d ms), falling back to LBS", GPS_FIX_TIMEOUT_MS);
    power_gps_off(uart_send_line);
    return false;
}

/* ======================= JSON Builders ======================= */

/**
 * Build location report JSON payload.
 * Caller must free() the returned string.
 */
static char *build_location_json(const gps_location_t *gps, const lbs_cell_info_t *lbs,
                                 uint8_t battery_pct)
{
    /* Pre-allocate a reasonable buffer: ~512 bytes is enough */
    char *json = malloc(512);
    if (!json) return NULL;

    if (gps && gps->has_fix) {
        /* GPS-based location */
        snprintf(json, 512,
                 "{"
                 "\"type\":\"location\","
                 "\"device_id\":\"%s\","
                 "\"ts\":%lu,"
                 "\"lat\":%.6f,"
                 "\"lng\":%.6f,"
                 "\"alt\":%.1f,"
                 "\"speed\":%.2f,"
                 "\"heading\":%.1f,"
                 "\"accuracy\":%.1f,"
                 "\"satellites\":%u,"
                 "\"fix_type\":%d,"
                 "\"battery\":%u,"
                 "\"charging\":false,"
                 "\"rssi\":0,"
                 "\"cell_id\":\"\","
                 "\"source\":\"gps\""
                 "}",
                 DEVICE_ID,
                 (unsigned long)(gps->timestamp_unix ? gps->timestamp_unix : esp_timer_get_time() / 1000000),
                 gps->latitude,
                 gps->longitude,
                 gps->altitude,
                 (double)gps->speed,
                 (double)gps->heading,
                 (double)gps->accuracy_hdop,
                 gps->satellites,
                 gps->fix_type,
                 battery_pct);
    } else {
        /* LBS-based location */
        const char *cell_str = lbs ? lbs_format_cell_id_string() : "unknown";
        snprintf(json, 512,
                 "{"
                 "\"device_id\":\"%s\","
                 "\"ts\":%lu,"
                 "\"lat\":0,"
                 "\"lng\":0,"
                 "\"cell_id\":\"%s\","
                 "\"rssi\":%d,"
                 "\"bat\":%u,"
                 "\"source\":\"lbs\""
                 "}",
                 DEVICE_ID,
                 (unsigned long)(esp_timer_get_time() / 1000000),
                 cell_str,
                 lbs ? (int)lbs->rssi_dbm : -999,
                 battery_pct);
    }

    return json;
}

/**
 * Build heartbeat JSON payload.
 * Caller must free() the returned string.
 */
static char *build_heartbeat_json(void)
{
    char *json = malloc(256);
    if (!json) return NULL;

    uint32_t loc_count = 0, sos_count = 0;
    power_get_stats(&loc_count, &sos_count);

    battery_level_t batt = sos_read_battery();

    snprintf(json, 256,
             "{"
             "\"type\":\"heartbeat\","
             "\"device_id\":\"%s\","
             "\"ts\":%lu,"
             "\"battery\":%u,"
             "\"charging\":false,"
             "\"rssi\":0,"
             "\"uptime\":%lu,"
             "\"fw_version\":\"%s\""
             "}",
             DEVICE_ID,
             (unsigned long)(esp_timer_get_time() / 1000000),
             batt.percent,
             (unsigned long)(esp_timer_get_time() / 1000),
             FIRMWARE_VERSION);

    return json;
}

/**
 * Build SOS alert JSON payload.
 * Caller must free() the returned string.
 */
static char *build_sos_json(const sos_event_t *event)
{
    char *json = malloc(384);
    if (!json) return NULL;

    /* Use event data if available, otherwise current GPS/LBS */
    double lat = 0.0, lng = 0.0;
    uint32_t ts = esp_timer_get_time() / 1000000;

    if (event) {
        lat = event->latitude;
        lng = event->longitude;
        ts = event->timestamp_unix ? event->timestamp_unix : ts;
    } else {
        gps_location_t loc = gps_get_location();
        if (loc.has_fix) {
            lat = loc.latitude;
            lng = loc.longitude;
            ts = loc.timestamp_unix ? loc.timestamp_unix : ts;
        }
    }

    snprintf(json, 384,
             "{"
             "\"type\":\"sos\","
             "\"device_id\":\"%s\","
             "\"ts\":%lu,"
             "\"lat\":%.6f,"
             "\"lng\":%.6f,"
             "\"accuracy\":10.0,"
             "\"battery\":%u,"
             "\"trigger_duration_ms\":%lu"
             "}",
             DEVICE_ID,
             (unsigned long)ts,
             lat,
             lng,
             event ? event->battery_percent : sos_read_battery().percent,
             event ? (unsigned long)event->trigger_duration_ms : 3000UL);

    return json;
}

/* ======================= SOS & Battery Callbacks ======================= */

static void on_sos_triggered(const sos_event_t *event, void *user_data)
{
    (void)user_data;
    ESP_LOGW(TAG, "SOS triggered! Battery: %u%%", event ? event->battery_percent : 0);

    /* Transition to SOS_ACTIVE state */
    power_on_sos_triggered();

    /* LED: red blink 5Hz */
    led_set_mode(LED_RED, LED_MODE_BLINK_5HZ);

    /* Vibro feedback */
    sos_vibrate_feedback(SOS_VIBRATE_MS);
}

static void on_low_battery(const battery_level_t *battery, void *user_data)
{
    (void)user_data;
    ESP_LOGW(TAG, "Low battery: %u%% (%u mV)", battery->percent, battery->voltage_mv);

    /* LED: red blink 0.5Hz */
    led_set_mode(LED_RED, LED_MODE_BLINK_0_5HZ);

    /* Publish low battery alert immediately */
    report_low_battery();
}

/* ======================= Report Functions ======================= */

static void report_location(void)
{
    uint32_t now_ms = esp_timer_get_time() / 1000;

    ESP_LOGI(TAG, "Reporting location (state=%d)", (int)power_get_state());

    /* --- Step 1: Acquire position --- */
    bool gps_fix = acquire_gps_fix();

    /* If GPS fix failed and we are stationary, use LBS */
    lbs_cell_info_t cell_info = {0};
    if (!gps_fix) {
        lbs_query_signal_strength(uart_send_line);
        lbs_query_cell_info(uart_send_line);
        cell_info = lbs_get_cell_info();
    }

    /* --- Step 2: Read battery --- */
    battery_level_t batt = sos_read_battery();

    /* --- Step 3: Build and publish JSON --- */
    gps_location_t gps_loc = gps_get_location();
    char *payload = build_location_json(
        gps_fix ? &gps_loc : NULL,
        gps_fix ? NULL : &cell_info,
        batt.percent
    );

    if (payload) {
        mqtt_publish_location(payload);
        free(payload);
    }

    /* --- Step 4: Update state machine --- */
    power_on_location_reported(now_ms);

    /* --- Step 5: LED indication --- */
    if (gps_fix) {
        led_set_mode(LED_GREEN, LED_MODE_BLINK_1HZ);  /* Green blink: GPS fix */
    }
    led_set_mode(LED_BLUE, LED_MODE_SOLID);            /* Blue solid: network */
}

static void report_heartbeat(void)
{
    uint32_t now_ms = esp_timer_get_time() / 1000;

    ESP_LOGI(TAG, "Sending heartbeat");

    char *payload = build_heartbeat_json();
    if (payload) {
        mqtt_publish_heartbeat(payload);
        free(payload);
    }

    power_on_heartbeat_sent(now_ms);
}

static void report_sos(void)
{
    ESP_LOGW(TAG, "Reporting SOS alert");

    /* Ensure GPS is on for SOS location */
    if (!gps_has_valid_fix()) {
        acquire_gps_fix();
    }

    const sos_event_t *event = sos_get_last_event();
    char *payload = build_sos_json(event);

    if (payload) {
        mqtt_publish_sos(payload);
        free(payload);
    }
}

static void report_low_battery(void)
{
    ESP_LOGW(TAG, "Reporting low battery alert");

    battery_level_t batt = sos_read_battery();
    char payload[256];

    snprintf(payload, sizeof(payload),
             "{"
             "\"device_id\":\"%s\","
             "\"ts\":%lu,"
             "\"type\":\"low_battery\","
             "\"bat\":%u,"
             "\"voltage_mv\":%u"
             "}",
             DEVICE_ID,
             (unsigned long)(esp_timer_get_time() / 1000000),
             batt.percent,
             batt.voltage_mv);

    mqtt_publish_low_battery(payload);
    sos_clear_low_battery_alert();
}

/* ======================= UART RX Task ======================= */

/**
 * FreeRTOS task: reads all responses from Air780E UART and feeds them
 * to the appropriate parsers (MQTT AT responses, LBS responses, GPS NMEA).
 */
static void uart_rx_task(void *arg)
{
    (void)arg;
    uint8_t buf[256];

    while (1) {
        int len = uart_read_bytes(UART_AIR780E_NUM, buf, sizeof(buf) - 1,
                                  pdMS_TO_TICKS(100));
        if (len > 0) {
            buf[len] = '\0';

            /* Feed each line to parsers */
            char *line = strtok((char *)buf, "\r\n");
            while (line) {
                /* Trim leading/trailing whitespace */
                while (*line == ' ' || *line == '\t') line++;
                if (*line == '\0') {
                    line = strtok(NULL, "\r\n");
                    continue;
                }

                /* Route to appropriate parser */
                mqtt_feed_response(line);
                lbs_parse_response(line);

                /* GPS NMEA always starts with '$' */
                if (line[0] == '$') {
                    gps_parse_line(line);
                }

                line = strtok(NULL, "\r\n");
            }
        }

        /* Yield to let lower-priority tasks run */
        taskYIELD();
    }
}

/* ======================= SOS Button ISR ======================= */

/**
 * GPIO ISR for SOS button. Called from interrupt context.
 */
static void IRAM_ATTR sos_gpio_isr_handler(void *arg)
{
    (void)arg;
    int level = gpio_get_level(GPIO_SOS_BUTTON);
    sos_button_isr(level);
}

/**
 * GPIO ISR for LIS3DH motion interrupt.
 */
static void IRAM_ATTR accel_gpio_isr_handler(void *arg)
{
    (void)arg;
    accel_isr_handler();
}

/* ======================= GPIO / Interrupt Setup ======================= */

static void configure_gpio_interrupts(void)
{
    /* SOS button: input with pull-up, interrupt on any edge */
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << GPIO_SOS_BUTTON),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    gpio_config(&io_conf);

    /* LIS3DH INT1: input, interrupt on positive edge */
    io_conf.pin_bit_mask = (1ULL << GPIO_LIS3DH_INT1);
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.intr_type = GPIO_INTR_POSEDGE;
    gpio_config(&io_conf);

    /* Install GPIO ISR service */
    gpio_install_isr_service(ESP_INTR_FLAG_LEVEL1);
    gpio_isr_handler_add(GPIO_SOS_BUTTON, sos_gpio_isr_handler, NULL);
    gpio_isr_handler_add(GPIO_LIS3DH_INT1, accel_gpio_isr_handler, NULL);

    ESP_LOGI(TAG, "GPIO interrupts configured (SOS=GPIO%d, MOTION=GPIO%d)",
             GPIO_SOS_BUTTON, GPIO_LIS3DH_INT1);
}

/* ======================= Main Entry Point ======================= */

void app_main(void)
{
    ESP_LOGI(TAG, "=== KeepSafe v%s Booting ===", FIRMWARE_VERSION);

    /* --- Initialize NVS (needed for WiFi/MQTT config storage) --- */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS flash needs erase");
        nvs_flash_erase();
        nvs_flash_init();
    }

    /* --- Initialize UART1 (Air780E) --- */
    uart_config_t uart_cfg = {
        .baud_rate           = UART_AIR780E_BAUD,
        .data_bits           = UART_DATA_8_BITS,
        .parity              = UART_PARITY_DISABLE,
        .stop_bits           = UART_STOP_BITS_1,
        .flow_ctrl           = UART_HW_FLOWCTRL_DISABLE,
        .source_clk          = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_AIR780E_NUM, &uart_cfg);
    uart_set_pin(UART_AIR780E_NUM, UART_AIR780E_TX_GPIO, UART_AIR780E_RX_GPIO,
                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    uart_driver_install(UART_AIR780E_NUM, UART_AIR780E_BUF_SIZE,
                        UART_AIR780E_BUF_SIZE, 0, NULL, 0);

    /* --- Initialize power management (detects wake reason) --- */
    power_init();

    /* Register UART send function with MQTT module */
    mqtt_set_uart_send(uart_send_line);

    /* --- Initialize all modules --- */
    gps_parser_init();
    lbs_init();
    mqtt_init(DEVICE_ID, MQTT_BROKER_HOST, MQTT_BROKER_PORT, NULL, NULL);
    led_init();
    sos_init(on_sos_triggered, on_low_battery, NULL);

    /* Initialize accelerometer (I2C) */
    if (!accel_init()) {
        ESP_LOGE(TAG, "LIS3DH initialization FAILED — continuing without motion detection");
    } else {
        accel_configure_motion_interrupt(50, 20);  /* 50 mg threshold, 20 ms duration */
        accel_low_power_mode();                     /* Enter 2 µA low-power mode */
    }

    /* Configure GPIO interrupts */
    configure_gpio_interrupts();

    /* --- Create UART RX task --- */
    xTaskCreatePinnedToCore(uart_rx_task, "uart_rx", 4096, NULL, 10, NULL, 1);

    /* --- Handle wake reason --- */
    wake_reason_t wake = power_get_wake_reason();
    ESP_LOGI(TAG, "Wake reason: %d", (int)wake);

    switch (wake) {
        case WAKE_REASON_TIMER:
            /* Periodic wake: just report, then go back to sleep */
            ESP_LOGI(TAG, "Timer wake — periodic report");
            led_set_mode(LED_BLUE, LED_MODE_SOLID);  /* Blue: network */
            break;

        case WAKE_REASON_MOTION:
            /* Motion detected: enter MOVING state, enable GPS */
            ESP_LOGI(TAG, "Motion wake — entering MOVING state");
            led_set_mode(LED_BLUE, LED_MODE_SOLID);  /* Blue: network */
            break;

        case WAKE_REASON_SOS_BUTTON:
            /* SOS button wake: immediate SOS report */
            ESP_LOGW(TAG, "SOS button wake — sending SOS alert");
            led_set_mode(LED_RED, LED_MODE_BLINK_5HZ); /* Red 5Hz: SOS */
            report_sos();
            break;

        case WAKE_REASON_RESET:
        default:
            /* Cold boot: full initialization, check battery */
            ESP_LOGI(TAG, "Cold boot — full initialization");
            led_set_mode(LED_BLUE, LED_MODE_SOLID);
            break;
    }

    /* If motion wake, notify power state machine */
    if (wake == WAKE_REASON_MOTION) {
        power_on_motion_detected();
    }

    /* --- Start MQTT connection --- */
    mqtt_start();

    /* If SOS wake, immediately enter SOS loop (don't delay) */
    if (wake == WAKE_REASON_SOS_BUTTON) {
        /* Already sent SOS above; keep reporting every INTERVAL_SOS_REPEAT_MS */
    }

    /*
     * ======================= Main Loop =======================
     *
     * Power-path: Each iteration checks time-based triggers and
     * accelerates sleep entry. The loop runs until power_enter_deep_sleep()
     * is called, which does not return.
     */
    uint32_t last_motion_check_ms = esp_timer_get_time() / 1000;

    while (1) {
        uint32_t now_ms = esp_timer_get_time() / 1000;

        /* --- Periodic ticks --- */
        sos_tick();                     /* SOS debounce + timing */
        mqtt_tick();                    /* MQTT reconnection + keepalive */
        led_update();                   /* LED blink patterns */

        /* --- Check for SOS trigger (from ISR) --- */
        if (sos_was_triggered()) {
            ESP_LOGW(TAG, "SOS triggered in main loop");
            power_on_sos_triggered();
            led_set_mode(LED_RED, LED_MODE_BLINK_5HZ);
            report_sos();
        }

        /* --- Motion detection tick (every 1 second) --- */
        if (now_ms - last_motion_check_ms >= 1000) {
            if (accel_was_motion_detected()) {
                ESP_LOGI(TAG, "Motion detected in main loop");
                power_on_motion_detected();
            }
            last_motion_check_ms = now_ms;
        }

        /* --- SOS_ACTIVE: high-frequency reporting --- */
        if (power_get_state() == POWER_STATE_SOS_ACTIVE) {
            if (power_is_time_for_location_report(now_ms)) {
                report_location();
            }
            /* SOS mode: sleep only briefly, then re-check */
            vTaskDelay(pdMS_TO_TICKS(5000));
            continue;
        }

        /* --- Location report due? --- */
        if (power_is_time_for_location_report(now_ms)) {
            report_location();
        }

        /* --- Heartbeat due? --- */
        if (power_is_time_for_heartbeat(now_ms)) {
            report_heartbeat();
        }

        /* --- Check stationary timeout (MOVING -> JUST_STOPPED -> STATIONARY) --- */
        if (power_get_state() == POWER_STATE_MOVING) {
            /* If no motion detected for 5 minutes, mark stationary timeout */
            uint32_t motion_timeout_ms = 5 * 60 * 1000;
            if (now_ms - last_motion_check_ms > motion_timeout_ms) {
                power_on_stationary_timeout();
            }
        }

        if (power_get_state() == POWER_STATE_JUST_STOPPED) {
            /*
             * JUST_STOPPED: one more report with GPS, then transition to STATIONARY.
             * The state machine handles the transition; we just need to ensure
             * a report was sent. After JUST_STOPPED timeout, the state transitions
             * back to STATIONARY in power.c.
             */
        }

        /* --- Check for low battery alert (latched) --- */
        if (sos_is_low_battery_alert_pending()) {
            report_low_battery();
        }

        /*
         * ======================= Deep Sleep =======================
         *
         * Power-path: Turn off LEDs, ensure UART TX is flushed,
         * set wake timers, and enter deep sleep.
         *
         * Total deep sleep current: ~25 µA
         *   MCU: 8 µA  +  Modem PSM: 15 µA  +  Accel: 2 µA
         *
         * Battery life estimate with 800mAh:
         *   800 mAh / 0.025 mA = 32,000 hours ≈ 3.6 years (ideal, no GPS)
         *   With one GPS fix per 30 min: ~6 months
         *   With one GPS fix per 5 min:  ~2 months
         */
        ESP_LOGI(TAG, "Entering deep sleep (state=%d, next report=%lu ms)",
                 (int)power_get_state(),
                 (unsigned long)power_get_next_report_interval());

        /* Disable LEDs for sleep */
        led_all_off();
        led_set_enabled(false);

        /* Enter deep sleep — does not return */
        power_enter_deep_sleep();

        /*
         * NOTREACHED: power_enter_deep_sleep() does not return.
         * On next wake, app_main() runs again fresh.
         */
    }
}
