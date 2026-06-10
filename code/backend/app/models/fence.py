"""
KeepSafe Backend — Fence Model

Geofence for a device: circular area defined by center (lat/lng) and radius,
or polygon area defined by vertices.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped

from app.db import Base


class Fence(Base):
    __tablename__ = "fences"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = Column(String(16), nullable=False, index=True)
    name: Mapped[str] = Column(String(128), nullable=False)
    fence_type: Mapped[str] = Column(String(16), default="circle", nullable=False)
    lat: Mapped[float | None] = Column(Float, nullable=True)
    lng: Mapped[float | None] = Column(Float, nullable=True)
    radius: Mapped[float | None] = Column(Float, nullable=True)
    vertices: Mapped[str | None] = Column(Text, nullable=True)
    enabled: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
