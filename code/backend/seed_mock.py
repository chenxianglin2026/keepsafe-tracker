"""Seed mock data for KeepSafe"""
import sys
sys.path.insert(0, '/Users/chenxianglin/projects/keepsafe/code/backend')

import asyncio
from datetime import datetime, timezone, timedelta
from app.db import engine, async_session_factory, Device, Location, UserDevice, Alert, Base


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # 2 mock devices
        d1 = Device(device_id="KS0001", device_token="mock_001", fw_version="1.0.0", is_active=True, last_seen=datetime.now(timezone.utc))
        d2 = Device(device_id="KS0002", device_token="mock_002", fw_version="1.0.0", is_active=True, last_seen=datetime.now(timezone.utc))
        session.add_all([d1, d2])
        await session.flush()

        # Bind to test user
        uid = "b437263a-9e61-426d-83d7-c576255cdc11"
        session.add_all([
            UserDevice(user_id=uid, device_id="KS0001", nickname="爷爷的定位器"),
            UserDevice(user_id=uid, device_id="KS0002", nickname="小宝的定位器"),
        ])

        # Locations
        now = datetime.now(timezone.utc)
        session.add_all([
            Location(device_id="KS0001", ts=now, lat=39.9087, lng=116.3975, battery=85, speed=0, accuracy=5),
            Location(device_id="KS0002", ts=now, lat=39.9163, lng=116.3972, battery=42, speed=2.3, accuracy=8),
        ])

        # Alerts
        session.add_all([
            Alert(device_id="KS0002", ts=now - timedelta(minutes=30), alert_type="sos", payload='{"message":"SOS求救"}', is_read=False),
            Alert(device_id="KS0001", ts=now - timedelta(hours=2), alert_type="fence", payload='{"fence":"家"}', is_read=False),
            Alert(device_id="KS0002", ts=now - timedelta(hours=5), alert_type="low_battery", payload='{"battery":42}', is_read=True),
        ])

        await session.commit()
        print("OK: 2 devices, 2 locations, 3 alerts seeded")


asyncio.run(seed())
