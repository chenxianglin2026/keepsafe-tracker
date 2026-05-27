"""Test user creation and password hashing."""
import asyncio
from app.db import engine, User, async_session_factory
from sqlalchemy import select
from app.api.users import hash_password
import uuid


async def test():
    async with async_session_factory() as db:
        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            email="test2@test.com",
            hashed_password=hash_password("test123"),
            nickname="Test",
        )
        db.add(user)
        await db.commit()
        print(f"Created user: {user_id}")

        stmt = select(User).where(User.email == "test2@test.com")
        result = await db.execute(stmt)
        u = result.scalar_one_or_none()
        print(f"Found: {u.user_id} {u.email}")

    await engine.dispose()

asyncio.run(test())
