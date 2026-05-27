"""
KeepSafe Backend — Apple Push Notification Service (iOS)

Uses HTTP/2-based APNs with JWT authentication.
"""

from __future__ import annotations

import jwt
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("keepsafe.push.apns")

# APNs endpoints
APNS_DEVELOPMENT_HOST = "https://api.sandbox.push.apple.com"
APNS_PRODUCTION_HOST = "https://api.push.apple.com"

# Default headers
APNS_TOPIC = settings.apns_topic


class APNsClient:
    """Apple Push Notification Service client using HTTP/2."""

    def __init__(self, use_sandbox: bool = False):
        self.use_sandbox = use_sandbox
        self._key: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    def _load_key(self) -> str:
        if self._key is not None:
            return self._key

        key_path = Path(settings.apns_key_path)
        if not key_path.exists():
            logger.warning("APNs key file not found: %s (push disabled)", key_path)
            return ""

        try:
            self._key = key_path.read_text()
            return self._key
        except Exception as exc:
            logger.error("Failed to load APNs key: %s", exc)
            return ""

    def _generate_token(self) -> str:
        """Generate a JWT provider token for APNs."""
        key = self._load_key()
        if not key:
            return ""

        now = int(time.time())
        headers = {"alg": "ES256", "kid": settings.apns_key_id}
        payload = {
            "iss": settings.apns_team_id,
            "iat": now,
        }
        return jwt.encode(payload, key, algorithm="ES256", headers=headers)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP/2 client (httpx with h2 transport)."""
        if self._client is None or self._client.is_closed:
            host = APNS_DEVELOPMENT_HOST if self.use_sandbox else APNS_PRODUCTION_HOST
            self._client = httpx.AsyncClient(
                base_url=host,
                http2=True,
                timeout=10,
            )
        return self._client

    async def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        sound: str = "default",
        badge: Optional[int] = None,
    ) -> bool:
        """
        Send a push notification via APNs.

        Args:
            device_token: APNs device token (hex string).
            title: Alert title.
            body: Alert body.
            data: Custom payload data.
            sound: Notification sound.
            badge: Badge number (optional).
        Returns:
            True if accepted by APNs.
        """
        token = self._generate_token()
        if not token:
            logger.warning("APNs not configured, cannot send push to %s", device_token)
            return False

        # Build APNs payload
        aps_payload: dict = {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }
        if badge is not None:
            aps_payload["badge"] = badge

        payload: dict = {"aps": aps_payload}
        if data:
            payload["data"] = data

        client = await self._get_client()
        url = f"/3/device/{device_token}"

        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": APNS_TOPIC,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }

        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info("APNs push sent successfully to %s", device_token[:16])
                return True
            elif resp.status_code == 410:
                logger.warning("APNs device token unregistered: %s", device_token[:16])
                return False
            else:
                logger.error(
                    "APNs push failed: HTTP %d — %s",
                    resp.status_code,
                    resp.text,
                )
                return False
        except httpx.RequestError as exc:
            logger.error("APNs HTTP error: %s", exc)
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
_apns_client: Optional[APNsClient] = None


def get_apns_client(use_sandbox: bool = False) -> APNsClient:
    global _apns_client
    if _apns_client is None:
        _apns_client = APNsClient(use_sandbox=use_sandbox)
    return _apns_client
