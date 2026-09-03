from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.channels import ChannelService

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class ChannelMembershipMiddleware(BaseMiddleware):
    """Require joining configured channels before customer interactions."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")
        bot: Bot | None = data.get("bot")

        if user is None or session is None or bot is None:
            return await handler(event, data)

        service = ChannelService(session)
        missing = await service.missing_for(bot, user.id)

        if isinstance(event, CallbackQuery) and event.data == "check_channel_membership":
            if not missing:
                await event.answer("✅ عضویت شما تایید شد.", show_alert=True)
                return await handler(event, data)
            await event.answer("❌ هنوز عضو همه کانال‌ها نشده‌اید.", show_alert=True)
            return None

        if not missing:
            return await handler(event, data)

        from bot.core.ui import button, keyboard

        rows = []
        for channel in missing:
            rows.append([button(f"📣 {channel.title}", url=channel.invite_link)])
        rows.append([button("✅ بررسی عضویت", callback_data="check_channel_membership")])

        text = "برای استفاده از ربات ابتدا عضو کانال‌های زیر شوید:"
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard(*rows))
        elif isinstance(event, CallbackQuery):
            await event.answer("ابتدا عضو کانال شوید.", show_alert=True)
        return None
