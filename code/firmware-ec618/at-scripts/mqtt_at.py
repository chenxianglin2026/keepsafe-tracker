#!/usr/bin/env python3
"""
mqtt_at.py — KeepSafe MQTT via AT Commands (Air780E/Air780EG AT Firmware)

Uses Air780E built-in MQTT AT command set:
  AT+MQTTCONNCFG — configure MQTT connection parameters
  AT+MQTTCONN   — connect to broker
  AT+MQTTPUB    — publish message
  AT+MQTTSUB    — subscribe to topic (for downlink)
  AT+MQTTDISC   — disconnect

IMPORTANT: These AT commands are only available on the AT firmware variant,
NOT on the LuatOS firmware that ships by default on Air780EG.
If your module runs LuatOS, use the LuatOS MQTT library instead (luatos/mqtt.lua).

Prerequisites:
  pip3 install pyserial

Usage:
  python3 mqtt_at.py --port /dev/cu.usbmodem0000000000013   # Run MQTT flow on specified port
  python3 mqtt_at.py --auto                                   # Auto-detect Air780EG port
  python3 mqtt_at.py --port /dev/cu.xxx --publish '{"test":1}' # Publish custom payload
  python3 mqtt_at.py --list                                   # List available serial ports
"""

import serial
import serial.tools.list_ports
import sys
import time
import argparse
import json as json_mod
import re
from typing import Optional, Tuple


# ============================================================
# Configuration
# ============================================================

MQTT_BROKER_HOST = "43.163.5.90"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID   = "KS-TEST-EC618"       # Test device ID
MQTT_KEEPALIVE   = 300                   # seconds
MQTT_CLEAN_SESSION = 1
MQTT_QOS_LOCATION  = 1
MQTT_QOS_HEARTBEAT = 0
MQTT_QOS_SOS       = 1

# Topic format
TOPIC_LOCATION   = f"keepsafe/v1/{MQTT_CLIENT_ID}/location"
TOPIC_HEARTBEAT  = f"keepsafe/v1/{MQTT_CLIENT_ID}/heartbeat"
TOPIC_SOS        = f"keepsafe/v1/{MQTT_CLIENT_ID}/sos"
TOPIC_LOW_BATTERY = f"keepsafe/v1/{MQTT_CLIENT_ID}/alert/low_battery"
TOPIC_DOWNLINK   = f"keepsafe/v1/{MQTT_CLIENT_ID}/cmd"

# APN / PDP
APN_NAME = "ctnet"                       # China Telecom
PDP_CID  = 1

# PSM
PSM_ACTIVE_TIMER = "00001000"            # T3324: 10 seconds
PSM_TAU_PERIOD   = "00000101"            # T3412: 54 minutes

# Serial
DEFAULT_BAUD   = 115200
DEFAULT_TIMEOUT = 1.0
AT_CMD_TIMEOUT  = 10.0                   # Some commands (CONN) take longer

# ============================================================
# Retry / Reconnection Configuration
# ============================================================

MAX_RETRIES         = 3                  # Max retries per individual AT command
RETRY_DELAY_BASE    = 0.5                # Base delay between retries (seconds)
RETRY_DELAY_MAX     = 10.0               # Maximum delay between retries
RETRY_BACKOFF       = 2.0                # Exponential backoff multiplier

MAX_STEP_RETRIES    = 3                  # Max retries per flow step (e.g., PDP setup)
RECONNECT_RETRIES   = 5                  # Max MQTT connect retries

# Steps that can be retried if they fail
RETRYABLE_STEPS = {
    "AT": True,
    "SIM": True,
    "NETWORK": True,
    "PDP": True,
    "PSM": False,       # PSM is optional, don't retry
    "MQTT_CFG": True,
    "MQTT_CONN": True,
}


# ============================================================
# Serial Port Detection
# ============================================================

def list_ports():
    """List all available serial ports."""
    ports = serial.tools.list_ports.comports()
    return sorted(ports, key=lambda p: p.device)


