"""
KeepSafe Backend — Database Connection & Models

Uses SQLAlchemy 2.0 async with asyncpg.
Sync engine available for alembic / migrations.
"""

from __future__ import annotations

from sqlalchemy import Column, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Async Engine ──────────────────────────────────────────────
if settings.dev_mode:
    ASYNC_DB_URL = "sqlite+aiosqlite:///./keepsafe_dev.db"
    engine = create_async_engine(
        ASYNC_DB_URL,
        echo=(settings.log_level == "debug"),
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=(settings.log_level == "debug"),
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Declarative Base ──────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────

class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(16), primary_key=True)
    device_token = Column(String(64), nullable=False)
    fw_version = Column(String(16), nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)


class Location(Base):
    """TimescaleDB hypertable — mapped but managed via raw SQL inserts for speed."""

    __tablename__ = "locations"

    device_id = Column(String(16), primary_key=True)
    ts = Column(DateTime(timezone=True), primary_key=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    alt = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    satellites = Column(Integer, nullable=True)
    fix_type = Column(Integer, nullable=True)
    cell_id = Column(String(32), nullable=True)
    battery = Column(Integer, nullable=True)
    charging = Column(Boolean, nullable=True)
    rssi = Column(Integer, nullable=True)
    fw_version = Column(String(16), nullable=True)


class SosEvent(Base):
    __tablename__ = "sos_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(16), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    battery = Column(Integer, nullable=True)
    trigger_duration_ms = Column(Integer, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(16), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    alert_type = Column(String(32), nullable=False)
    payload = Column(Text, nullable=True)  # JSONB in production, Text in SQLite dev mode
    is_read = Column(Boolean, default=False)


class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    device_id = Column(String(16), nullable=False)
    nickname = Column(String(64), nullable=True)
    bound_at = Column(DateTime(timezone=True), server_default=func.now())
    is_bound = Column(Boolean, default=True)


class Fence(Base):
    __tablename__ = "fences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(16), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    radius = Column(Float, nullable=False)  # meters
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    nickname = Column(String(128), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    phone = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserPushToken(Base):
    __tablename__ = "user_push_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    platform = Column(String(16), nullable=False)  # "ios" or "android"
    token = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Unique constraint per user + platform
        UniqueConstraint("user_id", "platform", name="uq_user_push_token_platform"),
    )
