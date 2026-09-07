from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.services.channels import ChannelService
from bot.services.users import UserService

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class ChannelMembershipMiddleware(BaseMiddleware):
    """Require joining configured channels before customer interactions."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")
        bot: Bot | None = data.get("bot")
        inner_event = _inner_event(event)

        if user is None or session is None or bot is None or inner_event is None:
            return await handler(event, data)

        db_user = data.get("db_user")
        if db_user is not None and await UserService(session).is_admin(db_user.id):
            return await handler(event, data)

        missing = await ChannelService(session).missing_for(bot, user.id)

        if isinstance(inner_event, CallbackQuery):
            try:
                callback_data = NavCallback.unpack(inner_event.data or "")
            except Exception:
                callback_data = None

            if callback_data and callback_data.action == "verify_join":
                if not missing:
                    await inner_event.answer("✅ عضویت شما تایید شد.", show_alert=True)
                    return await handler(event, data)
                await inner_event.answer("❌ هنوز عضو همه کانال‌ها نشده‌اید.", show_alert=True)
                return None

        if not missing:
            return await handler(event, data)

        from bot.core.ui import button, keyboard

        rows = [
            [InlineKeyboardButton(text=f"📣 {channel.title}", url=channel.invite_link)]
            for channel in missing
        ]
        rows.append([
            button(
                "✅ بررسی عضویت",
                callback_data=NavCallback(action="verify_join").pack(),
            )
        ])

        text = "برای استفاده از ربات ابتدا عضو کانال‌های زیر شوید:"
        if isinstance(inner_event, Message):
            await inner_event.answer(text, reply_markup=keyboard(*rows))
        elif isinstance(inner_event, CallbackQuery):
            await inner_event.answer("ابتدا عضو کانال شوید.", show_alert=True)
        return None


def _inner_event(event: TelegramObject) -> Message | CallbackQuery | None:
    """Return the actionable event when middleware is installed on updates."""
    if isinstance(event, (Message, CallbackQuery)):
        return event
    if isinstance(event, Update):
        return event.callback_query or event.message
    return None
