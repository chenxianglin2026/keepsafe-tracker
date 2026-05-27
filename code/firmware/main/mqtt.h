/*
 * mqtt.h — MQTT Communication + PSM Power Saving
 *
 * Manages MQTT client lifecycle, PSM (Power Saving Mode) configuration,
 * and exponential-backoff reconnection.
 *
 * Topic tree (prefixed with keepsafe/v1/{device_id}/):
 *   location    — QoS 1, GPS + LBS position report
 *   heartbeat   — QoS 0, periodic keepalive
 *   sos         — QoS 1, SOS alert
 *   alert/low_battery — QoS 1, low battery alert
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= MQTT Connection State ======================= */
typedef enum {
    MQTT_STATE_DISCONNECTED = 0,
    MQTT_STATE_CONNECTING,
    MQTT_STATE_CONNECTED,
    MQTT_STATE_ERROR,
} mqtt_state_t;

/* ======================= MQTT Message Structure ======================= */
typedef struct {
    char *topic;
    char *payload;
    int   topic_len;
    int   payload_len;
    int   qos;
    bool  retain;
} mqtt_message_t;

/* ======================= Callbacks ======================= */

/**
 * @brief Callback for MQTT connection state changes.
 * Users can use this to manage LED indicators, status flags, etc.
 */
typedef void (*mqtt_state_callback_t)(mqtt_state_t state);

/**
 * @brief Callback for received MQTT messages (if we subscribe).
 * Can be NULL if no subscriptions are needed.
 */
typedef void (*mqtt_msg_callback_t)(const char *topic, int topic_len,
                                    const char *payload, int payload_len);

/* ======================= Public API ======================= */

/**
 * @brief Initialize the MQTT module.
 * Configures PSM and MQTT client parameters.
 *
 * @param device_id          Device identifier string (e.g., "KS-A1B2C3D4")
 * @param mqtt_host          MQTT broker hostname or IP
 * @param mqtt_port          MQTT broker port (usually 1883)
 * @param state_cb           Optional callback for connection state changes
 * @param msg_cb             Optional callback for received messages
 */
void mqtt_init(const char *device_id,
               const char *mqtt_host,
               uint16_t    mqtt_port,
               mqtt_state_callback_t state_cb,
               mqtt_msg_callback_t   msg_cb);

/**
 * @brief Start MQTT connection.
 * Should be called after network is up.
 * Implements exponential backoff on failure.
 */
void mqtt_start(void);

/**
 * @brief Stop MQTT connection and clean up.
 */
void mqtt_stop(void);

/**
 * @brief Publish a location report (QoS 1).
 * @param payload JSON payload (null-terminated)
 * @return true if published successfully (queued if connected)
 */
bool mqtt_publish_location(const char *payload);

/**
 * @brief Publish a heartbeat (QoS 0).
 * @param payload JSON payload
 * @return true if published successfully
 */
bool mqtt_publish_heartbeat(const char *payload);

/**
 * @brief Publish an SOS alert (QoS 1).
 * @param payload JSON payload
 * @return true if published successfully
 */
bool mqtt_publish_sos(const char *payload);

/**
 * @brief Publish a low battery alert (QoS 1).
 * @param payload JSON payload
 * @return true if published successfully
 */
bool mqtt_publish_low_battery(const char *payload);

/**
 * @brief Get current MQTT connection state.
 */
mqtt_state_t mqtt_get_state(void);

/**
 * @brief Get the current reconnection delay (ms).
 * Useful for power management — if delay is long, we can deep-sleep.
 */
uint32_t mqtt_get_reconnect_delay(void);

/**
 * @brief Reset reconnection backoff to minimum (e.g., after successful connect).
 */
void mqtt_reset_backoff(void);

/**
 * @brief Configure PSM (Power Saving Mode) on Air780E.
 * Must be called after network registration.
 *
 * @param uart_send_func Function to send AT commands to Air780E.
 */
void mqtt_configure_psm(void (*uart_send_func)(const char *cmd));

/**
 * @brief Check if MQTT has a session and can publish.
 * @return true if connected and ready to publish.
 */
bool mqtt_is_ready(void);

/**
 * @brief MQTT periodic tick — call from main loop.
 * Handles reconnection timing and keepalive.
 */
void mqtt_tick(void);

/**
 * @brief Set the UART send function (needed for AT command dispatch).
 * The MQTT module uses this to send AT+MQTTCONN, AT+MQTTPUB, etc.
 */
void mqtt_set_uart_send(void (*uart_send_func)(const char *cmd));

/**
 * @brief Feed an AT response line into MQTT parser.
 * Called by UART response handler. Parses +MQTTCONNACK, +MQTTPUBACK, etc.
 */
void mqtt_feed_response(const char *line);

#ifdef __cplusplus
}
#endif
