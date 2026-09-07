from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, Update, User

from bot.core.channel_membership import ChannelMembershipMiddleware


@pytest.mark.asyncio
async def test_forced_join_answers_message_wrapped_in_update() -> None:
    telegram_user = User(id=12345, is_bot=False, first_name="Customer")
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    update = MagicMock(spec=Update)
    update.callback_query = None
    update.message = message
    handler = AsyncMock()
    channel = SimpleNamespace(title="Persian Shop", invite_link="https://t.me/persianshop")

    with (
        patch(
            "bot.core.channel_membership.UserService.is_admin",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "bot.core.channel_membership.ChannelService.missing_for",
            new=AsyncMock(return_value=[channel]),
        ),
    ):
        result = await ChannelMembershipMiddleware()(
            handler,
            update,
            {
                "event_from_user": telegram_user,
                "session": MagicMock(),
                "bot": MagicMock(),
                "db_user": SimpleNamespace(id=1),
            },
        )

    assert result is None
    handler.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert "ابتدا عضو کانال‌های زیر شوید" in message.answer.await_args.args[0]
