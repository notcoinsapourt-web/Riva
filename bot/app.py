from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from bot.config import AppSettings, get_settings
from bot.core.emojis import PremiumEmojiFallbackMiddleware
from bot.core.middlewares import (
    BusinessErrorMiddleware,
    DatabaseSessionMiddleware,
    RateLimitMiddleware,
    UserContextMiddleware,
)
from bot.database.bootstrap import create_schema, seed_database
from bot.database.session import Database
from bot.logging_setup import configure_logging
from bot.modules.admin.router import router as admin_router
from bot.modules.catalog.router import router as catalog_router
from bot.modules.orders.router import router as orders_router
from bot.modules.referral.router import router as referral_router
from bot.modules.start.router import router as start_router
from bot.modules.tickets.router import router as tickets_router
from bot.modules.wallet.router import router as wallet_router
from bot.web.health import HealthServer

logger = logging.getLogger(__name__)


def build_dispatcher(database: Database, settings: AppSettings) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(BusinessErrorMiddleware())
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(database.session_factory))
    dispatcher.update.outer_middleware(RateLimitMiddleware(settings))
    dispatcher.update.outer_middleware(UserContextMiddleware())
    dispatcher.include_routers(
        start_router,
        admin_router,
        catalog_router,
        orders_router,
        wallet_router,
        referral_router,
        tickets_router,
    )
    return dispatcher


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    _prepare_sqlite_directory(settings.database_url)
    database = Database.create(settings.database_url)
    health = HealthServer(settings.port)
    if settings.health_server_enabled:
        await health.start()
    try:
        await create_schema(database)
        await seed_database(database.session_factory, settings)
        health.ready = True
        bot = Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
            ),
        )
        bot.session.middleware(PremiumEmojiFallbackMiddleware())
        dispatcher = build_dispatcher(database, settings)
        await _set_commands(bot)
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Persian Shop bot started")
        await dispatcher.start_polling(
            bot,
            settings=settings,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        health.ready = False
        if settings.health_server_enabled:
            await health.stop()
        await database.close()


async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="شروع و منوی اصلی"),
            BotCommand(command="menu", description="نمایش منوی فروشگاه"),
            BotCommand(command="admin", description="پنل مدیریت"),
            BotCommand(command="cancel", description="لغو عملیات جاری"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )


def _prepare_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url.removeprefix(prefix)
    if path == ":memory:":
        return
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
