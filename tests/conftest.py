from __future__ import annotations

import pytest_asyncio

from bot.database.base import Base
from bot.database.session import Database


@pytest_asyncio.fixture
async def database():
    db = Database.create("sqlite+aiosqlite:///:memory:")
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield db
    finally:
        await db.close()
