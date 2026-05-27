"""
KeepSafe Backend — Fence Model

Geofence for a device: circular area defined by center (lat/lng) and radius.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped

from app.db import Base


class Fence(Base):
    __tablename__ = "fences"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = Column(String(16), nullable=False, index=True)
    name: Mapped[str] = Column(String(128), nullable=False)
    lat: Mapped[float] = Column(Float, nullable=False)
    lng: Mapped[float] = Column(Float, nullable=False)
    radius: Mapped[float] = Column(Float, nullable=False)  # meters
    enabled: Mapped[bool] = Column(Boolean, default=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
