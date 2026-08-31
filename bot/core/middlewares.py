from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import AppSettings
from bot.core.exceptions import PersianShopError
from bot.services.users import UserService

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DatabaseSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise


class UserContextMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        session: AsyncSession | None = data.get("session")
        telegram_user = data.get("event_from_user")
        if session is None or telegram_user is None or telegram_user.is_bot:
            return await handler(event, data)
        user = await UserService(session).ensure_user(telegram_user)
        data["db_user"] = user
        if user.is_blocked:
            inner_event = _inner_event(event)
            if isinstance(inner_event, CallbackQuery):
                await inner_event.answer("دسترسی شما به فروشگاه محدود شده است.", show_alert=True)
            elif isinstance(inner_event, Message):
                await inner_event.answer("دسترسی شما به فروشگاه محدود شده است.")
            return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, settings: AppSettings) -> None:
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window_seconds
        self.events: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return await handler(event, data)
        now = monotonic()
        bucket = self.events[telegram_user.id]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            inner_event = _inner_event(event)
            if isinstance(inner_event, CallbackQuery):
                await inner_event.answer("کمی آهسته‌تر لطفاً…", show_alert=False)
            elif isinstance(inner_event, Message):
                await inner_event.answer("درخواست‌ها خیلی سریع ارسال شدند؛ چند ثانیه صبر کنید.")
            return None
        bucket.append(now)
        return await handler(event, data)


class BusinessErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        try:
            return await handler(event, data)
        except PersianShopError as exc:
            inner_event = _inner_event(event)
            if isinstance(inner_event, CallbackQuery):
                await inner_event.answer(str(exc), show_alert=True)
            elif isinstance(inner_event, Message):
                await inner_event.answer(f"⚠️ {exc}")
            return None
        except Exception:
            update_id = event.update_id if isinstance(event, Update) else None
            logger.exception("Unhandled update error", extra={"update_id": update_id})
            inner_event = _inner_event(event)
            if isinstance(inner_event, CallbackQuery):
                await inner_event.answer("خطای موقت رخ داد؛ دوباره تلاش کنید.", show_alert=True)
            elif isinstance(inner_event, Message):
                await inner_event.answer("خطای موقت رخ داد؛ لطفاً دوباره تلاش کنید.")
            return None


def _inner_event(event: TelegramObject) -> Message | CallbackQuery | None:
    if isinstance(event, (Message, CallbackQuery)):
        return event
    if isinstance(event, Update):
        return event.callback_query or event.message
    return None
