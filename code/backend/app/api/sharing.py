"""
KeepSafe Backend — Device Sharing API

Endpoints for sharing device access with other users.
Owner can share a device; recipients can view shared devices.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import get_current_user, User
from app.db import get_db, Device, DeviceShare, UserDevice

logger = logging.getLogger("keepsafe.api.sharing")

router = APIRouter(prefix="/api/v1/devices", tags=["sharing"])


# ── Pydantic Schemas ───────────────────────────────────────────

class ShareRequest(BaseModel):
    shared_with_email: str
    permissions: str = "view"  # "view" or "control"


class ShareOut(BaseModel):
    id: int
    device_id: str
    owner_user_id: str
    shared_with_user_id: str
    permissions: str
    is_active: bool
    shared_at: datetime
    revoked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SharedDeviceOut(BaseModel):
    device_id: str
    device_nickname: Optional[str] = None
    owner_nickname: Optional[str] = None
    owner_email: Optional[str] = None
    permissions: str
    shared_at: datetime

    class Config:
        from_attributes = True


class ShareListOut(BaseModel):
    shares: List[ShareOut]
    total: int


class SharedDevicesListOut(BaseModel):
    devices: List[SharedDeviceOut]
    total: int


class MessageResponse(BaseModel):
    message: str


# ── Helpers ────────────────────────────────────────────────────

async def _verify_device_owner(
    device_id: str,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Verify current user owns this device (via UserDevice binding)."""
    stmt = select(UserDevice).where(
        and_(
            UserDevice.user_id == current_user.user_id,
            UserDevice.device_id == device_id,
            UserDevice.is_bound,
        )
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=403,
            detail="You do not own this device. Only the owner can manage shares.",
        )


# ── Endpoints ──────────────────────────────────────────────────

@router.post("/{device_id}/share", response_model=ShareOut, status_code=201)
async def share_device(
    device_id: str,
    req: ShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Share a device with another user by email.
    Only the device owner (bound user) can share.
    """
    if req.permissions not in ("view", "control"):
        raise HTTPException(
            status_code=400,
            detail="permissions must be 'view' or 'control'",
        )

    # Verify the current user owns this device
    await _verify_device_owner(device_id, current_user, db)

    # Verify device exists
    dev_stmt = select(Device).where(Device.device_id == device_id)
    dev_result = await db.execute(dev_stmt)
    if dev_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")

    # Find the target user by email
    user_stmt = select(User).where(User.email == req.shared_with_email.strip().lower())
    user_result = await db.execute(user_stmt)
    target_user = user_result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{req.shared_with_email}' not found",
        )

    # Cannot share with yourself
    if target_user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot share a device with yourself",
        )

    # Check if already shared (active)
    existing_stmt = select(DeviceShare).where(
        and_(
            DeviceShare.device_id == device_id,
            DeviceShare.owner_user_id == current_user.user_id,
            DeviceShare.shared_with_user_id == target_user.user_id,
            DeviceShare.is_active,
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update permissions if changed
        if existing.permissions != req.permissions:
            existing.permissions = req.permissions
            await db.commit()
            await db.refresh(existing)
        return ShareOut(
            id=existing.id,
            device_id=existing.device_id,
            owner_user_id=existing.owner_user_id,
            shared_with_user_id=existing.shared_with_user_id,
            permissions=existing.permissions,
            is_active=existing.is_active,
            shared_at=existing.shared_at,
            revoked_at=existing.revoked_at,
        )

    # Create new share
    share = DeviceShare(
        owner_user_id=current_user.user_id,
        shared_with_user_id=target_user.user_id,
        device_id=device_id,
        permissions=req.permissions,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    logger.info(
        "Device %s shared by %s with %s (permissions=%s)",
        device_id,
        current_user.user_id,
        target_user.user_id,
        req.permissions,
    )
    return ShareOut.model_validate(share)


@router.get("/{device_id}/shares", response_model=ShareListOut)
async def list_device_shares(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all active shares for a device. Only the device owner can view.
    """
    await _verify_device_owner(device_id, current_user, db)

    stmt = (
        select(DeviceShare)
        .where(
            and_(
                DeviceShare.device_id == device_id,
                DeviceShare.owner_user_id == current_user.user_id,
                DeviceShare.is_active,
            )
        )
        .order_by(DeviceShare.shared_at.desc())
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()

    return ShareListOut(
        shares=[ShareOut.model_validate(s) for s in shares],
        total=len(shares),
    )


@router.delete("/{device_id}/share/{share_id}", response_model=MessageResponse)
async def revoke_share(
    device_id: str,
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a device share. Only the device owner can revoke.
    """
    await _verify_device_owner(device_id, current_user, db)

    stmt = select(DeviceShare).where(
        and_(
            DeviceShare.id == share_id,
            DeviceShare.device_id == device_id,
            DeviceShare.owner_user_id == current_user.user_id,
        )
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()

    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")

    share.is_active = False
    share.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "Share %d revoked for device %s by owner %s",
        share_id,
        device_id,
        current_user.user_id,
    )
    return MessageResponse(message="Share revoked successfully")


@router.get("/shared-with-me", response_model=SharedDevicesListOut)
async def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all devices shared with the current user.
    """
    stmt = (
        select(DeviceShare, UserDevice, User)
        .join(UserDevice, and_(
            UserDevice.device_id == DeviceShare.device_id,
            UserDevice.user_id == DeviceShare.owner_user_id,
        ))
        .join(User, User.user_id == DeviceShare.owner_user_id)
        .where(
            and_(
                DeviceShare.shared_with_user_id == current_user.user_id,
                DeviceShare.is_active,
            )
        )
        .order_by(DeviceShare.shared_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    devices = []
    for share, user_device, owner in rows:
        devices.append(
            SharedDeviceOut(
                device_id=share.device_id,
                device_nickname=user_device.nickname,
                owner_nickname=owner.nickname,
                owner_email=owner.email,
                permissions=share.permissions,
                shared_at=share.shared_at,
            )
        )

    return SharedDevicesListOut(devices=devices, total=len(devices))
