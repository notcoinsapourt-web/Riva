from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.database.session import Database
from bot.logging_setup import configure_logging
from bot.services.order_reports import OrderReportService


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.order_report_target is None:
        raise RuntimeError("ORDER_REPORT_CHANNEL_ID is not configured.")

    database = Database.create(settings.database_url)
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    try:
        async with database.session_factory() as session:
            result = await OrderReportService(session, bot, settings).send_test()
        logging.getLogger(__name__).info(
            "ORDER_REPORT_TEST_SUCCESS chat_id=%s message_id=%s premium_emoji_used=%s",
            result.chat_id,
            result.message_id,
            result.premium_emoji_used,
        )
    finally:
        await bot.session.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(run())
