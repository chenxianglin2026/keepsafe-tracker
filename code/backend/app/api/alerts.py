"""
KeepSafe Backend — Alerts REST API

Endpoints for listing and managing device alerts.
Requires user authentication — only shows alerts for the current user's devices.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import get_current_user, User
from app.db import get_db, Alert, UserDevice

logger = logging.getLogger("keepsafe.api.alerts")

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ── Pydantic Schemas ──────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    device_id: str
    ts: datetime
    alert_type: str
    payload: Optional[dict] = None
    is_read: bool

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


class PaginatedAlerts(BaseModel):
    items: List[AlertOut]
    total: int
    page: int
    page_size: int


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/", response_model=PaginatedAlerts)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated alert list for the current user's devices, ordered by ts descending.
    """
    # First, get the user's device IDs
    device_stmt = select(UserDevice.device_id).where(
        UserDevice.user_id == current_user.user_id,
        UserDevice.is_bound == True,
    )
    device_result = await db.execute(device_stmt)
    device_ids = [row[0] for row in device_result.all()]

    if not device_ids:
        return PaginatedAlerts(items=[], total=0, page=page, page_size=page_size)

    # Build query
    conditions = [Alert.device_id.in_(device_ids)]
    if alert_type is not None:
        conditions.append(Alert.alert_type == alert_type)
    if is_read is not None:
        conditions.append(Alert.is_read == is_read)

    # Count total
    from sqlalchemy import func as sa_func
    count_stmt = select(sa_func.count()).select_from(Alert).where(and_(*conditions))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    stmt = (
        select(Alert)
        .where(and_(*conditions))
        .order_by(desc(Alert.ts))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return PaginatedAlerts(
        items=[AlertOut.model_validate(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{alert_id}/read", response_model=AlertOut)
async def mark_alert_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a single alert as read. The alert must belong to one of the current user's devices.
    """
    # Verify the alert belongs to a device owned by the current user
    alert_stmt = select(Alert).where(Alert.id == alert_id)
    alert_result = await db.execute(alert_stmt)
    alert = alert_result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Check device ownership
    device_stmt = select(UserDevice).where(
        UserDevice.user_id == current_user.user_id,
        UserDevice.device_id == alert.device_id,
        UserDevice.is_bound == True,
    )
    device_result = await db.execute(device_stmt)
    binding = device_result.scalar_one_or_none()

    if binding is None:
        raise HTTPException(status_code=403, detail="Alert does not belong to your devices")

    alert.is_read = True
    await db.commit()
    await db.refresh(alert)

    logger.info("Alert %d marked as read by user %s", alert_id, current_user.user_id)
    return AlertOut.model_validate(alert)


@router.put("/read-all", response_model=MessageResponse)
async def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all alerts as read for the current user's devices.
    """
    # Get user's device IDs
    device_stmt = select(UserDevice.device_id).where(
        UserDevice.user_id == current_user.user_id,
        UserDevice.is_bound == True,
    )
    device_result = await db.execute(device_stmt)
    device_ids = [row[0] for row in device_result.all()]

    if not device_ids:
        return MessageResponse(message="No alerts to mark as read")

    # Update all unread alerts for these devices
    stmt = (
        update(Alert)
        .where(
            and_(
                Alert.device_id.in_(device_ids),
                Alert.is_read == False,
            )
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("All alerts marked as read by user %s", current_user.user_id)
    return MessageResponse(message="All alerts marked as read")
