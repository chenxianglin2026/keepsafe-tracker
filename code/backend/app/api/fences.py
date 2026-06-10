"""
KeepSafe Backend — Fence (Geofence) Management API

Endpoints for creating, reading, updating, and deleting geofences
associated with a device. Supports both circular and polygon fences.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import get_current_user, User
from app.db import get_db, Device, Fence, UserDevice

logger = logging.getLogger("keepsafe.api.fences")

router = APIRouter(
    prefix="/api/v1/devices/{device_id}/fences",
    tags=["fences"],
)


# ── Pydantic Schemas ───────────────────────────────────────────

class VertexItem(BaseModel):
    """A single polygon vertex with lat/lng."""
    lat: float
    lng: float


class FenceCreateRequest(BaseModel):
    name: str
    fence_type: str = "circle"  # "circle" or "polygon"
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[float] = None  # meters
    vertices: Optional[List[VertexItem]] = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_fence_data(self):
        if self.fence_type == "circle":
            if self.lat is None or self.lng is None or self.radius is None:
                raise ValueError("lat, lng, and radius are required for circle fences")
            if self.radius <= 0:
                raise ValueError("radius must be positive")
        elif self.fence_type == "polygon":
            if not self.vertices or len(self.vertices) < 3:
                raise ValueError("polygon fences require at least 3 vertices")
            for v in self.vertices:
                if v.lat < -90 or v.lat > 90:
                    raise ValueError(f"vertex lat {v.lat} out of range [-90, 90]")
                if v.lng < -180 or v.lng > 180:
                    raise ValueError(f"vertex lng {v.lng} out of range [-180, 180]")
        else:
            raise ValueError("fence_type must be 'circle' or 'polygon'")
        return self


class FenceUpdateRequest(BaseModel):
    name: Optional[str] = None
    fence_type: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[float] = None
    vertices: Optional[List[VertexItem]] = None
    enabled: Optional[bool] = None


class FenceOut(BaseModel):
    id: int
    device_id: str
    name: str
    fence_type: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[float] = None
    vertices: Optional[List[VertexItem]] = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        """Override to parse vertices JSON string into list."""
        if hasattr(obj, "vertices") and isinstance(obj.vertices, str):
            try:
                obj.vertices = [VertexItem(**v) for v in json.loads(obj.vertices)]
            except (json.JSONDecodeError, TypeError):
                obj.vertices = None
        return super().model_validate(obj, *args, **kwargs)


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
        # Also check shared access
        from app.db import DeviceShare
        share_stmt = select(DeviceShare).where(
            and_(
                DeviceShare.shared_with_user_id == current_user.user_id,
                DeviceShare.device_id == device_id,
                DeviceShare.is_active,
            )
        )
        share_result = await db.execute(share_stmt)
        if share_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this device",
            )


# ── Endpoints ──────────────────────────────────────────────────

@router.get("", response_model=FenceListOut)
async def list_fences(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all geofences for a device.
    """
    await _ensure_device_exists(device_id, db)
    await _verify_device_ownership(device_id, current_user, db)

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new geofence for a device. Supports circle and polygon types.
    """
    await _ensure_device_exists(device_id, db)
    await _verify_device_ownership(device_id, current_user, db)

    vertices_json = None
    if req.vertices:
        vertices_json = json.dumps([v.model_dump() for v in req.vertices])

    fence = Fence(
        device_id=device_id,
        name=req.name,
        fence_type=req.fence_type,
        lat=req.lat,
        lng=req.lng,
        radius=req.radius,
        vertices=vertices_json,
        enabled=req.enabled,
    )
    db.add(fence)
    await db.commit()
    await db.refresh(fence)

    logger.info(
        "Fence created: id=%d device=%s name=%s type=%s",
        fence.id,
        device_id,
        req.name,
        req.fence_type,
    )
    return FenceOut.model_validate(fence)


@router.get("/{fence_id}", response_model=FenceOut)
async def get_fence(
    device_id: str,
    fence_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single geofence by ID.
    """
    await _verify_device_ownership(device_id, current_user, db)
    fence = await _get_fence_or_404(device_id, fence_id, db)
    return FenceOut.model_validate(fence)


@router.put("/{fence_id}", response_model=FenceOut)
async def update_fence(
    device_id: str,
    fence_id: int,
    req: FenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a geofence. Only provided fields will be updated.
    Supports type switching between circle and polygon.
    """
    await _verify_device_ownership(device_id, current_user, db)
    fence = await _get_fence_or_404(device_id, fence_id, db)

    if req.name is not None:
        fence.name = req.name
    if req.fence_type is not None:
        fence.fence_type = req.fence_type
    if req.lat is not None:
        fence.lat = req.lat
    if req.lng is not None:
        fence.lng = req.lng
    if req.radius is not None:
        fence.radius = req.radius
    if req.vertices is not None:
        fence.vertices = json.dumps([v.model_dump() for v in req.vertices])
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a geofence.
    """
    await _verify_device_ownership(device_id, current_user, db)
    fence = await _get_fence_or_404(device_id, fence_id, db)
    await db.delete(fence)
    await db.commit()

    logger.info("Fence deleted: id=%d device=%s", fence_id, device_id)
    return MessageResponse(message="Fence deleted successfully")
