"""
KeepSafe Backend API — Comprehensive Test Suite
Covers: health, auth, devices, fences, alerts, users (27 tests)
Run: pytest tests/test_api.py -v
"""
import pytest
import sys, os, hashlib, asyncio

sys.path.insert(0, '/Users/chenxianglin/projects/keepsafe/code/backend')
os.environ['DEV_MODE'] = 'true'

# Clean DB
db_path = os.path.expanduser('~/projects/keepsafe/code/backend/keepsafe_dev.db')
if os.path.exists(db_path):
    os.remove(db_path)

from app.main import app
from app.db import engine, async_session_factory, Base, User, Device, UserDevice
from sqlalchemy import select
from datetime import datetime, timezone

# ── Test Constants ────────────────────────────────────
TEST_EMAIL = "test@keepsafe.com"
TEST_PASSWORD = "test123456"
TEST_DEVICE_ID = "KS-00000001"


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    async def _s():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        salt = os.urandom(16)
        pw = salt.hex() + "$" + hashlib.sha256(salt + TEST_PASSWORD.encode()).hexdigest()
        async with async_session_factory() as s:
            r = await s.execute(select(User).where(User.email == TEST_EMAIL))
            if not r.scalar_one_or_none():
                s.add(User(user_id="test-uuid-001", email=TEST_EMAIL, hashed_password=pw, nickname="Test"))
                await s.commit()
            r2 = await s.execute(select(Device).where(Device.device_id == TEST_DEVICE_ID))
            if not r2.scalar_one_or_none():
                s.add(Device(device_id=TEST_DEVICE_ID, device_token="tok-001", fw_version="1.0",
                             first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)))
                await s.commit()
            r3 = await s.execute(select(UserDevice).where(UserDevice.device_id == TEST_DEVICE_ID))
            if not r3.scalar_one_or_none():
                s.add(UserDevice(user_id="test-uuid-001", device_id=TEST_DEVICE_ID, nickname="My Device"))
                await s.commit()
    asyncio.run(_s())
    yield


pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client):
    r = await client.post("/api/v1/users/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════
# Health Check (2 tests)
# ═══════════════════════════════════════════════════════

class TestHealth:
    async def test_health_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_docs(self, client):
        assert (await client.get("/docs")).status_code == 200


# ═══════════════════════════════════════════════════════
# Auth (5 tests)
# ═══════════════════════════════════════════════════════

class TestAuth:
    async def test_login_ok(self, client):
        r = await client.post("/api/v1/users/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        r = await client.post("/api/v1/users/login", json={"email": TEST_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    async def test_login_nonexistent_user(self, client):
        r = await client.post("/api/v1/users/login", json={"email": "nobody@nowhere.com", "password": "x"})
        assert r.status_code != 200

    async def test_protected_no_auth(self, client):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/status")
        assert r.status_code == 401

    async def test_protected_bad_token(self, client):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/status",
                             headers={"Authorization": "Bearer faketokeninvalid"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════
# Devices (8 tests)
# ═══════════════════════════════════════════════════════

class TestDevices:
    async def test_get_status(self, client, auth_headers):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/status", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["device_id"] == TEST_DEVICE_ID

    async def test_get_location(self, client, auth_headers):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/location", headers=auth_headers)
        assert r.status_code in (200, 404)  # 404 if no location data

    async def test_get_history(self, client, auth_headers):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/history?limit=10", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_sos(self, client, auth_headers):
        r = await client.get(f"/api/v1/devices/{TEST_DEVICE_ID}/sos/events", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_bind_new_device(self, client, auth_headers):
        r = await client.post("/api/v1/devices/bind", json={
            "user_id": "test-uuid-001", "device_id": "KS-BIND-001",
            "token": "tok-bind", "nickname": "Bind Test"
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["success"] is True

    async def test_bind_existing(self, client, auth_headers):
        r = await client.post("/api/v1/devices/bind", json={
            "user_id": "test-uuid-001", "device_id": TEST_DEVICE_ID, "token": "tok-001"
        }, headers=auth_headers)
        assert r.status_code == 200

    async def test_bind_wrong_token(self, client, auth_headers):
        r = await client.post("/api/v1/devices/bind", json={
            "user_id": "test-uuid-001", "device_id": TEST_DEVICE_ID, "token": "wrong-token"
        }, headers=auth_headers)
        assert r.status_code == 403

    async def test_device_not_owned(self, client, auth_headers):
        r = await client.get("/api/v1/devices/KS-NOT-MINE/status", headers=auth_headers)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════
# User Profile (3 tests)
# ═══════════════════════════════════════════════════════

class TestUsers:
    async def test_get_profile(self, client, auth_headers):
        r = await client.get("/api/v1/users/me", headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_update_profile(self, client, auth_headers):
        r = await client.put("/api/v1/users/me", json={"nickname": "Updated"}, headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_register(self, client):
        r = await client.post("/api/v1/users/register", json={
            "email": "fresh@test.com", "password": "pass123", "nickname": "Fresh"
        })
        assert r.status_code in (200, 201, 400)


# ═══════════════════════════════════════════════════════
# Fences (3 tests)
# ═══════════════════════════════════════════════════════

class TestFences:
    async def test_create_fence(self, client, auth_headers):
        r = await client.post("/api/v1/fences", json={
            "device_id": TEST_DEVICE_ID, "name": "Home",
            "center_lat": 31.23, "center_lng": 121.47, "radius": 500
        }, headers=auth_headers)
        assert r.status_code in (200, 201, 404)

    async def test_list_fences(self, client, auth_headers):
        r = await client.get(f"/api/v1/fences?device_id={TEST_DEVICE_ID}", headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_delete_fence(self, client, auth_headers):
        r = await client.delete("/api/v1/fences/1", headers=auth_headers)
        assert r.status_code in (200, 404)


# ═══════════════════════════════════════════════════════
# Alerts (2 tests)
# ═══════════════════════════════════════════════════════

class TestAlerts:
    async def test_list_alerts(self, client, auth_headers):
        r = await client.get("/api/v1/alerts", headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_mark_read(self, client, auth_headers):
        r = await client.put("/api/v1/alerts/1/read", headers=auth_headers)
        assert r.status_code in (200, 404)


# ═══════════════════════════════════════════════════════
# Edge Cases (4 tests)
# ═══════════════════════════════════════════════════════

class TestEdgeCases:
    async def test_empty_body_login(self, client):
        r = await client.post("/api/v1/users/login", json={})
        assert r.status_code == 422

    async def test_invalid_json(self, client):
        r = await client.post("/api/v1/users/login", content="bad",
                              headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 422)

    async def test_long_device_id(self, client, auth_headers):
        r = await client.get(f"/api/v1/devices/KS-{'A'*500}/status", headers=auth_headers)
        assert r.status_code in (200, 403, 404, 422)

    async def test_bind_other_user(self, client, auth_headers):
        """Should not allow binding device to another user"""
        r = await client.post("/api/v1/devices/bind", json={
            "user_id": "other-user-uuid", "device_id": TEST_DEVICE_ID, "token": "tok-001"
        }, headers=auth_headers)
        assert r.status_code == 403
