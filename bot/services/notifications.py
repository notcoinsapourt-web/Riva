from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Admin, Order, User
from bot.services.order_reports import OrderReportService

logger = logging.getLogger(__name__)

_NEW_ORDER_RE = re.compile(
    r"<b>📦 سفارش جدید</b>.*?شماره:\s*<code>([^<]+)</code>",
    re.DOTALL,
)


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
        database_ids = list(result.all())
        configured_ids: list[int] = []
        for value in os.getenv("ADMIN_IDS", "").split(","):
            try:
                configured_ids.append(int(value.strip()))
            except ValueError:
                continue
        return list(dict.fromkeys([*database_ids, *configured_ids]))

    async def notify_admins(self, text: str) -> tuple[int, int]:
        result = await self.send_many(await self.admin_ids(), text)
        await self._maybe_publish_order_report(text)
        return result

    async def notify_admins_receipt(
        self,
        *,
        file_id: str,
        file_type: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        delay: float = 0.04,
    ) -> tuple[int, int]:
        """Send the actual receipt to every support admin, with a text fallback."""

        sent = failed = 0
        admin_ids = await self.admin_ids()
        if not admin_ids:
            logger.error("Receipt notification skipped because no support admins are configured")
            return sent, 1
        for telegram_id in admin_ids:
            try:
                if file_type == "document":
                    await self.bot.send_document(
                        telegram_id,
                        file_id,
                        caption=caption,
                        reply_markup=reply_markup,
                    )
                else:
                    await self.bot.send_photo(
                        telegram_id,
                        file_id,
                        caption=caption,
                        reply_markup=reply_markup,
                    )
                sent += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(min(exc.retry_after, 10))
                try:
                    await self.bot.send_message(
                        telegram_id,
                        caption,
                        reply_markup=reply_markup,
                    )
                    sent += 1
                except TelegramAPIError:
                    failed += 1
            except (TelegramForbiddenError, TelegramAPIError):
                try:
                    await self.bot.send_message(
                        telegram_id,
                        caption,
                        reply_markup=reply_markup,
                    )
                    sent += 1
                except TelegramAPIError:
                    failed += 1
                    logger.warning(
                        "Receipt notification delivery failed for telegram_id=%s",
                        telegram_id,
                    )
            if delay:
                await asyncio.sleep(delay)
        return sent, failed

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

    async def _maybe_publish_order_report(self, text: str) -> None:
        match = _NEW_ORDER_RE.search(text)
        if match is None:
            return
        order_number = match.group(1).strip()
        order_id = await self.session.scalar(
            select(Order.id).where(Order.number == order_number)
        )
        if order_id is None:
            logger.warning(
                "Order report trigger could not resolve order number=%s",
                order_number,
            )
            return
        await OrderReportService(self.session, self.bot).send_order(order_id)
