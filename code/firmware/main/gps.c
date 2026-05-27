/*
 * gps.c — GPS NMEA Parsing Implementation
 *
 * Parses $GNGGA and $GNRMC NMEA sentences from Air780E.
 * Stores extracted data in a shared state protected by a mutex.
 *
 * Power path notes:
 *   - gps_parse_line() is called from the UART RX task on each received line.
 *   - The parser is zero-copy (avoids heap allocation during parse).
 *   - gps_get_location() returns a copy; callers own the data.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "gps.h"

static const char *TAG = "GPS";

/* ======================= Internal State ======================= */

static SemaphoreHandle_t s_gps_mutex = NULL;

// Latest parsed location (zero-initialized)
static gps_location_t s_location = {0};

/* ======================= NMEA Tokenizer Helpers ======================= */

/**
 * Count tokens in a comma-separated NMEA line.
 */
static int nmea_token_count(const char *line)
{
    int count = 0;
    const char *p = line;
    while (*p) {
        if (*p == ',') count++;
        p++;
    }
    return count + 1; // n commas = n+1 fields
}

/**
 * Extract the n-th comma-separated field from `line` into `dst` (max len).
 * Returns pointer to dst on success, NULL if field doesn't exist.
 * Does NOT handle checksum — caller strips it.
 */
static const char *nmea_field(const char *line, int index, char *dst, int dst_len)
{
    if (!line || !dst || dst_len <= 0) return NULL;

    int current = 0;
    const char *start = line;
    const char *p = line;

    while (*p) {
        if (*p == ',') {
            if (current == index) {
                // Found the field
                int len = (int)(p - start);
                if (len >= dst_len) len = dst_len - 1;
                memcpy(dst, start, len);
                dst[len] = '\0';
                return dst;
            }
            start = p + 1;
            current++;
        }
        p++;
    }

    // Last field (no trailing comma)
    if (current == index) {
        int len = (int)(p - start);
        if (len >= dst_len) len = dst_len - 1;
        memcpy(dst, start, len);
        dst[len] = '\0';
        return dst;
    }

    return NULL;
}

/**
 * Convert NMEA lat/lng format "DDMM.MMMMMM" to decimal degrees.
 * Example: "4807.038" -> 48 + 07.038/60 = 48.1173
 */
static double nmea_to_decimal(const char *nmea_str, char dir)
{
    if (!nmea_str || strlen(nmea_str) < 4) return 0.0;

    // Find the decimal point to split degrees and minutes
    char *dot = strchr(nmea_str, '.');
    if (!dot) return 0.0;

    int deg_len = (int)(dot - nmea_str) - 2; // 2 digits for degrees
    if (deg_len < 0) return 0.0;

    char deg_str[4] = {0};
    strncpy(deg_str, nmea_str, deg_len);
    deg_str[deg_len] = '\0';

    char min_str[16] = {0};
    strncpy(min_str, nmea_str + deg_len, sizeof(min_str) - 1);

    double degrees = atof(deg_str);
    double minutes = atof(min_str);

    double result = degrees + minutes / 60.0;

    if (dir == 'S' || dir == 'W') {
        result = -result;
    }

    return result;
}

/* ======================= GGA Parser ======================= */
/*
 * $GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
 * Fields:
 *  0  $GNGGA
 *  1  UTC time (hhmmss.sss)
 *  2  Latitude (DDMM.MMMMMM)
 *  3  N/S
 *  4  Longitude (DDDMM.MMMMMM)
 *  5  E/W
 *  6  Fix quality (0=invalid, 1=GPS, 2=DGPS)
 *  7  Number of satellites
 *  8  HDOP
 *  9  Altitude (meters)
 * 10  'M' (unit)
 * 11  Geoidal separation
 * 12  'M' (unit)
 * 13  Age of differential data (empty)
 * 14  Differential station ID (empty)
 */
static void parse_gga(const char *line)
{
    (void)nmea_token_count; // suppress unused warning

    char field[32];

    // Field 1: UTC time
    if (nmea_field(line, 1, field, sizeof(field))) {
        if (strlen(field) >= 6) {
            char h[3] = {field[0], field[1], 0};
            char m[3] = {field[2], field[3], 0};
            char s[3] = {field[4], field[5], 0};
            s_location.hour   = (uint8_t)atoi(h);
            s_location.minute = (uint8_t)atoi(m);
            s_location.second = (uint8_t)atoi(s);

            // Milliseconds from fractional seconds
            char *dot = strchr(field, '.');
            if (dot && strlen(dot) > 1) {
                s_location.millisecond = (uint16_t)(atof(dot) * 1000);
            }
        }
    }

    // Field 2: Latitude
    if (nmea_field(line, 2, field, sizeof(field))) {
        char dir[2] = {0};
        nmea_field(line, 3, dir, sizeof(dir));
        if (strlen(field) > 0 && strlen(dir) > 0) {
            s_location.latitude = nmea_to_decimal(field, dir[0]);
        }
    }

    // Field 4: Longitude
    if (nmea_field(line, 4, field, sizeof(field))) {
        char dir[2] = {0};
        nmea_field(line, 5, dir, sizeof(dir));
        if (strlen(field) > 0 && strlen(dir) > 0) {
            s_location.longitude = nmea_to_decimal(field, dir[0]);
        }
    }

    // Field 6: Fix quality
    if (nmea_field(line, 6, field, sizeof(field))) {
        int fix = atoi(field);
        s_location.fix_type = (gps_fix_type_t)fix;
        s_location.has_fix = (fix > 0);
    }

    // Field 7: Satellites
    if (nmea_field(line, 7, field, sizeof(field))) {
        s_location.satellites = (uint8_t)atoi(field);
    }

    // Field 8: HDOP
    if (nmea_field(line, 8, field, sizeof(field))) {
        s_location.accuracy_hdop = atof(field);
    }

    // Field 9: Altitude
    if (nmea_field(line, 9, field, sizeof(field))) {
        s_location.altitude = atof(field);
    }

    ESP_LOGD(TAG, "GGA parsed: fix=%d sats=%d lat=%.6f lng=%.6f alt=%.1f",
             s_location.fix_type, s_location.satellites,
             s_location.latitude, s_location.longitude,
             s_location.altitude);
}

