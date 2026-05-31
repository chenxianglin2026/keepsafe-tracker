"""KeepSafe Backend API Tests"""
import pytest
import sys, os, hashlib, asyncio
sys.path.insert(0, '/Users/chenxianglin/projects/keepsafe/code/backend')
os.environ['DEV_MODE'] = 'true'

# Clean DB
db_path = os.path.expanduser('~/projects/keepsafe/code/backend/keepsafe_dev.db')
if os.path.exists(db_path):
    os.remove(db_path)

from app.main import app
from app.db import Base, engine, async_session_factory, User
from sqlalchemy import select

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    async def _s():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        salt = os.urandom(16)
        pw = salt.hex() + "$" + hashlib.sha256(salt + b"test123456").hexdigest()
        async with async_session_factory() as s:
            r = await s.execute(select(User).where(User.email == "test@keepsafe.com"))
            if not r.scalar_one_or_none():
                s.add(User(user_id="test-uuid-001", email="test@keepsafe.com", hashed_password=pw, nickname="Test"))
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

class TestHealth:
    async def test_docs(self, client):
        assert (await client.get("/docs")).status_code == 200

class TestAuth:
    async def test_login_ok(self, client):
        r = await client.post("/api/v1/users/login", json={"email":"test@keepsafe.com","password":"test123456"})
        assert r.status_code == 200

    async def test_login_fail(self, client):
        r = await client.post("/api/v1/users/login", json={"email":"x@x.com","password":"x"})
        assert r.status_code != 200

class TestDevices:
    async def test_location(self, client):
        assert (await client.get("/api/v1/devices/KS-00000001/location")).status_code in (200,401,404)

    async def test_status(self, client):
        assert (await client.get("/api/v1/devices/KS-00000001/status")).status_code in (200,401,404)
