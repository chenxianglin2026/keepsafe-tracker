"""
KeepSafe Backend — Devices REST API

Endpoints for retrieving device status, location history, SOS events,
and managing device bindings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import get_current_user, User
from app.db import get_db, Device, Location, SosEvent, UserDevice
from app.redis_cache import get_device_status, get_latest_location

logger = logging.getLogger("keepsafe.api.devices")

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


# ── Pydantic Schemas ─────────────────────────────────────────

class LocationOut(BaseModel):
    device_id: str
    ts: datetime
    lat: Optional[float] = None
    lng: Optional[float] = None
    alt: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    accuracy: Optional[float] = None
    satellites: Optional[int] = None
    fix_type: Optional[int] = None
    cell_id: Optional[str] = None
    battery: Optional[int] = None
    charging: Optional[bool] = None
    rssi: Optional[int] = None
    fw_version: Optional[str] = None

    class Config:
        from_attributes = True


class DeviceStatusOut(BaseModel):
    device_id: str
    online: bool
    battery: Optional[int] = None
    charging: Optional[bool] = None
    rssi: Optional[int] = None
    last_seen: Optional[datetime] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class SosEventOut(BaseModel):
    id: int
    device_id: str
    ts: datetime
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy: Optional[float] = None
    battery: Optional[int] = None
    trigger_duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


class BindRequest(BaseModel):
    user_id: str
    device_id: str
    token: str
    nickname: Optional[str] = None


class BindResponse(BaseModel):
    success: bool
    message: str


# ── Auth Helper ────────────────────────────────────────────────

async def _verify_device_ownership(
    device_id: str,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Verify the current user is bound to this device. Raises 403 if not."""
    stmt = select(UserDevice).where(
        and_(
            UserDevice.user_id == current_user.user_id,
            UserDevice.device_id == device_id,
            UserDevice.is_bound,
        )
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()
    if binding is None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this device",
        )


# ── Endpoints ────────────────────────────────────────────────

@router.get("/{device_id}/location", response_model=Optional[LocationOut])
async def get_device_location(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the latest location for a device.
    Reads from Redis cache first, falls back to TimescaleDB.
    """
    await _verify_device_ownership(device_id, current_user, db)

    # Try Redis first (fast path)
    cached = await get_latest_location(device_id)
    if cached:
        return LocationOut(**cached)

    # Fallback to DB
    stmt = (
        select(Location)
        .where(Location.device_id == device_id)
        .order_by(desc(Location.ts))
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")

    loc = row[0] if row._fields == ('Location',) else row
    return LocationOut.model_validate(loc)


@router.get("/{device_id}/status", response_model=DeviceStatusOut)
async def get_device_status_endpoint(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get device online status, battery level, RSSI, and last known position.
    Reads from Redis cache first.
    """
    await _verify_device_ownership(device_id, current_user, db)

    # Try Redis
    cached = await get_device_status(device_id)
    if cached:
        return DeviceStatusOut(
            device_id=device_id,
            online=True,
            battery=cached.get("battery"),
            charging=cached.get("charging"),
            rssi=cached.get("rssi"),
            last_seen=datetime.fromisoformat(cached["last_seen"]) if cached.get("last_seen") else None,
            lat=cached.get("lat"),
            lng=cached.get("lng"),
        )

    # Fallback: check DB for last location & device record
    stmt = select(Device).where(Device.device_id == device_id)
    result = await db.execute(stmt)
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    # get_db 返回的 Row 是 (Device_obj,) 元组
    device = row[0] if row._fields == ('Device',) else row

    # Get latest location for position
    loc_stmt = (
        select(Location)
        .where(Location.device_id == device_id)
        .order_by(desc(Location.ts))
        .limit(1)
    )
    loc_result = await db.execute(loc_stmt)
    loc_row = loc_result.fetchone()
    loc = loc_row[0] if loc_row and loc_row._fields == ('Location',) else loc_row

    # Determine online status based on last_seen
    online = False
    if device.last_seen:
        # 确保 last_seen 和 now 都是 offset-aware
        ls = device.last_seen
        if ls.tzinfo is None:
            ls = ls.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - ls).total_seconds()
        online = delta < 180  # 3-minute threshold

    return DeviceStatusOut(
        device_id=device_id,
        online=online,
        battery=None,
        charging=None,
        rssi=None,
        last_seen=device.last_seen,
        lat=loc.lat if loc else None,
        lng=loc.lng if loc else None,
    )


