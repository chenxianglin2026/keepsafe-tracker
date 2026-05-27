/*
 * gps.h — GPS NMEA Parsing Interface
 *
 * Parses $GNGGA and $GNRMC sentences from Air780E GNSS module.
 * Provides a normalized coordinate structure for use by mqtt.c and sos.c.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= GPS Fix Quality (from GGA) ======================= */
typedef enum {
    GPS_FIX_NONE            = 0,
    GPS_FIX_SPS             = 1,    // Standard Positioning Service (GPS SPS)
    GPS_FIX_DGPS            = 2,    // Differential GPS
    GPS_FIX_PPS             = 3,    // Precise Positioning Service (PPS)
    GPS_FIX_RTK             = 4,    // Real Time Kinematic
    GPS_FIX_FLOAT_RTK       = 5,    // Float RTK
    GPS_FIX_ESTIMATED       = 6,    // Estimated (dead reckoning)
    GPS_FIX_MANUAL          = 7,
    GPS_FIX_SIMULATION      = 8,
} gps_fix_type_t;

/* ======================= Normalized Location Structure ======================= */
typedef struct {
    double      latitude;            // Decimal degrees (positive = N, negative = S)
    double      longitude;           // Decimal degrees (positive = E, negative = W)
    double      altitude;            // Meters above mean sea level
    float       speed;               // Ground speed in m/s (from RMC)
    float       heading;             // True course in degrees (from RMC)
    float       accuracy_hdop;       // Horizontal Dilution of Precision
    uint8_t     satellites;          // Number of satellites in use
    gps_fix_type_t fix_type;         // GPS fix quality
    bool        has_fix;             // True if we have a valid 3D fix

    // UTC time from RMC sentence
    uint8_t     hour;
    uint8_t     minute;
    uint8_t     second;
    uint16_t    millisecond;

    // Unix timestamp (approximate, computed from RMC date + time if available)
    uint32_t    timestamp_unix;
} gps_location_t;

/* ======================= Public API ======================= */

/**
 * @brief Initialize the GPS NMEA parser.
 * Must be called once before feeding data.
 */
void gps_parser_init(void);

/**
 * @brief Feed a raw NMEA sentence (one line) into the parser.
 *
 * The string must include the leading '$' and trailing '\r\n' or '\n'.
 * The parser will silently ignore non-GGA/non-RMC sentences.
 *
 * @param line Null-terminated NMEA sentence
 */
void gps_parse_line(const char *line);

/**
 * @brief Get the latest parsed GPS location.
 *
 * @return gps_location_t with current fix data.
 *         Check has_fix before trusting lat/lng.
 */
gps_location_t gps_get_location(void);

/**
 * @brief Check if a valid fix exists (non-zero satellites && fix_type > 0).
 */
bool gps_has_valid_fix(void);

/**
 * @brief Get GPS timestamp as Unix epoch (seconds since 1970-01-01).
 * Returns 0 if GPS time is not yet available.
 */
uint32_t gps_get_unix_timestamp(void);

/**
 * @brief Reset parser state (e.g., after GPS is powered down and back up).
 */
void gps_parser_reset(void);

#ifdef __cplusplus
}
#endif
