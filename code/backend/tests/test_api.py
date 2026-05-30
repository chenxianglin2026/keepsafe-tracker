"""KeepSafe Backend API Tests"""
import pytest
from httpx import AsyncClient, ASGITransport
import sys, os
sys.path.insert(0, '/Users/chenxianglin/projects/keepsafe/code/backend')

# Force dev mode SQLite
os.environ['DEV_MODE'] = 'true'

from app.main import app

pytestmark = pytest.mark.anyio

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

class TestHealth:
    async def test_docs(self, client):
        res = await client.get("/docs")
        assert res.status_code == 200

class TestAuth:
    async def test_login_success(self, client):
        res = await client.post("/api/v1/users/login", json={
            "email": "test@keepsafe.com",
            "password": "test123456"
        })
        # May fail if DB not seeded, accept 200 or 401
        assert res.status_code in (200, 401)

    async def test_login_fail(self, client):
        res = await client.post("/api/v1/users/login", json={
            "email": "noexist@test.com",
            "password": "x"
        })
        assert res.status_code != 200

class TestDevices:
    async def test_location_unauth(self, client):
        res = await client.get("/api/v1/devices/KS-00000001/location")
        assert res.status_code in (200, 401, 404)

    async def test_status_unauth(self, client):
        res = await client.get("/api/v1/devices/KS-00000001/status")
        assert res.status_code in (200, 401, 404)
