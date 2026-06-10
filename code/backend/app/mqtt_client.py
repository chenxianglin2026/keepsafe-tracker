"""
KeepSafe Backend — MQTT Client (EMQX Consumer)

Subscribes to all 5 device topics:
  - keepsafe/v1/{device_id}/location
  - keepsafe/v1/{device_id}/heartbeat
  - keepsafe/v1/{device_id}/sos
  - keepsafe/v1/{device_id}/alert/low_battery
  - keepsafe/v1/{device_id}/version

Processes messages, writes to TimescaleDB, updates Redis cache, triggers push.
Checks geofences on location updates and detects low battery from location data.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, asin
from typing import Optional

import gmqtt

from app.config import settings
from app.db import async_session_factory
from app.redis_cache import set_device_status, set_latest_location
from app.lbs_resolver import resolve_lbs

logger = logging.getLogger("keepsafe.mqtt")

# ── GMQTT Stop (sentinel) ──
STOP = object()

# ── Geofence state tracking (in-process, avoids duplicate alerts) ──
# Key: "device_id:fence_id" -> "inside" | "outside"
_fence_states: dict[str, str] = {}


def _normalize_ec618_payload(data: dict) -> dict:
    """Normalize EC618 firmware payload fields to backend expected names.

    EC618 firmware uses abbreviated field names (suited for bandwidth-constrained
    LTE Cat.1 devices). This maps them to the backend's canonical names.
    Also handles ESP32-S3 firmware which already uses canonical names.
    """
    # Map short -> canonical field names
    FIELD_MAP = {
        "spd": "speed",
        "bat": "battery",
        "sat": "satellites",
        "fix": "fix_type",
        "hdg": "heading",
        "fw": "fw_version",
    }

    normalized = {}
    for key, value in data.items():
        canonical = FIELD_MAP.get(key, key)
        normalized[canonical] = value

    return normalized


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance in meters between two coordinates."""
    R = 6371000  # Earth radius in meters
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * asin(sqrt(a))


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
        """Handle incoming MQTT messages.

        Routes by topic pattern (not by a 'type' field in JSON body) because
        the EC618 firmware sends messages without a type discriminator.
        """
        try:
            data = json.loads(payload.decode("utf-8"))
            device_id = data.get("device_id", "unknown")

            # Extract device_id from topic as fallback: keepsafe/v1/{device_id}/suffix
            if device_id == "unknown":
                parts = topic.split("/")
                if len(parts) >= 3:
                    device_id = parts[2]

            logger.debug("MQTT msg: device=%s topic=%s", device_id, topic)

            loop = asyncio.get_running_loop()

            # Route by topic suffix (last segment of topic)
            if topic.endswith("/location"):
                loop.create_task(self._handle_location(device_id, data))
            elif topic.endswith("/heartbeat"):
                loop.create_task(self._handle_heartbeat(device_id, data))
            elif topic.endswith("/sos"):
                loop.create_task(self._handle_sos(device_id, data))
            elif topic.endswith("/low_battery") or topic.endswith("/alert/low_battery"):
                loop.create_task(self._handle_low_battery(device_id, data))
            elif topic.endswith("/version"):
                loop.create_task(self._handle_version(device_id, data))
            else:
                logger.warning("Unknown topic: %s from %s", topic, device_id)

        except json.JSONDecodeError:
            logger.error("MQTT: invalid JSON payload on %s", topic)
        except Exception as exc:
            logger.error("MQTT: error processing message on %s: %s", topic, exc, exc_info=True)

    async def _handle_location(self, device_id: str, data: dict):
        """Process location report: DB insert + Redis update + geofence check + LBS."""
        # Normalize EC618 abbreviated field names to canonical backend names
        data = _normalize_ec618_payload(data)

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
                              fw_version = COALESCE(:fw_version, devices.fw_version),
                              is_active = TRUE
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

        # 5. Check geofences (enter/exit detection)
        await self._check_geofences(device_id, lat, lng, ts)

        # 6. Auto-detect low battery from location reports (< 20%)
        battery = data.get("battery")
        if battery is not None and battery < 20:
            # Avoid duplicate alerts: check if we recently alerted for this device
            # Simple throttle: only alert once per 6 hours per device
            throttle_key = f"low_battery_throttle:{device_id}"
            from app.redis_cache import get_redis
            r = await get_redis()
            if not await r.exists(throttle_key):
                await r.set(throttle_key, "1", ex=21600)  # 6 hours
                logger.warning("Auto low-battery for %s: %d%% from location report", device_id, battery)
                async with async_session_factory() as session:
                    await session.execute(
                        """
                        INSERT INTO alerts (device_id, ts, alert_type, payload)
                        VALUES (:device_id, :ts, 'low_battery', :payload)
                        """,
                        {
                            "device_id": device_id,
                            "ts": ts,
                            "payload": json.dumps({"battery": battery, "source": "location_report"}),
                        },
                    )
                    await session.commit()

    async def _check_geofences(self, device_id: str, lat: float, lng: float, ts: datetime):
        """Check all enabled fences for this device and fire enter/exit alerts."""
        if lat is None or lng is None or (lat == 0.0 and lng == 0.0):
            return  # No valid GPS fix, skip geofence check

        try:
            async with async_session_factory() as session:
                from sqlalchemy import select as sa_select
                from app.db import Fence

                result = await session.execute(
                    sa_select(Fence).where(
                        Fence.device_id == device_id,
                        Fence.enabled == True,  # noqa: E712
                    )
                )
                fences = result.scalars().all()

                for fence in fences:
                    distance = _haversine_distance(lat, lng, fence.lat, fence.lng)
                    inside = distance <= fence.radius
                    state_key = f"{device_id}:{fence.id}"
                    prev_state = _fence_states.get(state_key, "unknown")

                    if prev_state == "unknown":
                        # First location for this fence pair
                        _fence_states[state_key] = "inside" if inside else "outside"
                        continue

                    if prev_state == "outside" and inside:
                        # Entered fence
                        _fence_states[state_key] = "inside"
                        await self._record_geofence_alert(device_id, fence, "enter", ts, lat, lng)
                    elif prev_state == "inside" and not inside:
                        # Exited fence
                        _fence_states[state_key] = "outside"
                        await self._record_geofence_alert(device_id, fence, "exit", ts, lat, lng)
                    elif prev_state == "inside" and inside:
                        # Still inside - update state but no new alert
                        pass
                    elif prev_state == "outside" and not inside:
                        # Still outside - no change
                        pass
        except Exception as exc:
            logger.error("Geofence check failed for %s: %s", device_id, exc, exc_info=True)

    async def _record_geofence_alert(self, device_id: str, fence, event: str, ts: datetime, lat: float, lng: float):
        """Record a geofence enter/exit alert and send push notification."""
        event_label = "进入" if event == "enter" else "离开"

        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO alerts (device_id, ts, alert_type, payload)
                VALUES (:device_id, :ts, :alert_type, :payload)
                """,
                {
                    "device_id": device_id,
                    "ts": ts,
                    "alert_type": f"geofence_{event}",
                    "payload": json.dumps({
                        "fence_id": fence.id,
                        "fence_name": fence.name,
                        "event": event,
                        "lat": lat,
                        "lng": lng,
                        "radius": fence.radius,
                    }),
                },
            )
            await session.commit()

        logger.info("Geofence %s: device=%s fence=%s(%s)", event, device_id, fence.name, fence.id)

        # Push notification
        try:
            from app.push import send_geofence_push

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
                nickname = row[0] or device_id
                await send_geofence_push(
                    device_token=device_id,  # placeholder
                    platform="android",
                    fence_name=fence.name,
                    event=event,
                    device_name=nickname,
                )
        except Exception as exc:
            logger.error("Geofence push notification failed: %s", exc)

    async def _handle_heartbeat(self, device_id: str, data: dict):
        """Process heartbeat: update Redis status + DB last_seen."""
        data = _normalize_ec618_payload(data)

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

        # Update DB last_seen and reactivate if needed
        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO devices (device_id, device_token, last_seen, is_active)
                VALUES (:device_id, '', :last_seen, TRUE)
                ON CONFLICT (device_id)
                DO UPDATE SET last_seen = :last_seen,
                              is_active = TRUE
                """,
                {"device_id": device_id, "last_seen": ts},
            )
            await session.commit()

        logger.debug("Heartbeat processed for %s", device_id)

    async def _handle_sos(self, device_id: str, data: dict):
        """Process SOS event: DB insert + push notification."""
        data = _normalize_ec618_payload(data)

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
                VALUES (:device_id, :ts, 'sos', :payload)
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
                    _ = row[0]  # user_id (reserved for push notification routing)
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
        data = _normalize_ec618_payload(data)

        ts = datetime.fromtimestamp(data["ts"], tz=timezone.utc)

        async with async_session_factory() as session:
            await session.execute(
                """
                INSERT INTO alerts (device_id, ts, alert_type, payload)
                VALUES (:device_id, :ts, 'low_battery', :payload)
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
