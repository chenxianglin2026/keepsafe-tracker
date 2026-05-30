#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "config.h"

static const char *TAG = "WIFI";
static esp_mqtt_client_handle_t mqtt = NULL;
static bool ok = false;

static void mqtt_ev(void *a, esp_event_base_t b, int32_t c, void *d) {
    esp_mqtt_event_handle_t e = d;
    if (e->event_id == MQTT_EVENT_CONNECTED) { ok = true; ESP_LOGI(TAG,"MQTT OK"); }
    else if (e->event_id == MQTT_EVENT_DISCONNECTED) ok = false;
}

static void wifi_ev(void *a, esp_event_base_t b, int32_t c, void *d) {
    if (b == WIFI_EVENT && c == WIFI_EVENT_STA_START) esp_wifi_connect();
    else if (b == IP_EVENT && c == IP_EVENT_STA_GOT_IP) ESP_LOGI(TAG,"WiFi OK");
}

void wifi_mqtt_init(void) {
    nvs_flash_init(); esp_netif_init(); esp_event_loop_create_default();
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t wc = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&wc);
    esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_ev,NULL,NULL);
    esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_ev,NULL,NULL);
    wifi_config_t w = {.sta={.ssid=WIFI_SSID,.password=WIFI_PASSWORD}};
    esp_wifi_set_mode(WIFI_MODE_STA); esp_wifi_set_config(WIFI_IF_STA,&w); esp_wifi_start();
    vTaskDelay(5000/portTICK_PERIOD_MS);
    char uri[128]; snprintf(uri,128,"mqtt://%s:%d",MQTT_BROKER_HOST,MQTT_BROKER_PORT);
    esp_mqtt_client_config_t mc = {.broker.address.uri=uri,.credentials.client_id=DEVICE_ID};
    mqtt = esp_mqtt_client_init(&mc);
    esp_mqtt_client_register_event(mqtt,ESP_EVENT_ANY_ID,mqtt_ev,NULL);
    esp_mqtt_client_start(mqtt);
    vTaskDelay(2000/portTICK_PERIOD_MS);
}

int wifi_mqtt_publish(const char *t, const char *d, int q) {
    if(!mqtt||!ok) return -1;
    return esp_mqtt_client_publish(mqtt,t,d,0,q,0);
}

bool wifi_mqtt_is_connected(void) { return ok; }