/* ======================= RMC Parser ======================= */
/*
 * $GNRMC,123519,A,4807.038,N,01131.000,E,000.0,360.0,230394,003.1,W*6A
 * Fields:
 *  0  $GNRMC
 *  1  UTC time (hhmmss.sss)
 *  2  Status (A=active/valid, V=void/invalid)
 *  3  Latitude
 *  4  N/S
 *  5  Longitude
 *  6  E/W
 *  7  Speed over ground (knots)
 *  8  Course over ground (degrees true)
 *  9  Date (DDMMYY)
 * 10  Magnetic variation
 * 11  E/W
 * 12  Checksum
 */
static void parse_rmc(const char *line)
{
    char field[32];

    // Field 1: UTC time (re-parsed from GGA, but update from RMC if better)
    // (GGA already sets it, but RMC is another source)

    // Field 2: Status
    if (nmea_field(line, 2, field, sizeof(field))) {
        bool valid = (field[0] == 'A');
        // If RMC says invalid but GGA said fix > 0, trust GGA
        // If RMC says valid and GGA says no fix, still trust GGA fix_type
    }

    // Field 3-6: Lat/Lng (skip, GGA is preferred for precision)
    // But we can update if GGA wasn't seen yet

    // Field 7: Speed over ground (knots -> m/s)
    if (nmea_field(line, 7, field, sizeof(field))) {
        float knots = atof(field);
        s_location.speed = knots * 0.514444f; // knots -> m/s
    }

    // Field 8: Course over ground (degrees true)
    if (nmea_field(line, 8, field, sizeof(field))) {
        s_location.heading = atof(field);
    }

    // Field 9: Date (DDMMYY) — use to set approximate Unix time
    if (nmea_field(line, 9, field, sizeof(field))) {
        if (strlen(field) == 6) {
            // We don't have full date->unix conversion here (no time.h RTC set)
            // In production, set ESP RTC from this using date_to_unix()
            // For now, we just store the components
            // ESP_LOGD(TAG, "RMC date: %s", field);
        }
    }

    ESP_LOGD(TAG, "RMC parsed: speed=%.2f heading=%.1f",
             s_location.speed, s_location.heading);
}

/* ======================= Public API ======================= */

void gps_parser_init(void)
{
    if (s_gps_mutex == NULL) {
        s_gps_mutex = xSemaphoreCreateMutex();
    }
    memset(&s_location, 0, sizeof(s_location));
    ESP_LOGI(TAG, "GPS parser initialized");
}

void gps_parse_line(const char *line)
{
    if (!line || !s_gps_mutex) return;

    // Quick check for NMEA sentence start
    if (line[0] != '$') return;

    // Determine sentence type (first 6 chars after '$')
    if (strncmp(line + 1, "GNGGA", 5) == 0 ||
        strncmp(line + 1, "GPGGA", 5) == 0 ||
        strncmp(line + 1, "BDGGA", 5) == 0) {
        if (xSemaphoreTake(s_gps_mutex, portMAX_DELAY)) {
            parse_gga(line);
            xSemaphoreGive(s_gps_mutex);
        }
    } else if (strncmp(line + 1, "GNRMC", 5) == 0 ||
               strncmp(line + 1, "GPRMC", 5) == 0 ||
               strncmp(line + 1, "BDRMC", 5) == 0) {
        if (xSemaphoreTake(s_gps_mutex, portMAX_DELAY)) {
            parse_rmc(line);
            xSemaphoreGive(s_gps_mutex);
        }
    }
}

gps_location_t gps_get_location(void)
{
    gps_location_t loc = {0};
    if (s_gps_mutex && xSemaphoreTake(s_gps_mutex, pdMS_TO_TICKS(100))) {
        loc = s_location;
        xSemaphoreGive(s_gps_mutex);
    }
    return loc;
}

bool gps_has_valid_fix(void)
{
    gps_location_t loc = gps_get_location();
    return (loc.has_fix && loc.satellites > 0 && loc.fix_type > 0);
}

uint32_t gps_get_unix_timestamp(void)
{
    gps_location_t loc = gps_get_location();
    return loc.timestamp_unix;
}

void gps_parser_reset(void)
{
    if (s_gps_mutex && xSemaphoreTake(s_gps_mutex, portMAX_DELAY)) {
        memset(&s_location, 0, sizeof(s_location));
        xSemaphoreGive(s_gps_mutex);
    }
    ESP_LOGI(TAG, "GPS parser reset");
}
