#ifndef WIFI_MQTT_H
#define WIFI_MQTT_H
#include <stdbool.h>
void wifi_mqtt_init(void);
int wifi_mqtt_publish(const char *t, const char *d, int q);
bool wifi_mqtt_is_connected(void);
#endif
