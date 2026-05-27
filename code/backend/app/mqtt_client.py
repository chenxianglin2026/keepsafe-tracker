"""
KeepSafe Backend — MQTT Client (EMQX Consumer)

Subscribes to all 5 device topics:
  - keepsafe/v1/{device_id}/location
  - keepsafe/v1/{device_id}/heartbeat
  - keepsafe/v1/{device_id}/sos
  - keepsafe/v1/{device_id}/alert/low_battery
  - keepsafe/v1/{device_id}/version

Processes messages, writes to TimescaleDB, updates Redis cache, triggers push.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import gmqtt

from app.config import settings
from app.db import async_session_factory
from app.redis_cache import set_device_status, set_latest_location
from app.lbs_resolver import resolve_lbs

logger = logging.getLogger("keepsafe.mqtt")

# ── GMQTT Stop (sentinel) ──
STOP = object()


class MQTTClient:
    """Async MQTT client using gmqtt."""

    def __init__(self):
        self.client: Optional[gmqtt.Client] = None
        self._connected = False

    def _on_connect(self, client, flags, rc, properties):
        self._connected = True
        logger.info("MQTT connected to %s:%d", settings.emqx_host, settings.emqx_port)

        # Subscribe to all device topics using wildcards
        client.subscribe("keepsafe/v1/+/location", qos=1)
        client.subscribe("keepsafe/v1/+/heartbeat", qos=0)
        client.subscribe("keepsafe/v1/+/sos", qos=1)
        client.subscribe("keepsafe/v1/+/alert/low_battery", qos=1)
        client.subscribe("keepsafe/v1/+/version", qos=0)
        logger.info("MQTT subscribed to all device topics")

    def _on_disconnect(self, client, packet, exc=None):
        self._connected = False
        logger.warning("MQTT disconnected: %s", exc)

    def _on_message(self, client, topic, payload, qos, properties):
        """Handle incoming MQTT messages."""
        try:
            data = json.loads(payload.decode("utf-8"))
            msg_type = data.get("type", "unknown")
            device_id = data.get("device_id", "unknown")

            logger.debug("MQTT msg: type=%s device=%s topic=%s", msg_type, device_id, topic)

            if msg_type == "location":
                self._handle_location(device_id, data)
            elif msg_type == "heartbeat":
                self._handle_heartbeat(device_id, data)
            elif msg_type == "sos":
                self._handle_sos(device_id, data)
            elif msg_type == "low_battery":
                self._handle_low_battery(device_id, data)
            elif msg_type == "version":
                self._handle_version(device_id, data)
            else:
                logger.warning("Unknown message type: %s from %s", msg_type, device_id)

        except json.JSONDecodeError:
            logger.error("MQTT: invalid JSON payload on %s", topic)
        except Exception as exc:
            logger.error("MQTT: error processing message on %s: %s", topic, exc, exc_info=True)

    async def _handle_location(self, device_id: str, data: dict):
        """Process location report: DB insert + Redis update + LBS resolution."""
        ts = datetime.fromtimestamp(data["ts"], tz=timezone.utc)

        # 1. Update Redis cache immediately
        loc_cache = {
            "device_id": device_id,
            "ts": ts.isoformat(),
            "lat": data.get("lat"),
            "lng": data.get("lng"),
            "alt": data.get("alt"),
            "speed": data.get("speed"),
            "heading": data.get("heading"),
            "accuracy": data.get("accuracy"),
            "satellites": data.get("satellites"),
            "fix_type": data.get("fix_type"),
            "cell_id": data.get("cell_id"),
            "battery": data.get("battery"),
            "charging": data.get("charging"),
            "rssi": data.get("rssi"),
            "fw_version": data.get("fw_version"),
        }
        await set_latest_location(device_id, loc_cache)

        # 2. Update device status in Redis
        status = {
            "device_id": device_id,
            "battery": data.get("battery"),
            "charging": data.get("charging"),
            "rssi": data.get("rssi"),
            "lat": data.get("lat"),
            "lng": data.get("lng"),
            "last_seen": ts.isoformat(),
        }
        await set_device_status(device_id, status)

        # 3. Write to TimescaleDB
        async with async_session_factory() as session:
            # Insert location
            await session.execute(
                """
                INSERT INTO locations
                    (device_id, ts, lat, lng, alt, speed, heading, accuracy,
                     satellites, fix_type, cell_id, battery, charging, rssi, fw_version)
                VALUES
                    (:device_id, :ts, :lat, :lng, :alt, :speed, :heading, :accuracy,
                     :satellites, :fix_type, :cell_id, :battery, :charging, :rssi, :fw_version)
                """,
                {
                    "device_id": device_id,
                    "ts": ts,
                    "lat": data.get("lat"),
                    "lng": data.get("lng"),
                    "alt": data.get("alt"),
                    "speed": data.get("speed"),
                    "heading": data.get("heading"),
                    "accuracy": data.get("accuracy"),
                    "satellites": data.get("satellites"),
                    "fix_type": data.get("fix_type"),
                    "cell_id": data.get("cell_id"),
                    "battery": data.get("battery"),
                    "charging": data.get("charging"),
                    "rssi": data.get("rssi"),
                    "fw_version": data.get("fw_version"),
                },
            )

            # Update device last_seen
            await session.execute(
                """
                INSERT INTO devices (device_id, device_token, fw_version, last_seen, is_active)
                VALUES (:device_id, '', :fw_version, :last_seen, TRUE)
                ON CONFLICT (device_id)
                DO UPDATE SET last_seen = :last_seen,
                              fw_version = COALESCE(:fw_version, devices.fw_version)
                """,
                {
                    "device_id": device_id,
                    "fw_version": data.get("fw_version"),
                    "last_seen": ts,
                },
            )

            await session.commit()

        # 4. Resolve LBS position if cell_id is present and fix is poor (no GPS fix)
        cell_id = data.get("cell_id")
        lat = data.get("lat")
        lng = data.get("lng")
        if cell_id and (lat is None or lng is None or lat == 0.0 or lng == 0.0):
            lbs_result = await resolve_lbs(cell_id)
            if lbs_result:
                logger.info("LBS resolved for %s: (%.4f, %.4f)", device_id, lbs_result["lat"], lbs_result["lng"])
                # We don't overwrite the DB record here; LBS data can be returned
                # via a separate API call or used as fallback in location endpoint

    async def _handle_heartbeat(self, device_id: str, data: dict):
        """Process heartbeat: update Redis status + DB last_seen."""
        ts = datetime.fromtimestamp(data["ts"], tz=timezone.utc)

        # Update Redis status
        status = {
            "device_id": device_id,
            "battery": data.get("battery"),
            "charging": data.get("charging"),
            "rssi": data.get("rssi"),
            "uptime": data.get("uptime"),
            "last_seen": ts.isoformat(),
        }
        await set_device_status(device_id, status)

        # Update DB last_seen
        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO devices (device_id, device_token, last_seen, is_active)
                VALUES (:device_id, '', :last_seen, TRUE)
                ON CONFLICT (device_id)
                DO UPDATE SET last_seen = :last_seen
                """,
                {"device_id": device_id, "last_seen": ts},
            )
            await session.commit()

        logger.debug("Heartbeat processed for %s", device_id)

    async def _handle_sos(self, device_id: str, data: dict):
        """Process SOS event: DB insert + push notification."""
        ts = datetime.fromtimestamp(data["ts"], tz=timezone.utc)

        # Insert into sos_events
        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO sos_events
                    (device_id, ts, lat, lng, accuracy, battery, trigger_duration_ms)
                VALUES
                    (:device_id, :ts, :lat, :lng, :accuracy, :battery, :trigger_duration_ms)
                """,
                {
                    "device_id": device_id,
                    "ts": ts,
                    "lat": data.get("lat"),
                    "lng": data.get("lng"),
                    "accuracy": data.get("accuracy"),
                    "battery": data.get("battery"),
                    "trigger_duration_ms": data.get("trigger_duration_ms"),
                },
            )

            # Also record as alert
            await session.execute(
                """
                INSERT INTO alerts (device_id, ts, alert_type, payload)
                VALUES (:device_id, :ts, 'sos', :payload::jsonb)
                """,
                {
                    "device_id": device_id,
                    "ts": ts,
                    "payload": json.dumps(data),
                },
            )

            await session.commit()

        logger.warning("SOS received from %s", device_id)

        # ── Push notifications (fire-and-forget) ──
        try:
            from app.push import send_sos_push

            # Look up bound users for push
            async with async_session_factory() as session:
                result = await session.execute(
                    """
                    SELECT ud.user_id, ud.nickname, d.device_token
                    FROM user_devices ud
                    JOIN devices d ON d.device_id = ud.device_id
                    WHERE ud.device_id = :device_id AND ud.is_bound = TRUE
                    """,
                    {"device_id": device_id},
                )
                bindings = result.fetchall()

            if bindings:
                for row in bindings:
                    user_id = row[0]
                    nickname = row[1] or f"设备 {device_id}"
                    # NOTE: device_token here should be the user's push token,
                    # not the device's MQTT token. In production, store push tokens
                    # in a separate user_push_tokens table. Here we approximate.
                    await send_sos_push(
                        device_token=device_id,  # placeholder
                        platform="android",
                        device_name=nickname,
                    )
        except Exception as exc:
            logger.error("SOS push notification failed: %s", exc)

    async def _handle_low_battery(self, device_id: str, data: dict):
        """Process low battery alert: DB insert + push notification."""
        ts = datetime.fromtimestamp(data["ts"], tz=timezone.utc)

        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO alerts (device_id, ts, alert_type, payload)
                VALUES (:device_id, :ts, 'low_battery', :payload::jsonb)
                """,
                {
                    "device_id": device_id,
                    "ts": ts,
                    "payload": json.dumps(data),
                },
            )
            await session.commit()

        logger.info("Low battery alert from %s: %d%%", device_id, data.get("battery", 0))

        # Push notification
        try:
            from app.push import send_low_battery_push

            async with async_session_factory() as session:
                result = await session.execute(
                    """
                    SELECT ud.nickname, d.device_token
                    FROM user_devices ud
                    JOIN devices d ON d.device_id = ud.device_id
                    WHERE ud.device_id = :device_id AND ud.is_bound = TRUE
                    LIMIT 1
                    """,
                    {"device_id": device_id},
                )
                row = result.fetchone()

            if row:
                nickname = row[0] or f"设备 {device_id}"
                await send_low_battery_push(
                    device_token=device_id,  # placeholder
                    platform="android",
                    battery=data.get("battery", 0),
                    device_name=nickname,
                )
        except Exception as exc:
            logger.error("Low battery push failed: %s", exc)

    async def _handle_version(self, device_id: str, data: dict):
        """Process firmware version report."""
        fw_version = data.get("fw_version", "")
        logger.info("Version report from %s: %s", device_id, fw_version)

        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO devices (device_id, device_token, fw_version, is_active)
                VALUES (:device_id, '', :fw_version, TRUE)
                ON CONFLICT (device_id)
                DO UPDATE SET fw_version = :fw_version
                """,
                {"device_id": device_id, "fw_version": fw_version},
            )
            await session.commit()

    # ── Connection management ──

    async def connect(self):
        """Connect to EMQX broker."""
        client_id = f"keepsafe-backend-{int(datetime.now().timestamp())}"
        self.client = gmqtt.Client(client_id)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # EMQX auth — backend uses a dedicated service account
        # In production, use a specific backend MQTT user
        self.client.set_auth_credentials("keepsafe-backend", "{{PLACEHOLDER_EMQX_BACKEND_PASSWORD}}")

        logger.info("Connecting to EMQX at %s:%d...", settings.emqx_host, settings.emqx_port)
        await self.client.connect(settings.emqx_host, settings.emqx_port, keepalive=60)

    async def disconnect(self):
        """Disconnect from EMQX."""
        if self.client:
            await self.client.disconnect()
            self._connected = False
            logger.info("MQTT disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected


# Singleton
_mqtt_client: Optional[MQTTClient] = None


def get_mqtt_client() -> MQTTClient:
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MQTTClient()
    return _mqtt_client
