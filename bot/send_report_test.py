from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.database.session import Database
from bot.services.order_reports import OrderReportService


async def run() -> None:
    settings = get_settings()
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
            delivery = await OrderReportService(session, bot, settings).send_test()
            print(
                "ORDER_REPORT_TEST_SENT "
                f"chat_id={delivery.chat_id} "
                f"message_id={delivery.message_id} "
                f"premium_emoji_used={delivery.premium_emoji_used}"
            )
    finally:
        await bot.session.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(run())