@router.get("/{device_id}/history", response_model=List[LocationOut])
async def get_device_history(
    device_id: str,
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get location history (trajectory) for a device within a time range.
    """
    await _verify_device_ownership(device_id, current_user, db)

    if not from_:
        from_ = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if not to:
        to = datetime.now(timezone.utc)

    stmt = (
        select(Location)
        .where(
            and_(
                Location.device_id == device_id,
                Location.ts >= from_,
                Location.ts <= to,
            )
        )
        .order_by(desc(Location.ts))
        .limit(limit)
    )

    result = await db.execute(stmt)
    locations = result.scalars().all()

    return [LocationOut.model_validate(loc) for loc in locations]


@router.get("/{device_id}/sos/events", response_model=List[SosEventOut])
async def get_sos_events(
    device_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get SOS event history for a device.
    """
    await _verify_device_ownership(device_id, current_user, db)

    stmt = (
        select(SosEvent)
        .where(SosEvent.device_id == device_id)
        .order_by(desc(SosEvent.ts))
        .limit(limit)
    )

    result = await db.execute(stmt)
    events = result.scalars().all()

    return [SosEventOut.model_validate(evt) for evt in events]


@router.post("/bind", response_model=BindResponse)
async def bind_device(
    req: BindRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bind a device to a user account.

    Validates the device token before binding.
    """
    # Verify req.user_id matches the authenticated user
    if req.user_id != current_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot bind device to a different user account",
        )

    # Verify device exists and token matches
    stmt = select(Device).where(Device.device_id == req.device_id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if device is None:
        # Auto-register device if it doesn't exist yet
        device = Device(
            device_id=req.device_id,
            device_token=req.token,
            fw_version=None,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(device)
        await db.commit()
        logger.info("Auto-registered device %s during bind", req.device_id)
    elif device.device_token != req.token:
        raise HTTPException(status_code=403, detail="Device token mismatch")

    # Check existing binding
    bind_stmt = select(UserDevice).where(
        and_(
            UserDevice.user_id == req.user_id,
            UserDevice.device_id == req.device_id,
        )
    )
    bind_result = await db.execute(bind_stmt)
    existing = bind_result.scalar_one_or_none()

    if existing:
        if not existing.is_bound:
            existing.is_bound = True
            await db.commit()
            return BindResponse(success=True, message="Device re-bound successfully")
        return BindResponse(success=True, message="Device already bound")

    # Create binding
    binding = UserDevice(
        user_id=req.user_id,
        device_id=req.device_id,
        nickname=req.nickname,
    )
    db.add(binding)
    await db.commit()

    logger.info("Device %s bound to user %s", req.device_id, req.user_id)
    return BindResponse(success=True, message="Device bound successfully")


@router.delete("/{device_id}/bind", response_model=BindResponse)
async def unbind_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unbind a device from the authenticated user's account.
    """
    await _verify_device_ownership(device_id, current_user, db)

    stmt = select(UserDevice).where(
        and_(
            UserDevice.user_id == current_user.user_id,
            UserDevice.device_id == device_id,
        )
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()

    if binding is None:
        raise HTTPException(status_code=404, detail="Binding not found")

    binding.is_bound = False
    await db.commit()

    logger.info("Device %s unbound from user %s", device_id, current_user.user_id)
    return BindResponse(success=True, message="Device unbound successfully")
