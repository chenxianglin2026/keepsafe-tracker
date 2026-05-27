"""
KeepSafe Backend — Firebase Cloud Messaging (Android) Push
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger("keepsafe.push.fcm")

_app: Optional[firebase_admin.App] = None


def init_fcm(cred_path: str) -> bool:
    """
    Initialize Firebase Admin SDK.

    Args:
        cred_path: Path to Firebase service account JSON file.
    Returns:
        True if initialized, False if file missing.
    """
    global _app
    cred_file = Path(cred_path)
    if not cred_file.exists():
        logger.warning("FCM credentials file not found: %s (push disabled)", cred_path)
        return False

    try:
        cred = credentials.Certificate(str(cred_file))
        _app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized")
        return True
    except Exception as exc:
        logger.error("Failed to initialize Firebase: %s", exc)
        return False


async def send_push(device_token: str, title: str, body: str, data: Optional[dict] = None) -> bool:
    """
    Send a push notification via FCM.

    Args:
        device_token: FCM device registration token.
        title: Notification title.
        body: Notification body.
        data: Optional additional data payload.
    Returns:
        True if sent successfully.
    """
    if _app is None:
        logger.warning("FCM not initialized, cannot send push to %s", device_token)
        return False

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=device_token,
    )

    try:
        response = messaging.send(message)
        logger.info("FCM push sent: %s", response)
        return True
    except messaging.UnregisteredError:
        logger.warning("FCM device token unregistered: %s", device_token)
        return False
    except Exception as exc:
        logger.error("FCM push failed: %s", exc)
        return False
