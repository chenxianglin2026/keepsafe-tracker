/*
 * mqtt.c — MQTT Communication + PSM Power Saving Implementation
 *
 * Uses Air780E's built-in MQTT AT command set:
 *   AT+MQTTCONNCFG — configure MQTT connection parameters
 *   AT+MQTTCONN   — connect to broker
 *   AT+MQTTPUB    — publish message
 *   AT+MQTTSUB    — subscribe (if needed)
 *   AT+MQTTDISC   — disconnect
 *
 * PSM is configured via AT+CPSMS (see config.h for details).
 *
 * Power path notes:
 *   - After publishing, the modem enters PSM deep sleep within ~10 seconds.
 *   - During PSM, the modem is unreachable but draws ~15 µA.
 *   - Wake from PSM: any AT command or RRC paging (if tracking area updates).
 *   - Keepalive = 300s balances battery life with connection stability.
 *   - Exponential backoff prevents rapid reconnect attempts that drain battery.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "mqtt.h"
#include "config.h"

static const char *TAG = "MQTT";

/* ======================= Internal State ======================= */

typedef struct {
    char    device_id[16];
    char    mqtt_host[128];
    uint16_t mqtt_port;
    bool    initialized;

    // State
    mqtt_state_t        state;
    uint32_t            reconnect_delay_ms;
    uint32_t            last_reconnect_attempt;
    uint32_t            last_publish_time;

    // UART send function (for AT commands to Air780E)
    void (*uart_send)(const char *cmd);

    // Callbacks
    mqtt_state_callback_t state_cb;
    mqtt_msg_callback_t   msg_cb;

    // Mutex for state changes
    SemaphoreHandle_t mutex;
} mqtt_context_t;

static mqtt_context_t s_ctx = {0};

/* ======================= JSON Builders for MQTT Topics ======================= */

// Topic strings (pre-allocated in BSS)
static char s_topic_location[64];
static char s_topic_heartbeat[64];
static char s_topic_sos[64];
static char s_topic_low_battery[64];

static void build_topics(void)
{
    snprintf(s_topic_location, sizeof(s_topic_location),
             "keepsafe/v1/%s/location", s_ctx.device_id);
    snprintf(s_topic_heartbeat, sizeof(s_topic_heartbeat),
             "keepsafe/v1/%s/heartbeat", s_ctx.device_id);
    snprintf(s_topic_sos, sizeof(s_topic_sos),
             "keepsafe/v1/%s/sos", s_ctx.device_id);
    snprintf(s_topic_low_battery, sizeof(s_topic_low_battery),
             "keepsafe/v1/%s/alert/low_battery", s_ctx.device_id);
}

/* ======================= AT Command Helpers ======================= */

static void send_at(const char *cmd)
{
    if (s_ctx.uart_send) {
        s_ctx.uart_send(cmd);
    }
}

/**
 * Send MQTTCONNCFG (connection configuration).
 */
static void at_mqtt_conncfg(void)
{
    char cmd[256];
    snprintf(cmd, sizeof(cmd),
             "AT+MQTTCONNCFG=0,%d,\"%s\",%d,0,%d,\"%s\"\r\n",
             MQTT_CLEAN_SESSION,
             s_ctx.mqtt_host,
             s_ctx.mqtt_port,
             MQTT_KEEPALIVE_S,
             s_ctx.device_id);
    send_at(cmd);
}

/**
 * Send MQTTCONN to establish connection.
 */
static void at_mqtt_conn(void)
{
    char cmd[128];
    snprintf(cmd, sizeof(cmd),
             "AT+MQTTCONN=0,\"%s\",%d,0\r\n",
             s_ctx.mqtt_host, s_ctx.mqtt_port);
    send_at(cmd);
}

/**
 * Send MQTTPUB for a publish.
 */
static bool at_mqtt_pub(const char *topic, const char *payload, int qos)
{
    if (!topic || !payload || !s_ctx.uart_send) return false;

    // Escape special characters in payload for AT command
    // AT+MQTTPUB=<profile>,<topic>,<payload>,<qos>,<retain>
    // Maximum payload length per packet: ~1024 bytes (limited by Air780E AT buffer)
    // We'll use a simple approach: send as raw text if no special chars

    char cmd[1536]; // Large enough for typical payloads
    int len = snprintf(cmd, sizeof(cmd),
                       "AT+MQTTPUB=0,\"%s\",\"%s\",%d,0\r\n",
                       topic, payload, qos);

    if (len >= (int)sizeof(cmd)) {
        ESP_LOGE(TAG, "MQTT publish payload too large (%d bytes)", len);
        return false;
    }

    send_at(cmd);
    return true;
}

/* ======================= Publish Wrappers ======================= */

bool mqtt_publish_location(const char *payload)
{
    if (s_ctx.state != MQTT_STATE_CONNECTED) {
        ESP_LOGW(TAG, "Cannot publish location: not connected");
        return false;
    }
    bool ok = at_mqtt_pub(s_topic_location, payload, MQTT_QOS_LOCATION);
    if (ok) {
        ESP_LOGI(TAG, "Published location (QoS 1, %d bytes)", strlen(payload));
    }
    return ok;
}

