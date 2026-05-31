"""KeepSafe Backend API Tests"""
import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os
sys.path.insert(0, '/Users/chenxianglin/projects/keepsafe/code/backend')

# Force dev mode SQLite
os.environ['DEV_MODE'] = 'true'

from app.main import app
from app.db import Base, engine, async_session_factory, User


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables before tests and drop after."""
    import asyncio
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed test user
        import hashlib
        async with async_session_factory() as session:
            salt = os.urandom(16)
            pw_hash = salt.hex() + "$" + hashlib.sha256(salt + b"test123456").hexdigest()
            user = User(
                user_id="test-uuid-001",
                email="test@keepsafe.com",
                hashed_password=pw_hash,
                nickname="Test User",
            )
            session.add(user)
            await session.commit()
    asyncio.run(_setup())
    yield
    # Teardown: drop tables
    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.run(_teardown())


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
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

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
