/*
 * lbs.c — LBS Cell ID Implementation
 *
 * Parses AT command responses from Air780E:
 *   AT+CSQ  -> RSSI + BER
 *   AT+CREG? -> LAC + Cell ID
 *   AT+COPS? -> MCC + MNC (optional, we extract from CREG if possible)
 *
 * Power path note:
 *   - LBS queries are only done when GPS is OFF (stationary mode) for
 *     auxiliary positioning, or as fallback when GPS fix times out.
 *   - Each AT command takes ~100-300ms and consumes ~50mA during active TX.
 *   - Batch queries together to minimize wake time.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "lbs.h"

static const char *TAG = "LBS";

/* ======================= Internal State ======================= */

static SemaphoreHandle_t s_lbs_mutex = NULL;
static lbs_cell_info_t s_cell_info = {0};
static char s_cell_id_string[32] = {0}; // Format: "MCC-MNC-LAC-CellID"

/* ======================= Helper Functions ======================= */

int16_t lbs_csq_to_dbm(int csq_raw)
{
    if (csq_raw == 99) return -999; // not detectable
    if (csq_raw < 0) csq_raw = 0;
    if (csq_raw > 31) csq_raw = 31;
    return (int16_t)(-113 + 2 * csq_raw);
}

/**
 * Strip trailing whitespace/CR/LF from a string in-place.
 */
static void strip_crlf(char *s)
{
    if (!s) return;
    size_t len = strlen(s);
    while (len > 0 && (s[len-1] == '\r' || s[len-1] == '\n' || s[len-1] == ' ')) {
        s[--len] = '\0';
    }
}

/**
 * Find a substring in a larger string, case-insensitive.
 */
static const char *stristr(const char *haystack, const char *needle)
{
    if (!haystack || !needle) return NULL;
    size_t nlen = strlen(needle);
    while (*haystack) {
        if (strncasecmp(haystack, needle, nlen) == 0) {
            return haystack;
        }
        haystack++;
    }
    return NULL;
}

/* ======================= Response Parser ======================= */

void lbs_parse_response(const char *line)
{
    if (!line) return;

    // Parse: +CSQ: <rssi>,<ber>
    if (strstr(line, "+CSQ:") != NULL) {
        int csq_raw = 0, ber = 0;
        if (sscanf(line, "+CSQ: %d,%d", &csq_raw, &ber) >= 1) {
            if (xSemaphoreTake(s_lbs_mutex, portMAX_DELAY)) {
                s_cell_info.rssi_dbm = lbs_csq_to_dbm(csq_raw);
                s_cell_info.ber = (uint8_t)(ber & 0xFF);
                ESP_LOGD(TAG, "CSQ: raw=%d, rssi=%d dBm, ber=%d",
                         csq_raw, s_cell_info.rssi_dbm, s_cell_info.ber);
                xSemaphoreGive(s_lbs_mutex);
            }
        }
        return;
    }

    // Parse: +CREG: <n>,<stat>[,<lac>,<ci>[,<AcT>]]
    // Or: +CGREG: ... for packet-switched registration
    if (strstr(line, "+CREG:") != NULL || strstr(line, "+CGREG:") != NULL) {
        int n = 0, stat = 0;
        char lac_str[8] = {0}, ci_str[8] = {0};
        int parsed = sscanf(line, "%*[^:]: %d,%d,\"%7[^\"]\",\"%7[^\"]\"",
                            &n, &stat, lac_str, ci_str);

        if (parsed < 4) {
            // Try without quotes
            parsed = sscanf(line, "%*[^:]: %d,%d,%7s,%7s",
                            &n, &stat, lac_str, ci_str);
        }

        if (parsed >= 4) {
            if (xSemaphoreTake(s_lbs_mutex, portMAX_DELAY)) {
                s_cell_info.lac = (uint32_t)strtol(lac_str, NULL, 16);
                s_cell_info.cell_id = (uint32_t)strtol(ci_str, NULL, 16);
                s_cell_info.valid = (stat == 1 || stat == 5); // registered, home/roaming
                ESP_LOGD(TAG, "CREG: stat=%d, LAC=0x%04lX, CellID=0x%08lX",
                         stat, s_cell_info.lac, s_cell_info.cell_id);
                xSemaphoreGive(s_lbs_mutex);
            }
        }
        return;
    }

    // Parse: +COPS: <mode>[,<format>,<oper>[,<Act>]]
    // e.g. +COPS: 0,0,"CHINA MOBILE",7
    if (strstr(line, "+COPS:") != NULL) {
        // MCC/MNC extraction from operator name not reliable;
        // we rely on CREG for LAC/CI and set MCC/MNC separately
        // via a dedicated AT+COPS=3,2; AT+COPS? sequence if needed.
        // For now, just log.
        ESP_LOGD(TAG, "COPS response: %s", line);
        return;
    }

    // Parse: +CENG: <n>,<cell1>,<cell2>,...
    // Format: <mcc>,<mnc>,<lac>,<cell_id>,<rssi>
    if (strstr(line, "+CENG:") != NULL) {
        // Neighbor cell parsing - detailed implementation
        // Format: +CENG: 0,"460,00,1234,56789,-85","...","..."
        // This is network/firmware-specific
        ESP_LOGD(TAG, "CENG response: %s", line);

        // Try to extract MCC/MNC from first cell entry
        char first_cell[64] = {0};
        // Pattern: +CENG: 0,"460,00,...
        const char *q1 = strchr(line, '"');
        if (q1) {
            const char *q2 = strchr(q1 + 1, '"');
            if (q2) {
                int len = (int)(q2 - q1 - 1);
                if (len > 0 && len < (int)sizeof(first_cell)) {
                    strncpy(first_cell, q1 + 1, len);
                    first_cell[len] = '\0';
                    // Parse fields from first_cell
                    int mcc = 0, mnc = 0;
                    if (sscanf(first_cell, "%d,%d", &mcc, &mnc) == 2) {
                        if (xSemaphoreTake(s_lbs_mutex, portMAX_DELAY)) {
                            snprintf(s_cell_info.mcc, sizeof(s_cell_info.mcc), "%d", mcc);
                            snprintf(s_cell_info.mnc, sizeof(s_cell_info.mnc), "%d", mnc);
                            xSemaphoreGive(s_lbs_mutex);
                        }
                    }
                }
            }
        }
        return;
    }
}