bool mqtt_publish_heartbeat(const char *payload)
{
    if (s_ctx.state != MQTT_STATE_CONNECTED) {
        return false;
    }
    bool ok = at_mqtt_pub(s_topic_heartbeat, payload, MQTT_QOS_HEARTBEAT);
    if (ok) {
        ESP_LOGD(TAG, "Published heartbeat (QoS 0)");
    }
    return ok;
}

bool mqtt_publish_sos(const char *payload)
{
    if (s_ctx.state != MQTT_STATE_CONNECTED) {
        ESP_LOGW(TAG, "Cannot publish SOS: not connected");
        return false;
    }
    bool ok = at_mqtt_pub(s_topic_sos, payload, MQTT_QOS_SOS);
    if (ok) {
        ESP_LOGI(TAG, "Published SOS alert (QoS 1, %d bytes)", strlen(payload));
    }
    return ok;
}

bool mqtt_publish_low_battery(const char *payload)
{
    if (s_ctx.state != MQTT_STATE_CONNECTED) {
        ESP_LOGW(TAG, "Cannot publish low battery: not connected");
        return false;
    }
    bool ok = at_mqtt_pub(s_topic_low_battery, payload, MQTT_QOS_LOW_BATTERY);
    if (ok) {
        ESP_LOGI(TAG, "Published low battery alert (QoS 1)");
    }
    return ok;
}

/* ======================= PSM Configuration ======================= */

void mqtt_configure_psm(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) return;

    char cmd[128];

    // AT+CPSMS=1,,,"<ActiveTime>","<TAU>"
    // Active Time (T3324): time the device stays in connected mode after data transfer
    //   "00001000" = 10 seconds
    // TAU period (T3412): time before periodic Tracking Area Update
    //   "00000101" = 54 minutes
    snprintf(cmd, sizeof(cmd),
             "AT+CPSMS=1,,,\"%s\",\"%s\"\r\n",
             PSM_ACTIVE_TIMER, PSM_TAU_PERIOD);
    uart_send_func(cmd);

    ESP_LOGI(TAG, "PSM configured: Active=%ss, TAU=%s (54min)",
             PSM_ACTIVE_TIMER, PSM_TAU_PERIOD);

    // Also set eDRX mode for NB-IoT (optional, further power savings)
    // AT+CEDRXS=1,5,"1000"  — NB-IoT eDRX cycle of ~2.05s
    uart_send_func("AT+CEDRXS=1,5,\"1000\"\r\n");
}

/* ======================= Connection Management ======================= */

static void set_state(mqtt_state_t new_state)
{
    if (s_ctx.mutex) xSemaphoreTake(s_ctx.mutex, portMAX_DELAY);
    s_ctx.state = new_state;
    if (s_ctx.mutex) xSemaphoreGive(s_ctx.mutex);

    if (s_ctx.state_cb) {
        s_ctx.state_cb(new_state);
    }

    ESP_LOGI(TAG, "State -> %d", new_state);
}

void mqtt_start(void)
{
    if (!s_ctx.initialized) {
        ESP_LOGE(TAG, "MQTT not initialized");
        return;
    }

    if (s_ctx.state == MQTT_STATE_CONNECTED) {
        ESP_LOGW(TAG, "Already connected");
        return;
    }

    set_state(MQTT_STATE_CONNECTING);

    // Step 1: Configure MQTT parameters
    at_mqtt_conncfg();
    vTaskDelay(pdMS_TO_TICKS(500));

    // Step 2: Connect to broker
    at_mqtt_conn();

    // Connection result will be handled via mqtt_feed_response
    // when +MQTTCONNACK is received.
    // This function returns immediately; state will update async.
}

void mqtt_stop(void)
{
    send_at("AT+MQTTDISC=0\r\n");
    set_state(MQTT_STATE_DISCONNECTED);
}

void mqtt_reset_backoff(void)
{
    s_ctx.reconnect_delay_ms = RECONNECT_BASE_MS;
    ESP_LOGD(TAG, "Reconnect backoff reset to %lu ms", s_ctx.reconnect_delay_ms);
}

void mqtt_tick(void)
{
    if (!s_ctx.initialized) return;

    uint32_t now = esp_timer_get_time() / 1000; // ms

    // Handle reconnection with exponential backoff
    if (s_ctx.state == MQTT_STATE_DISCONNECTED || s_ctx.state == MQTT_STATE_ERROR) {
        uint32_t elapsed = now - s_ctx.last_reconnect_attempt;
        if (elapsed >= s_ctx.reconnect_delay_ms) {
            ESP_LOGI(TAG, "Attempting reconnect (backoff=%lu ms)", s_ctx.reconnect_delay_ms);
            mqtt_start();
            s_ctx.last_reconnect_attempt = now;

            // Exponential backoff
            s_ctx.reconnect_delay_ms *= RECONNECT_MULTIPLIER;
            if (s_ctx.reconnect_delay_ms > RECONNECT_MAX_MS) {
                s_ctx.reconnect_delay_ms = RECONNECT_MAX_MS;
            }
        }
    }
}

