from __future__ import annotations

import pytest
from aiogram.types import User as TelegramUser

from bot.services.users import UserService


@pytest.mark.asyncio
async def test_new_user_always_starts_in_persian(database) -> None:
    async with database.session_factory() as session:
        user = await UserService(session).ensure_user(
            TelegramUser(
                id=91001,
                is_bot=False,
                first_name="English Client",
                language_code="en",
            )
        )
        assert user.language_code == "fa"


@pytest.mark.asyncio
async def test_existing_manual_language_choice_is_preserved(database) -> None:
    async with database.session_factory() as session:
        service = UserService(session)
        user = await service.ensure_user(
            TelegramUser(
                id=91002,
                is_bot=False,
                first_name="User",
                language_code="en",
            )
        )
        await service.set_language(user.id, "en")

        refreshed = await service.ensure_user(
            TelegramUser(
                id=91002,
                is_bot=False,
                first_name="User Updated",
                language_code="fa",
            )
        )
        assert refreshed.language_code == "en"
