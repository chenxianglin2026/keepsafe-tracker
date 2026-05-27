"""
KeepSafe Backend — FastAPI Application Entry Point

Usage:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import engine
from app.mqtt_client import get_mqtt_client
from app.redis_cache import close_redis
from app.push.fcm import init_fcm
from app.chat_agent import chat_consumer_loop

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

    yield

    # ── Shutdown ──
    logger.info("KeepSafe backend shutting down...")

    # 0. Cancel chat consumer
    chat_task.cancel()
    try:
        await chat_task
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

from app.api.auth import router as auth_router
from app.api.devices import router as devices_router
from app.api.users import router as users_router
from app.api.fences import router as fences_router
from app.api.alerts import router as alerts_router
from app.chat_agent import router as chat_router

app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(users_router)
app.include_router(fences_router)
app.include_router(alerts_router)
app.include_router(chat_router)

# 全局 500 错误处理 — 开发调试用
from fastapi.responses import JSONResponse as JR
import traceback

@app.exception_handler(Exception)
async def global_500_handler(request, exc):
    tb = traceback.format_exc()
    logger.error("Unhandled 500 error:\n%s", tb)
    return JR(status_code=500, content={"detail": str(exc)[:200], "trace": tb.split("\n")[-5:]})

# 静态文件服务 — 上传目录
import os
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