def find_air780eg_port():
    """Auto-detect Air780EG serial port by sending AT and checking response."""
    for port in list_ports():
        device = port.device
        # Prefer USB modem / USB serial devices
        if not ("usbmodem" in device or "usbserial" in device or "ttyUSB" in device):
            continue
        try:
            ser = serial.Serial(device, DEFAULT_BAUD, timeout=2.0)
            ser.reset_input_buffer()
            ser.write(b"AT\r\n")
            time.sleep(0.5)
            response = ser.read(ser.in_waiting or 256).decode("utf-8", errors="replace")
            ser.close()
            if "OK" in response:
                print(f"[DETECT] Found Air780EG at {device}")
                return device
        except Exception:
            continue
    return None


# ============================================================
# AT Command Engine
# ============================================================

class ATSession:
    """Manage an AT command session over a serial port with retry support."""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD,
                 timeout: float = DEFAULT_TIMEOUT):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self._consecutive_errors = 0

    def connect(self) -> bool:
        """Open the serial port with retries."""
        for attempt in range(MAX_RETRIES):
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
                self.ser.reset_input_buffer()
                print(f"[SERIAL] Opened {self.port} @ {self.baud} baud")
                return True
            except Exception as e:
                delay = min(RETRY_DELAY_BASE * (RETRY_BACKOFF ** attempt), RETRY_DELAY_MAX)
                print(f"[ERROR] Cannot open {self.port}: {e}")
                if attempt < MAX_RETRIES - 1:
                    print(f"[RETRY] Attempt {attempt + 1}/{MAX_RETRIES}, waiting {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    return False
        return False

    def close(self):
        """Close the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"[SERIAL] Closed {self.port}")

    def _recover_serial(self) -> bool:
        """Attempt to recover a misbehaving serial connection by closing and reopening."""
        print("[SERIAL] Attempting serial recovery...")
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            time.sleep(1.0)
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.ser.reset_input_buffer()
            # Verify with basic AT
            self.ser.write(b"AT\r\n")
            self.ser.flush()
            time.sleep(0.5)
            resp = self.ser.read(self.ser.in_waiting or 256).decode("utf-8", errors="replace")
            if "OK" in resp:
                print("[SERIAL] Recovery successful")
                self._consecutive_errors = 0
                return True
        except Exception as e:
            print(f"[SERIAL] Recovery failed: {e}")
        return False

    def send_at(self, cmd: str, timeout: float = AT_CMD_TIMEOUT,
                retries: int = MAX_RETRIES) -> Tuple[bool, str]:
        """
        Send an AT command and wait for response. Retries on failure.
        Returns (success, full_response_string).
        """
        if not self.ser or not self.ser.is_open:
            return False, "ERROR: serial port not open"

        # Ensure command ends with \r\n
        if not cmd.endswith("\r\n"):
            cmd = cmd.rstrip() + "\r\n"

        last_error = ""
        for attempt in range(retries):
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode("utf-8"))
                self.ser.flush()
            except Exception as e:
                print(f"[AT] Write error: {e}")
                if not self._recover_serial():
                    return False, f"ERROR: write failed and recovery failed: {e}"
                continue

            # Read response with timeout
            self.ser.timeout = timeout
            response_lines = []
            start = time.time()
            while True:
                try:
                    line = self.ser.readline()
                except Exception as e:
                    print(f"[AT] Read error: {e}")
                    break

                if line:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        response_lines.append(decoded)
                # Stop when we see OK, ERROR, or timeout
                full = "\n".join(response_lines)
                if "OK" in full or "ERROR" in full:
                    break
                if "CONNECT" in full and "OK" not in full:
                    if time.time() - start > 3.0:
                        break
                if time.time() - start > timeout:
                    break

            full_response = "\n".join(response_lines)
            success = "OK" in full_response and "ERROR" not in full_response

            if success:
                self._consecutive_errors = 0
                return True, full_response

            # Failed this attempt
            last_error = full_response or "no response"
            self._consecutive_errors += 1

            if attempt < retries - 1:
                delay = min(RETRY_DELAY_BASE * (RETRY_BACKOFF ** attempt), RETRY_DELAY_MAX)
                print(f"[AT] Command failed (attempt {attempt + 1}/{retries}), "
                      f"retrying in {delay:.1f}s...")
                time.sleep(delay)

            # If we have consecutive errors, try serial recovery
            if self._consecutive_errors >= 3:
                if not self._recover_serial():
                    return False, f"ERROR: {last_error} (serial recovery failed)"
                self._consecutive_errors = 0

        return False, f"ERROR: {last_error} (all {retries} retries exhausted)"

    # ── AT command wrappers ──

    def at_basic(self) -> bool:
        """Test basic AT communication."""
        ok, resp = self.send_at("AT")
        print(f"[AT] AT -> {'OK' if ok else 'FAIL'}: {resp}")
        return ok

    def at_check_firmware(self) -> Tuple[bool, str]:
        """Check firmware version / type via AT+CGMR."""
        ok, resp = self.send_at("AT+CGMR")
        fw_type = "UNKNOWN"
        if "LuatOS" in resp:
            fw_type = "LuatOS"
        elif "AT" in resp and "AirM2M" in resp:
            fw_type = "AT_FIRMWARE"
        print(f"[FW] Firmware type: {fw_type}, response: {resp}")
        return ok, fw_type

    def at_check_sim(self) -> bool:
        """Check SIM card status via AT+CPIN?."""
        ok, resp = self.send_at("AT+CPIN?")
        ready = "+CPIN: READY" in resp
        print(f"[SIM] SIM status: {'READY' if ready else 'NOT READY'}: {resp}")
        return ready

    def at_csq(self) -> Optional[int]:
        """Get signal strength via AT+CSQ."""
        ok, resp = self.send_at("AT+CSQ")
        match = re.search(r'\+CSQ:\s*(\d+)', resp)
        if match:
            rssi = int(match.group(1))
            print(f"[NET] Signal strength: {rssi} (0-31, 99=no signal)")
            return rssi
        return None

    def at_network_reg(self) -> bool:
        """Check network registration via AT+CEREG?."""
        ok, resp = self.send_at("AT+CEREG?")
        registered = False
        # +CEREG: 0,1 or +CEREG: 0,5
        if re.search(r'\+CEREG:\s*\d+,\s*[15]', resp):
            registered = True
        print(f"[NET] Network registration: {'REGISTERED' if registered else 'NOT REGISTERED'}")
        return registered

    def at_pdp_setup(self) -> bool:
        """Configure and activate PDP context with retries."""
        # Configure PDP context
        ok, resp = self.send_at(f'AT+CGDCONT={PDP_CID},"IP","{APN_NAME}"')
        print(f"[PDP] CGDCONT: {'OK' if ok else 'FAIL'}")
        if not ok:
            return False

        # Activate PDP
        ok, resp = self.send_at(f"AT+CGACT=1,{PDP_CID}")
        print(f"[PDP] CGACT: {'OK' if ok else 'FAIL'}")
        if not ok:
            return False

        # Check IP
        ok, resp = self.send_at(f"AT+CGPADDR={PDP_CID}")
        ip_match = re.search(r'\+CGPADDR:\s*\d+,\s*"?([\d.]+)"?', resp)
        if ip_match:
            ip = ip_match.group(1)
            print(f"[PDP] Got IP: {ip}")
            return True
        else:
            print("[PDP] No IP address obtained")
            return False

    def at_psm_configure(self) -> bool:
        """Configure PSM (Power Saving Mode)."""
        cmd = f'AT+CPSMS=1,,,"{PSM_ACTIVE_TIMER}","{PSM_TAU_PERIOD}"'
        ok, resp = self.send_at(cmd)
        print(f"[PSM] CPSMS: {'OK' if ok else 'FAIL'}")
        return ok

    def at_cgnsinf(self) -> Optional[dict]:
        """Get GNSS navigation info via AT+CGNSINF.
        Returns parsed GPS data dict or None on failure."""
        ok, resp = self.send_at("AT+CGNSINF", timeout=5.0)
        if not ok:
            print(f"[GPS] CGNSINF failed: {resp}")
            return None

        # Parse: +CGNSINF: mode,lat,lng,alt,speed,course,,sv_count,hdop,pdop,vdop,utc
        match = re.search(r'\+CGNSINF:\s*(.+)', resp)
        if not match:
            print(f"[GPS] CGNSINF parse error: {resp}")
            return None

        fields = match.group(1).split(",")
        if len(fields) < 10:
            print(f"[GPS] CGNSINF too few fields: {len(fields)}")
            return None

        try:
            mode = int(fields[0]) if fields[0].strip() else 0
            lat = float(fields[1]) if fields[1].strip() else 0.0
            lng = float(fields[2]) if fields[2].strip() else 0.0
            alt = float(fields[3]) if fields[3].strip() else 0.0
            speed_kmh = float(fields[4]) if fields[4].strip() else 0.0
            course = float(fields[5]) if fields[5].strip() else 0.0
            sv_count = int(fields[7]) if len(fields) > 7 and fields[7].strip() else 0
            hdop = float(fields[8]) if len(fields) > 8 and fields[8].strip() else 99.9

            gps = {
                "has_fix": mode > 0 and lat != 0.0 and lng != 0.0,
                "mode": mode,
                "lat": lat,
                "lng": lng,
                "alt": alt,
                "speed": speed_kmh / 3.6,  # km/h -> m/s
                "heading": course,
                "satellites": sv_count,
                "hdop": hdop,
            }
            status = "3D" if mode == 2 else ("2D" if mode == 1 else "NO FIX")
            print(f"[GPS] {status}: lat={lat:.6f} lng={lng:.6f} alt={alt:.1f}m "
                  f"spd={speed_kmh:.1f}km/h sat={sv_count} hdop={hdop:.1f}")
            return gps
        except (ValueError, IndexError) as e:
            print(f"[GPS] CGNSINF value error: {e}")
            return None


# ============================================================
# MQTT AT Commands
# ============================================================

class MQTTATClient:
    """
    MQTT client using Air780E AT command set.
    Commands: MQTTCONNCFG, MQTTCONN, MQTTPUB, MQTTSUB, MQTTDISC
    URC responses: +MQTTCONNACK, +MQTTPUBACK, +MQTTDISCONNECT, +MQTTSUBRECV
    """

    def __init__(self, session: ATSession):
        self.at = session
        self.connected = False

    def configure(self) -> bool:
        """
        AT+MQTTCONNCFG=<profile>,<clean_session>,<host>,<port>,<ssl>,<keepalive>,<client_id>
        Configure MQTT connection parameters for profile 0.
        """
        cmd = (
            f'AT+MQTTCONNCFG=0,{MQTT_CLEAN_SESSION},'
            f'"{MQTT_BROKER_HOST}",{MQTT_BROKER_PORT},'
            f'0,{MQTT_KEEPALIVE},"{MQTT_CLIENT_ID}"'
        )
        ok, resp = self.at.send_at(cmd)
        print(f"[MQTT] CONNCFG: {'OK' if ok else 'FAIL'} -> {resp}")
        return ok

    def connect(self, max_retries: int = RECONNECT_RETRIES) -> bool:
        """
        AT+MQTTCONN=<profile>,<host>,<port>,<reconnect>
        Initiate MQTT connection. Response comes as URC +MQTTCONNACK.
        Retries with exponential backoff on failure.
        """
        for attempt in range(max_retries):
            cmd = f'AT+MQTTCONN=0,"{MQTT_BROKER_HOST}",{MQTT_BROKER_PORT},0'
            ok, resp = self.at.send_at(cmd, timeout=15.0)
            print(f"[MQTT] CONN (attempt {attempt + 1}/{max_retries}): "
                  f"{'OK' if ok else 'FAIL'} -> {resp}")

            if ok:
                # Wait for +MQTTCONNACK URC
                time.sleep(2.0)
                # Read any pending URC
                self.at.ser.timeout = 3.0
                extra = self.at.ser.read(self.at.ser.in_waiting or 256).decode(
                    "utf-8", errors="replace")

                if "+MQTTCONNACK: 0,0,0" in extra:
                    self.connected = True
                    print("[MQTT] Connection accepted by broker (result=0, code=0)")
                    return True
                elif "+MQTTCONNACK:" in extra:
                    print(f"[MQTT] Connection rejected: {extra.strip()}")
                else:
                    # Some firmwares return OK after CONNACK
                    self.connected = True
                    print("[MQTT] Connection assumed OK (no CONNACK rejection)")
                    return True

            # Failed this attempt
            if attempt < max_retries - 1:
                delay = min(RETRY_DELAY_BASE * (RETRY_BACKOFF ** attempt) * 2,
                           RETRY_DELAY_MAX)
                print(f"[MQTT] Connect failed, retrying in {delay:.1f}s...")
                time.sleep(delay)

        print(f"[MQTT] Connect failed after {max_retries} attempts")
        return False

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """
        AT+MQTTPUB=<profile>,<topic>,<payload>,<qos>,<retain>
        Publish a message. For QoS 1, reads +MQTTPUBACK URC.
        """
        if not self.connected:
            print("[MQTT] Cannot publish: not connected")
            return False

        cmd = f'AT+MQTTPUB=0,"{topic}","{payload}",{qos},0'
        ok, resp = self.at.send_at(cmd, timeout=5.0)
        print(f"[MQTT] PUB ({topic}): {'OK' if ok else 'FAIL'} -> {resp}")

        if ok and qos > 0:
            time.sleep(0.5)
            self.at.ser.timeout = 2.0
            extra = self.at.ser.read(self.at.ser.in_waiting or 256).decode(
                "utf-8", errors="replace")
            if "+MQTTPUBACK:" in extra:
                print(f"[MQTT] PUBACK received: {extra.strip()}")
            else:
                print(f"[MQTT] PUBACK URC: {extra.strip()}")
        return ok

    def subscribe(self, topic: str, qos: int = 1) -> bool:
        """
        AT+MQTTSUB=<profile>,<topic>,<qos>
        Subscribe to a topic. URC +MQTTSUBRECV delivers messages.
        """
        cmd = f'AT+MQTTSUB=0,"{topic}",{qos}'
        ok, resp = self.at.send_at(cmd)
        print(f"[MQTT] SUB ({topic}): {'OK' if ok else 'FAIL'} -> {resp}")
        return ok

    def disconnect(self) -> bool:
        """
        AT+MQTTDISC=<profile>
        Disconnect MQTT session.
        """
        cmd = "AT+MQTTDISC=0"
        ok, resp = self.at.send_at(cmd)
        print(f"[MQTT] DISC: {'OK' if ok else 'FAIL'} -> {resp}")
        if ok:
            self.connected = False
        return ok

    def read_downlink(self) -> Optional[str]:
        """Check for any subscribed messages (non-blocking)."""
        self.at.ser.timeout = 0.1
        data = self.at.ser.read(self.at.ser.in_waiting or 256).decode(
            "utf-8", errors="replace")
        if "+MQTTSUBRECV:" in data:
            print(f"[MQTT] DOWNLINK: {data.strip()}")
            return data.strip()
        return None


# ============================================================
# Retry Helpers
# ============================================================

def retry_with_backoff(func, step_name: str, max_retries: int = MAX_STEP_RETRIES,
                       fatal: bool = True) -> bool:
    """
    Execute func with exponential backoff retries.
    Returns True on success, False if all retries exhausted.
    If fatal=False (for optional steps), returns True even on failure.
    """
    for attempt in range(max_retries):
        try:
            if func():
                return True
        except Exception as e:
            print(f"[{step_name}] Exception: {e}")

        if attempt < max_retries - 1:
            delay = min(RETRY_DELAY_BASE * (RETRY_BACKOFF ** attempt), RETRY_DELAY_MAX)
            print(f"[{step_name}] Step failed (attempt {attempt + 1}/{max_retries}), "
                  f"retrying in {delay:.1f}s...")
            time.sleep(delay)

    if fatal:
        print(f"[FAIL] {step_name} failed after {max_retries} retries")
        return False
    else:
        print(f"[WARN] {step_name} failed (non-fatal, continuing)")
        return True


# ============================================================
# MQTT Flow: Full Connection + Publish Sequence
# ============================================================

def run_mqtt_flow(session: ATSession) -> bool:
    """
    Execute the complete MQTT connection flow with retry:
    1. Verify AT communication
    2. Check SIM & network registration
    3. Set up PDP context
    4. Configure PSM
    5. Configure MQTT parameters (MQTTCONNCFG)
    6. Connect to broker (MQTTCONN)
    7. Publish test messages (location, heartbeat)
    8. Subscribe to downlink topic
    9. Disconnect (MQTTDISC)
    """
    print("\n" + "=" * 60)
    print("  KeepSafe MQTT AT Command Flow")
    print("=" * 60 + "\n")

    mqtt = MQTTATClient(session)

    # Step 1: Basic AT check
    print("--- Step 1: AT Communication ---")
    if not retry_with_backoff(session.at_basic, "AT"):
        return False

    # Step 2: Check firmware type
    print("\n--- Step 2: Firmware Check ---")
    ok, fw_type = session.at_check_firmware()
    if fw_type == "LuatOS":
        print("[WARN] Module is running LuatOS firmware. MQTT AT commands may not be available.")
        print("       Use the LuatOS MQTT library instead (see luatos/mqtt.lua).")
        print("       Continuing anyway...")
    elif fw_type == "UNKNOWN":
        print("[WARN] Could not determine firmware type. Proceeding anyway.")

    # Step 3: SIM check
    print("\n--- Step 3: SIM Card ---")
    if not retry_with_backoff(session.at_check_sim, "SIM"):
        return False

    # Step 4: Signal strength
    print("\n--- Step 4: Signal Strength ---")
    session.at_csq()

    # Step 5: Network registration
    print("\n--- Step 5: Network Registration ---")
    if not retry_with_backoff(session.at_network_reg, "NETWORK"):
        print("[WARN] Network not registered. Continuing anyway...")

    # Step 6: PDP context + activation
    print("\n--- Step 6: PDP Setup ---")
    if not retry_with_backoff(session.at_pdp_setup, "PDP"):
        return False

    # Step 7: PSM configuration (optional)
    print("\n--- Step 7: PSM Configuration ---")
    retry_with_backoff(session.at_psm_configure, "PSM", fatal=False)

    # Step 8: MQTT CONNCFG
    print("\n--- Step 8: MQTT Config (MQTTCONNCFG) ---")
    if not retry_with_backoff(mqtt.configure, "MQTT_CFG"):
        return False

    # Step 9: MQTT CONN
    print("\n--- Step 9: MQTT Connect (MQTTCONN) ---")
    if not mqtt.connect():
        print("[FAIL] MQTT connection failed after all retries. Check broker availability.")
        return False

    # Step 10: Publish test messages
    print("\n--- Step 10: Publish Test Messages ---")

    # Location report (with GPS poll if available)
    print("Polling GPS...")
    gps_data = session.at_cgnsinf()
    lat = 22.5431
    lng = 113.9346
    alt = 15.0
    spd = 0.5
    sat = 12
    fix = 1
    if gps_data and gps_data["has_fix"]:
        lat = gps_data["lat"]
        lng = gps_data["lng"]
        alt = gps_data["alt"]
        spd = gps_data["speed"]
        sat = gps_data["satellites"]
        fix = 2 if gps_data["mode"] == 2 else 1
        print("[GPS] Using real GPS data for location report")

    location_payload = json_mod.dumps({
        "device_id": MQTT_CLIENT_ID,
        "fw": "ec618-test",
        "ts": int(time.time()),
        "lat": lat,
        "lng": lng,
        "alt": alt,
        "spd": spd,
        "sat": sat,
        "fix": fix,
        "bat": 95,
    })
    mqtt.publish(TOPIC_LOCATION, location_payload, MQTT_QOS_LOCATION)

    time.sleep(1)

    # Heartbeat
    heartbeat_payload = json_mod.dumps({
        "device_id": MQTT_CLIENT_ID,
        "fw": "ec618-test",
        "ts": int(time.time()),
        "state": "STATIONARY",
        "bat": 95,
        "mqtt": 2,  # CONNECTED
    })
    mqtt.publish(TOPIC_HEARTBEAT, heartbeat_payload, MQTT_QOS_HEARTBEAT)

    time.sleep(0.5)

    # SOS (test)
    sos_payload = json_mod.dumps({
        "device_id": MQTT_CLIENT_ID,
        "fw": "ec618-test",
        "ts": int(time.time()),
        "alert": "sos",
        "lat": lat,
        "lng": lng,
        "bat": 95,
    })
    mqtt.publish(TOPIC_SOS, sos_payload, MQTT_QOS_SOS)

    # Step 11: Subscribe (for downlink)
    print("\n--- Step 11: Subscribe Downlink ---")
    mqtt.subscribe(TOPIC_DOWNLINK, qos=1)

    time.sleep(1)

    # Check for downlink messages
    print("\n--- Step 12: Check Downlink ---")
    mqtt.read_downlink()

    # Step 13: Disconnect
    print("\n--- Step 13: MQTT Disconnect (MQTTDISC) ---")
    mqtt.disconnect()

    print("\n" + "=" * 60)
    print("  MQTT Flow Complete!")
    print("=" * 60)
    return True


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="KeepSafe MQTT AT Command Script (Air780E/EC618 AT Firmware)"
    )
    parser.add_argument("--port", help="Serial port (e.g., /dev/cu.usbmodem0000000000013)")
    parser.add_argument("--auto", action="store_true", help="Auto-detect Air780EG port")
    parser.add_argument("--list", action="store_true", help="List available serial ports")
    parser.add_argument("--publish", metavar="JSON",
                        help="Publish a custom JSON payload to location topic and exit")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--gps", action="store_true",
                        help="Quick GPS poll via AT+CGNSINF and exit")
    parser.add_argument("--max-retries", type=int, default=MAX_RETRIES,
                        help=f"Max retries per AT command (default: {MAX_RETRIES})")
    args = parser.parse_args()

    # --list: show ports and exit
    if args.list:
        ports = list_ports()
        if not ports:
            print("No serial ports found.")
        else:
            print("Available serial ports:")
            for p in ports:
                print(f"  {p.device}  {p.description}  [{p.vid}:{p.pid}]")
        return

    # Determine port
    port = args.port
    if args.auto and not port:
        print("Auto-detecting Air780EG port...")
        port = find_air780eg_port()
        if not port:
            print("[ERROR] Could not auto-detect Air780EG. Use --port to specify.")
            sys.exit(1)

    if not port:
        print("[ERROR] No port specified. Use --port, --auto, or --list.")
        parser.print_help()
        sys.exit(1)

    # Create AT session
    session = ATSession(port, baud=args.baud)
    if not session.connect():
        sys.exit(1)

    try:
        if args.gps:
            # Quick GPS poll
            print("Polling GPS (AT+CGNSINF)...")
            gps = session.at_cgnsinf()
            if gps:
                print(json_mod.dumps(gps, indent=2))
            else:
                print("[GPS] No fix or GPS not available")
        elif args.publish:
            # Quick publish mode
            print(f"Publishing custom payload: {args.publish}")
            mqtt = MQTTATClient(session)
            if mqtt.configure() and mqtt.connect():
                mqtt.publish(TOPIC_LOCATION, args.publish)
                mqtt.disconnect()
        else:
            # Full MQTT flow
            success = run_mqtt_flow(session)
            if not success:
                print("\n[RESULT] MQTT flow FAILED. Check logs above for details.")
                sys.exit(1)
            else:
                print("\n[RESULT] MQTT flow PASSED.")
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
