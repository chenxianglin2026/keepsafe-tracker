"""
KeepSafe Backend — LBS (Base Station) Location Resolver

Resolves cell_id → estimated lat/lng using OpenCellID or Baidu LBS API.
Results are cached in Redis for 7 days.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.redis_cache import get_lbs_cache, set_lbs_cache

logger = logging.getLogger("keepsafe.lbs")


def parse_cell_id(cell_id: str) -> Optional[dict]:
    """
    Parse cell_id string "MCC-MNC-LAC-CellID" → dict.

    Args:
        cell_id: e.g. "460-00-12345-6789"
                 Format: MCC-MNC-LAC-CellID
    Returns:
        dict with mcc, mnc, lac, cellid or None if unparseable.
    """
    try:
        parts = cell_id.split("-")
        if len(parts) < 4:
            logger.warning("Invalid cell_id format: %s", cell_id)
            return None
        return {
            "mcc": int(parts[0]),
            "mnc": int(parts[1]),
            "lac": int(parts[2]),
            "cellid": int(parts[3]),
        }
    except (ValueError, IndexError) as exc:
        logger.warning("Failed to parse cell_id '%s': %s", cell_id, exc)
        return None


def _cell_cache_key(cell_id: str) -> str:
    """Build Redis cache key for a cell ID."""
    return f"cell:{cell_id}"


async def resolve_lbs_opencellid(cell_id: str) -> Optional[dict]:
    """
    Resolve cell_id via OpenCellID API.

    Returns dict with lat, lng, accuracy, source or None.
    """
    parsed = parse_cell_id(cell_id)
    if not parsed:
        return None

    # Check cache first
    cache_key = _cell_cache_key(cell_id)
    cached = await get_lbs_cache(cache_key)
    if cached:
        logger.debug("LBS cache hit for %s", cell_id)
        return cached

    url = "https://eu1.unwiredlabs.com/v2/process.php"
    payload = {
        "token": settings.opencellid_api_key,
        "mcc": parsed["mcc"],
        "mnc": parsed["mnc"],
        "cells": [{"lac": parsed["lac"], "cid": parsed["cellid"]}],
        "address": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "ok":
            result = {
                "lat": data["lat"],
                "lng": data["lon"],
                "accuracy": data.get("accuracy", 1000),
                "source": "opencellid",
            }
            await set_lbs_cache(cache_key, result)
            logger.info("LBS resolved %s → (%.4f, %.4f)", cell_id, result["lat"], result["lng"])
            return result
        else:
            logger.warning("OpenCellID returned error for %s: %s", cell_id, data.get("message", "unknown"))
            return None

    except httpx.RequestError as exc:
        logger.error("HTTP error resolving LBS for %s: %s", cell_id, exc)
        return None
    except (KeyError, ValueError) as exc:
        logger.error("Parse error in LBS response for %s: %s", cell_id, exc)
        return None


async def resolve_lbs_baidu(cell_id: str) -> Optional[dict]:
    """
    Resolve cell_id via Baidu LBS API (placeholder).

    Returns dict with lat, lng, accuracy, source or None.
    """
    # Baidu LBS API integration placeholder
    # Endpoint: https://api.map.baidu.com/location/ip
    logger.warning("Baidu LBS not yet implemented for %s", cell_id)
    return None


async def resolve_lbs(cell_id: str) -> Optional[dict]:
    """
    Resolve cell_id to estimated lat/lng.

    Uses configured LBS source (opencellid or baidu).
    Falls back to OpenCellID if configured source fails.
    """
    if not cell_id:
        return None

    if settings.lbs_source == "baidu":
        result = await resolve_lbs_baidu(cell_id)
        if result:
            return result
        logger.info("Baidu LBS failed, falling back to OpenCellID")
        return await resolve_lbs_opencellid(cell_id)

    return await resolve_lbs_opencellid(cell_id)