/* ======================= AT Command Builders ======================= */

bool lbs_query_signal_strength(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) return false;
    uart_send_func("AT+CSQ\r\n");
    return true;
}

bool lbs_query_cell_info(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) return false;
    // Request registration info
    uart_send_func("AT+CREG?\r\n");
    // Also request operator selection for MCC/MNC
    uart_send_func("AT+COPS=3,2\r\n"); // Set format: numeric
    uart_send_func("AT+COPS?\r\n");
    return true;
}

bool lbs_query_neighbor_cells(void (*uart_send_func)(const char *cmd))
{
    if (!uart_send_func) return false;
    uart_send_func("AT+CENG=0,1\r\n"); // Enable neighbor cell reporting
    uart_send_func("AT+CENG?\r\n");
    return true;
}

/* ======================= Public API ======================= */

void lbs_init(void)
{
    if (s_lbs_mutex == NULL) {
        s_lbs_mutex = xSemaphoreCreateMutex();
    }

    if (xSemaphoreTake(s_lbs_mutex, portMAX_DELAY)) {
        memset(&s_cell_info, 0, sizeof(s_cell_info));
        // Default MCC/MNC - set from actual network registration
        strncpy(s_cell_info.mcc, "460", sizeof(s_cell_info.mcc) - 1);
        strncpy(s_cell_info.mnc, "00", sizeof(s_cell_info.mnc) - 1);
        s_cell_info.rssi_dbm = -999;
        s_cell_info.ber = 99;
        xSemaphoreGive(s_lbs_mutex);
    }

    ESP_LOGI(TAG, "LBS module initialized");
}

lbs_cell_info_t lbs_get_cell_info(void)
{
    lbs_cell_info_t info = {0};
    if (s_lbs_mutex && xSemaphoreTake(s_lbs_mutex, pdMS_TO_TICKS(100))) {
        info = s_cell_info;
        xSemaphoreGive(s_lbs_mutex);
    }
    return info;
}

const char *lbs_format_cell_id_string(void)
{
    if (s_lbs_mutex && xSemaphoreTake(s_lbs_mutex, pdMS_TO_TICKS(100))) {
        snprintf(s_cell_id_string, sizeof(s_cell_id_string),
                 "%s-%s-%lu-%lu",
                 s_cell_info.mcc,
                 s_cell_info.mnc,
                 (unsigned long)s_cell_info.lac,
                 (unsigned long)s_cell_info.cell_id);
        xSemaphoreGive(s_lbs_mutex);
    }
    return s_cell_id_string;
}
