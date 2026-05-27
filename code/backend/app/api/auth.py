"""
KeepSafe Backend — Device Authentication API

EMQX auth backend calls these endpoints to verify device credentials.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Device

logger = logging.getLogger("keepsafe.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthRequest(BaseModel):
    device_id: str
    token: str


class AuthResponse(BaseModel):
    result: str  # "allow" | "deny"


@router.post("/device", response_model=AuthResponse)
async def authenticate_device(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    """
    EMQX authentication callback.

    Authenticates device_id + token against the devices table.
    Returns {"result": "allow"} on success, {"result": "deny"} otherwise.
    """
    logger.info("Auth request: device=%s", req.device_id)

    if not req.device_id or not req.token:
        logger.warning("Auth denied: missing credentials for %s", req.device_id)
        return AuthResponse(result="deny")

    stmt = select(Device).where(Device.device_id == req.device_id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device is None:
        logger.warning("Auth denied: unknown device %s", req.device_id)
        return AuthResponse(result="deny")

    if device.device_token != req.token:
        logger.warning("Auth denied: token mismatch for %s", req.device_id)
        return AuthResponse(result="deny")

    if not device.is_active:
        logger.warning("Auth denied: device %s is inactive", req.device_id)
        return AuthResponse(result="deny")

    logger.info("Auth allowed: device=%s", req.device_id)
    return AuthResponse(result="allow")


@router.get("/device/acl", response_model=AuthResponse)
async def authorize_device_acl(
    device_id: str,
    topic: str,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    """
    EMQX authorization (ACL) callback.

    Verifies that device_id is allowed to publish/subscribe to the given topic.
    Pattern: keepsafe/v1/{device_id}/...
    Returns {"result": "allow"} if the device_id in the topic matches the authenticated user.
    """
    # Parse the topic: keepsafe/v1/{topic_device_id}/...
    parts = topic.split("/")
    if len(parts) < 3:
        logger.warning("ACL denied: malformed topic %s", topic)
        return AuthResponse(result="deny")

    topic_device_id = parts[2]  # keepsafe/v1/{device_id}/...

    # Device can only publish/subscribe to its own topics
    if topic_device_id != device_id:
        logger.warning(
            "ACL denied: device %s tried to access %s topic",
            device_id,
            topic,
        )
        return AuthResponse(result="deny")

    # Verify device still exists and is active
    stmt = select(Device).where(Device.device_id == device_id, Device.is_active == True)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device is None:
        logger.warning("ACL denied: device %s not found or inactive", device_id)
        return AuthResponse(result="deny")

    logger.debug("ACL allowed: device=%s topic=%s action=%s", device_id, topic, action)
    return AuthResponse(result="allow")
