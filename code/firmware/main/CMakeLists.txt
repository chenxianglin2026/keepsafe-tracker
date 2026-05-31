idf_component_register(SRCS "main.c" "gps.c" "mqtt.c" "sos.c" "led.c" "lbs.c" "power.c" "accel.c" "wifi_mqtt.c"
                    INCLUDE_DIRS "."
                    REQUIRES nvs_flash esp_wifi esp_mqtt esp_event)
