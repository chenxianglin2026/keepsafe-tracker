"""
KeepSafe Backend — Push Notification Dispatcher

Routes alerts to the correct push channel (FCM / APNs) based on user device type.
"""

from __future__ import annotations

import logging

from app.push.fcm import send_push as fcm_send
from app.push.apns import get_apns_client

logger = logging.getLogger("keepsafe.push")


async def send_sos_push(device_token: str, platform: str, device_name: str = "设备") -> bool:
    """
    Send SOS emergency push notification.

    Args:
        device_token: FCM or APNs token.
        platform: "android" or "ios".
        device_name: Human-readable device name / family member name.
    Returns:
        True if sent successfully.
    """
    title = f"🚨 紧急求助！{device_name}"
    body = "该设备正在发送 SOS 紧急求助，请立即查看位置信息。"

    if platform == "ios":
        apns = get_apns_client()
        return await apns.send_push(device_token, title=title, body=body, data={"type": "sos"})
    else:
        return await fcm_send(device_token, title=title, body=body, data={"type": "sos"})


async def send_low_battery_push(
    device_token: str,
    platform: str,
    battery: int,
    device_name: str = "设备",
) -> bool:
    """
    Send low battery alert push notification.

    Args:
        device_token: FCM or APNs token.
        platform: "android" or "ios".
        battery: Battery percentage.
        device_name: Human-readable device name.
    Returns:
        True if sent successfully.
    """
    title = f"⚠️ {device_name} 电量不足"
    body = f"当前电量 {battery}%，请尽快充电。"

    if platform == "ios":
        apns = get_apns_client()
        return await apns.send_push(
            device_token,
            title=title,
            body=body,
            data={"type": "low_battery", "battery": str(battery)},
        )
    else:
        return await fcm_send(
            device_token,
            title=title,
            body=body,
            data={"type": "low_battery", "battery": str(battery)},
        )


async def send_geofence_push(
    device_token: str,
    platform: str,
    fence_name: str,
    event: str,
    device_name: str = "设备",
) -> bool:
    """
    Send geofence entry/exit push notification. (Reserved for future use.)

    Args:
        device_token: FCM or APNs token.
        platform: "android" or "ios".
        fence_name: Name of the geofence.
        event: "enter" or "exit".
        device_name: Human-readable device name.
    Returns:
        True if sent successfully.
    """
    event_label = "进入" if event == "enter" else "离开"
    title = f"📍 {device_name} 围栏提醒"
    body = f"{device_name} 已{event_label}围栏「{fence_name}」"

    if platform == "ios":
        apns = get_apns_client()
        return await apns.send_push(
            device_token,
            title=title,
            body=body,
            data={"type": "geofence", "fence": fence_name, "event": event},
        )
    else:
        return await fcm_send(
            device_token,
            title=title,
            body=body,
            data={"type": "geofence", "fence": fence_name, "event": event},
        )