/* ======================= Response Parser ======================= */

void mqtt_feed_response(const char *line)
{
    if (!line) return;

    // +MQTTCONNACK: <profile>,<result>,<code>
    // result=0 success, code=0 accepted
    if (strstr(line, "+MQTTCONNACK:") != NULL) {
        int profile = 0, result = 0, code = 0;
        sscanf(line, "+MQTTCONNACK: %d,%d,%d", &profile, &result, &code);
        if (result == 0 && code == 0) {
            ESP_LOGI(TAG, "MQTT connected successfully (profile=%d)", profile);
            set_state(MQTT_STATE_CONNECTED);
            mqtt_reset_backoff();
        } else {
            ESP_LOGE(TAG, "MQTT connection failed: result=%d, code=%d", result, code);
            set_state(MQTT_STATE_ERROR);
        }
        return;
    }

    // +MQTTPUBACK: <profile>,<packet_id>,<result>
    // QoS 1 publish acknowledgement
    if (strstr(line, "+MQTTPUBACK:") != NULL) {
        int profile = 0, pkt_id = 0, result = 0;
        sscanf(line, "+MQTTPUBACK: %d,%d,%d", &profile, &pkt_id, &result);
        if (result != 0) {
            ESP_LOGW(TAG, "Publish NACK: profile=%d, pkt=%d, result=%d",
                     profile, pkt_id, result);
        }
        return;
    }

    // +MQTTDISCONNECT: <profile>,<result>
    if (strstr(line, "+MQTTDISCONNECT:") != NULL) {
        ESP_LOGW(TAG, "MQTT disconnected: %s", line);
        set_state(MQTT_STATE_DISCONNECTED);
        return;
    }

    // +MQTTSUBRECV: <profile>,<topic>,<payload_len>
    // (only if we subscribe — not used in current design but parsed for completeness)
    if (strstr(line, "+MQTTSUBRECV:") != NULL) {
        // We don't subscribe to any topics in current design
        ESP_LOGD(TAG, "Received MQTT message (ignored): %s", line);
        return;
    }

    // CONNECT (response to AT+MQTTCONN before ACK)
    if (strstr(line, "CONNECT") != NULL && strchr(line, '\n')) {
        // This is just a transitional response, ignore
        return;
    }

    // OK / ERROR (for AT command responses)
    if (strcmp(line, "OK\r\n") == 0 || strcmp(line, "OK") == 0) {
        return;
    }
    if (strstr(line, "ERROR") != NULL) {
        // Could be from any AT command, just log
        ESP_LOGD(TAG, "AT ERROR (MQTT context): %s", line);
        return;
    }
}

/* ======================= Public API ======================= */

void mqtt_init(const char *device_id,
               const char *mqtt_host,
               uint16_t    mqtt_port,
               mqtt_state_callback_t state_cb,
               mqtt_msg_callback_t   msg_cb)
{
    memset(&s_ctx, 0, sizeof(s_ctx));

    if (device_id) strncpy(s_ctx.device_id, device_id, sizeof(s_ctx.device_id) - 1);
    if (mqtt_host) strncpy(s_ctx.mqtt_host, mqtt_host, sizeof(s_ctx.mqtt_host) - 1);
    s_ctx.mqtt_port = mqtt_port;
    s_ctx.state_cb = state_cb;
    s_ctx.msg_cb = msg_cb;
    s_ctx.reconnect_delay_ms = RECONNECT_BASE_MS;
    s_ctx.state = MQTT_STATE_DISCONNECTED;

    s_ctx.mutex = xSemaphoreCreateMutex();

    build_topics();

    s_ctx.initialized = true;
    ESP_LOGI(TAG, "MQTT initialized: client=%s, broker=%s:%d",
             s_ctx.device_id, s_ctx.mqtt_host, s_ctx.mqtt_port);
}

mqtt_state_t mqtt_get_state(void)
{
    mqtt_state_t st = MQTT_STATE_DISCONNECTED;
    if (s_ctx.mutex && xSemaphoreTake(s_ctx.mutex, pdMS_TO_TICKS(10))) {
        st = s_ctx.state;
        xSemaphoreGive(s_ctx.mutex);
    }
    return st;
}

uint32_t mqtt_get_reconnect_delay(void)
{
    return s_ctx.reconnect_delay_ms;
}

bool mqtt_is_ready(void)
{
    return (s_ctx.state == MQTT_STATE_CONNECTED && s_ctx.initialized);
}

void mqtt_set_uart_send(void (*uart_send_func)(const char *cmd))
{
    s_ctx.uart_send = uart_send_func;
    if (uart_send_func) {
        ESP_LOGI(TAG, "UART send function registered");
    }
}
