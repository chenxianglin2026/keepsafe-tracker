/*
 * lbs.h — LBS (Cell ID) Interface
 *
 * Uses Air780E AT commands to retrieve cell tower information:
 *   - Cell ID, LAC, MCC, MNC via AT+CREG or AT+CENG
 *   - RSSI signal strength via AT+CSQ
 *
 * This is used for auxiliary positioning when GPS is unavailable or
 * disabled during stationary mode (power saving).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================= Cell Tower Info ======================= */
typedef struct {
    char     mcc[4];            // Mobile Country Code (e.g., "460" for China)
    char     mnc[4];            // Mobile Network Code (e.g., "00" for China Mobile)
    uint32_t lac;               // Location Area Code
    uint32_t cell_id;           // Cell ID
    int16_t  rssi_dbm;          // Received Signal Strength Indicator (dBm)
    uint8_t  ber;               // Bit Error Rate (0-7, 99=unknown)
    bool     valid;             // True if all fields are populated
} lbs_cell_info_t;

/* ======================= Public API ======================= */

/**
 * @brief Initialize the LBS module.
 * Prepares AT command buffers.
 */
void lbs_init(void);

/**
 * @brief Send AT+CSQ to get RSSI and BER.
 * Updates the internal cell info structure.
 *
 * @param uart_send_func Function pointer to send AT commands to Air780E.
 * @return true if the query succeeded.
 */
bool lbs_query_signal_strength(void (*uart_send_func)(const char *cmd));

/**
 * @brief Send AT+CREG? to get cell registration status and LAC/Cell ID.
 * Updates the internal cell info structure.
 *
 * @param uart_send_func Function pointer to send AT commands to Air780E.
 * @return true if the query succeeded and cell info is valid.
 */
bool lbs_query_cell_info(void (*uart_send_func)(const char *cmd));

/**
 * @brief Send AT+CENG? to get detailed neighbor cell info (optional, may
 * not be supported on all networks/firmware versions).
 *
 * @param uart_send_func Function pointer to send AT commands.
 * @return true if neighbor cell info was retrieved.
 */
bool lbs_query_neighbor_cells(void (*uart_send_func)(const char *cmd));

/**
 * @brief Get the latest cell info.
 * @return lbs_cell_info_t with current tower data.
 */
lbs_cell_info_t lbs_get_cell_info(void);

/**
 * @brief Format cell info as a human-readable string for JSON building.
 * Returns a pointer to a static buffer. NOT thread-safe.
 * Format: "MCC-MNC-LAC-CellID" e.g. "460-00-12345-6789"
 */
const char *lbs_format_cell_id_string(void);

/**
 * @brief Convert RSSI (AT+CSQ raw value 0-31) to dBm.
 * From 3GPP TS 27.007: dBm = -113 + 2*CSQ for CSQ 0-31
 * CSQ=99 means not detectable.
 */
int16_t lbs_csq_to_dbm(int csq_raw);

/**
 * @brief Parse an AT response line for cell information.
 * Called by the UART response handler.
 *
 * @param line A response line from the Air780E.
 */
void lbs_parse_response(const char *line);

#ifdef __cplusplus
}
#endif
