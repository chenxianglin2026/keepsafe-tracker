"""
KeepSafe Backend — FastAPI Application Entry Point

Usage:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import engine
from app.mqtt_client import get_mqtt_client
from app.redis_cache import close_redis
from app.push.fcm import init_fcm
from app.chat_agent import chat_consumer_loop
from app.db import async_session_factory

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("keepsafe")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup & shutdown hooks."""
    # ── Startup ──
    logger.info("KeepSafe backend starting...")

    # 1. Initialize Firebase (FCM)
    init_fcm(settings.fcm_credentials_path)

    # 2. Connect to EMQX
    mqtt = get_mqtt_client()
    try:
        await mqtt.connect()
        logger.info("EMQX MQTT client connected")
    except Exception as exc:
        logger.error("Failed to connect to EMQX: %s", exc)
        logger.warning("Backend will start without MQTT (retry on first message)")

    # 3. Start chat consumer background task
    chat_task = asyncio.create_task(chat_consumer_loop())

    # 4. Start device offline detection background task
    offline_task = asyncio.create_task(_offline_detection_loop())

    yield

    # ── Shutdown ──
    logger.info("KeepSafe backend shutting down...")

    # 0. Cancel chat consumer and offline detector
    chat_task.cancel()
    try:
        await chat_task
    except asyncio.CancelledError:
        pass
    offline_task.cancel()
    try:
        await offline_task
    except asyncio.CancelledError:
        pass

    # 1. Disconnect MQTT
    try:
        await mqtt.disconnect()
    except Exception as exc:
        logger.warning("MQTT disconnect error: %s", exc)

    # 2. Close Redis
    await close_redis()

    # 3. Close DB engine
    await engine.dispose()

    logger.info("KeepSafe backend shut down complete")


# ── Offline Detection Loop ──────────────────────────────────

async def _offline_detection_loop():
    """Background task: periodically checks for offline devices and creates alerts.

    Runs every 60 seconds. A device is considered offline if:
    - Its Redis status entry has expired (no update in 180s), OR
    - Its DB last_seen is older than 5 minutes.

    Throttled: only generates one offline alert per device per hour.
    """
    await asyncio.sleep(30)  # Initial delay so the system settles

    while True:
        try:
            from app.redis_cache import get_redis
            from sqlalchemy import select as sa_select
            from app.db import Device, UserDevice

            r = await get_redis()

            async with async_session_factory() as session:
                # Find devices whose last_seen is older than 5 minutes
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

                result = await session.execute(
                    sa_select(Device).where(
                        Device.last_seen.isnot(None),
                        Device.last_seen < cutoff,
                        Device.is_active == True,  # noqa: E712
                    )
                )
                stale_devices = result.scalars().all()

                for device in stale_devices:
                    # Check Redis: if status entry still exists, device is probably online
                    # (Redis TTL is 180s, so if it exists, last update was within 180s)
                    status_key = f"device:{device.device_id}:status"
                    redis_status = await r.get(status_key)
                    if redis_status:
                        continue  # Redis still has status, device is online

                    # Throttle: only one offline alert per hour per device
                    throttle_key = f"offline_throttle:{device.device_id}"
                    if await r.exists(throttle_key):
                        continue

                    await r.set(throttle_key, "1", ex=3600)  # 1 hour throttle

                    # Check if the device is bound to any user
                    bind_result = await session.execute(
                        sa_select(UserDevice).where(
                            UserDevice.device_id == device.device_id,
                            UserDevice.is_bound == True,  # noqa: E712
                        )
                    )
                    binding = bind_result.scalar_one_or_none()

                    if not binding:
                        continue  # Unbound device, skip

                    # Create offline alert
                    await session.execute(
                        """
                        INSERT INTO alerts (device_id, ts, alert_type, payload)
                        VALUES (:device_id, :ts, 'offline', :payload)
                        """,
                        {
                            "device_id": device.device_id,
                            "ts": datetime.now(timezone.utc),
                            "payload": json.dumps({
                                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                                "reason": "device_stopped_reporting",
                            }),
                        },
                    )
                    await session.commit()
                    logger.warning("Offline alert created for %s (last seen: %s)",
                                   device.device_id, device.last_seen)

            await asyncio.sleep(60)  # Check every 60 seconds

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Offline detection error: %s", exc, exc_info=True)
            await asyncio.sleep(60)


# ── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="KeepSafe Backend API",
    description="KeepSafe 防丢器定位器后端服务",
    version="1.1.0",
    lifespan=lifespan,
    # Don't auto-redirect trailing slashes — clients must match exactly
    # This avoids confusion when some clients send /path and others /path/
    redirect_slashes=False,
)

# CORS — allow mobile app and web dashboard
# In dev_mode, allow all origins. In production, restrict to CORS_ORIGINS env var.
if settings.dev_mode:
    allow_origins = ["*"]
else:
    cors_origins_str = settings.cors_origins.strip()
    allow_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()] if cors_origins_str else []
    if not allow_origins:
        logger.warning("CORS_ORIGINS is empty in production mode; no cross-origin requests will be allowed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ─────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    """Basic health check endpoint."""
    mqtt = get_mqtt_client()
    return {
        "status": "ok",
        "service": "keepsafe-backend",
        "version": "1.1.0",
        "mqtt_connected": mqtt.is_connected,
    }


# ── Register Routers ─────────────────────────────────────────

from app.api.auth import router as auth_router  # noqa: E402
from app.api.devices import router as devices_router  # noqa: E402
from app.api.users import router as users_router  # noqa: E402
from app.api.fences import router as fences_router  # noqa: E402
from app.api.alerts import router as alerts_router  # noqa: E402
from app.api.sharing import router as sharing_router  # noqa: E402
from app.chat_agent import router as chat_router  # noqa: E402

app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(users_router)
app.include_router(fences_router)
app.include_router(alerts_router)
app.include_router(sharing_router)
app.include_router(chat_router)

# 全局 500 错误处理 — 开发调试用
from fastapi.responses import JSONResponse as JR  # noqa: E402
import traceback  # noqa: E402


@app.exception_handler(Exception)
async def global_500_handler(request, exc):
    tb = traceback.format_exc()
    logger.error("Unhandled 500 error:\n%s", tb)
    # Do NOT leak traceback to clients in production
    if settings.dev_mode:
        return JR(status_code=500, content={"detail": str(exc)[:200], "trace": tb.split("\n")[-5:]})
    return JR(status_code=500, content={"detail": "Internal server error"})

# 静态文件服务 — 上传目录
import os  # noqa: E402
uploads_dir = os.path.expanduser("~/projects/keepsafe/uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


# ── Main Entry ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level,
        reload=True,
    )
