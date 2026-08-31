from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Admin, User

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self.session = session
        self.bot = bot

    async def admin_ids(self) -> list[int]:
        result = await self.session.scalars(
            select(User.telegram_id)
            .join(Admin, Admin.user_id == User.id)
            .where(Admin.is_active.is_(True), User.is_blocked.is_(False))
        )
        return list(result.all())

    async def notify_admins(self, text: str) -> tuple[int, int]:
        return await self.send_many(await self.admin_ids(), text)

    async def send_many(
        self, telegram_ids: Iterable[int], text: str, *, delay: float = 0.04
    ) -> tuple[int, int]:
        sent = failed = 0
        for telegram_id in telegram_ids:
            try:
                await self.bot.send_message(telegram_id, text)
                sent += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(min(exc.retry_after, 10))
                try:
                    await self.bot.send_message(telegram_id, text)
                    sent += 1
                except TelegramAPIError:
                    failed += 1
            except (TelegramForbiddenError, TelegramAPIError):
                failed += 1
                logger.info("Notification delivery failed for telegram_id=%s", telegram_id)
            if delay:
                await asyncio.sleep(delay)
        return sent, failed
