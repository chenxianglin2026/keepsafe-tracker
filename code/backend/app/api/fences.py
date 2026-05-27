"""
KeepSafe Backend — Fence (Geofence) Management API

Endpoints for creating, reading, updating, and deleting geofences
associated with a device.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Device, Fence

logger = logging.getLogger("keepsafe.api.fences")

router = APIRouter(
    prefix="/api/v1/devices/{device_id}/fences",
    tags=["fences"],
)


# ── Pydantic Schemas ───────────────────────────────────────────

class FenceCreateRequest(BaseModel):
    name: str
    lat: float
    lng: float
    radius: float  # meters
    enabled: bool = True


class FenceUpdateRequest(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[float] = None
    enabled: Optional[bool] = None


class FenceOut(BaseModel):
    id: int
    device_id: str
    name: str
    lat: float
    lng: float
    radius: float
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FenceListOut(BaseModel):
    fences: List[FenceOut]
    total: int


class MessageResponse(BaseModel):
    message: str


# ── Helper ─────────────────────────────────────────────────────

async def _ensure_device_exists(device_id: str, db: AsyncSession) -> None:
    """Verify the device exists, raise 404 if not."""
    stmt = select(Device).where(Device.device_id == device_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")


async def _get_fence_or_404(
    device_id: str, fence_id: int, db: AsyncSession
) -> Fence:
    """Fetch a fence by id, scoped to device_id. Raises 404 if not found."""
    stmt = select(Fence).where(
        and_(Fence.id == fence_id, Fence.device_id == device_id)
    )
    result = await db.execute(stmt)
    fence = result.scalar_one_or_none()
    if fence is None:
        raise HTTPException(status_code=404, detail="Fence not found")
    return fence


# ── Endpoints ──────────────────────────────────────────────────

@router.get("", response_model=FenceListOut)
async def list_fences(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all geofences for a device.
    """
    await _ensure_device_exists(device_id, db)

    stmt = (
        select(Fence)
        .where(Fence.device_id == device_id)
        .order_by(Fence.created_at.desc())
    )
    result = await db.execute(stmt)
    fences = result.scalars().all()

    return FenceListOut(
        fences=[FenceOut.model_validate(f) for f in fences],
        total=len(fences),
    )


@router.post("", response_model=FenceOut, status_code=201)
async def create_fence(
    device_id: str,
    req: FenceCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new geofence for a device.
    """
    await _ensure_device_exists(device_id, db)

    fence = Fence(
        device_id=device_id,
        name=req.name,
        lat=req.lat,
        lng=req.lng,
        radius=req.radius,
        enabled=req.enabled,
    )
    db.add(fence)
    await db.commit()
    await db.refresh(fence)

    logger.info(
        "Fence created: id=%d device=%s name=%s",
        fence.id,
        device_id,
        req.name,
    )
    return FenceOut.model_validate(fence)


@router.get("/{fence_id}", response_model=FenceOut)
async def get_fence(
    device_id: str,
    fence_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single geofence by ID.
    """
    fence = await _get_fence_or_404(device_id, fence_id, db)
    return FenceOut.model_validate(fence)


@router.put("/{fence_id}", response_model=FenceOut)
async def update_fence(
    device_id: str,
    fence_id: int,
    req: FenceUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a geofence. Only provided fields will be updated.
    """
    fence = await _get_fence_or_404(device_id, fence_id, db)

    if req.name is not None:
        fence.name = req.name
    if req.lat is not None:
        fence.lat = req.lat
    if req.lng is not None:
        fence.lng = req.lng
    if req.radius is not None:
        fence.radius = req.radius
    if req.enabled is not None:
        fence.enabled = req.enabled

    await db.commit()
    await db.refresh(fence)

    logger.info("Fence updated: id=%d device=%s", fence.id, device_id)
    return FenceOut.model_validate(fence)


@router.delete("/{fence_id}", response_model=MessageResponse)
async def delete_fence(
    device_id: str,
    fence_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a geofence.
    """
    fence = await _get_fence_or_404(device_id, fence_id, db)
    await db.delete(fence)
    await db.commit()

    logger.info("Fence deleted: id=%d device=%s", fence_id, device_id)
    return MessageResponse(message="Fence deleted successfully")
