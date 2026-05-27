"""Initialize database tables for KeepSafe dev mode."""
import asyncio
from app.db import engine, Base


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created OK")
    await engine.dispose()

asyncio.run(init())
