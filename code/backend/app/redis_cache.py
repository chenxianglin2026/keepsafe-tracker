"""
KeepSafe Backend — Redis Cache Layer

Caches device status, latest location, and LBS lookups.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("keepsafe.redis")

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return singleton async Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


# ── Device Status ────────────────────────────────────────────

async def set_device_status(device_id: str, status: dict) -> None:
    """Cache device online status + battery + RSSI. TTL = 180s."""
    r = await get_redis()
    key = f"device:{device_id}:status"
    await r.set(key, json.dumps(status), ex=settings.device_status_ttl)


async def get_device_status(device_id: str) -> Optional[dict]:
    """Get cached device status. None = offline."""
    try:
        r = await get_redis()
        key = f"device:{device_id}:status"
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        logger.warning("Redis unavailable for get_device_status, returning None")
    return None


# ── Latest Location ──────────────────────────────────────────

async def set_latest_location(device_id: str, loc: dict) -> None:
    """Cache the latest location for a device. TTL = 180s."""
    r = await get_redis()
    key = f"device:{device_id}:latest_location"
    await r.set(key, json.dumps(loc), ex=settings.device_status_ttl)


async def get_latest_location(device_id: str) -> Optional[dict]:
    """Get cached latest location. None = no data."""
    try:
        r = await get_redis()
        key = f"device:{device_id}:latest_location"
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        logger.warning("Redis unavailable for get_latest_location, returning None")
    return None


# ── LBS Cache ────────────────────────────────────────────────

async def set_lbs_cache(cell_key: str, result: dict) -> None:
    """Cache LBS resolution result. TTL = 7 days."""
    r = await get_redis()
    await r.set(f"lbs:{cell_key}", json.dumps(result), ex=settings.lbs_cache_ttl)


async def get_lbs_cache(cell_key: str) -> Optional[dict]:
    """Get cached LBS resolution."""
    r = await get_redis()
    data = await r.get(f"lbs:{cell_key}")
    if data:
        return json.loads(data)
    return None
