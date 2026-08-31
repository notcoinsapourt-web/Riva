from __future__ import annotations

import secrets
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import AppSettings
from bot.database.base import Base
from bot.database.enums import UserRole
from bot.database.models import Admin, Category, Module, Setting, User, Wallet
from bot.database.session import Database

DEFAULT_SETTINGS: tuple[tuple[str, str, str, bool, str], ...] = (
    ("shop_name", "Persian Shop", "str", True, "نام فروشگاه"),
    ("currency", "تومان", "str", True, "واحد پول"),
    ("support_username", "", "str", True, "نام کاربری پشتیبانی"),
    ("welcome_text", "به فروشگاه دیجیتال Persian Shop خوش آمدید.", "str", True, "پیام خوش‌آمد"),
    ("referral_reward", "0", "int", True, "پاداش دعوت پس از اولین سفارش تکمیل‌شده"),
    ("payments_enabled", "false", "bool", False, "فعال‌سازی نمایشی پرداخت"),
    ("maintenance_mode", "false", "bool", True, "حالت تعمیرات"),
)

DEFAULT_MODULES: tuple[tuple[str, str, bool, bool, int, str | None, str | None], ...] = (
    ("catalog", "فروشگاه", True, True, 10, "فروشگاه", "🛍"),
    ("orders", "سفارش‌ها", True, True, 20, "سفارش‌های من", "📦"),
    ("wallet", "کیف پول", True, False, 30, "کیف پول", "💰"),
    ("referral", "دعوت دوستان", True, False, 40, "دعوت دوستان", "🎁"),
    ("tickets", "پشتیبانی", True, False, 50, "پشتیبانی", "🎧"),
    ("notifications", "اعلان‌ها", True, False, 60, None, "🔔"),
    ("payments", "پرداخت آنلاین", False, False, 70, None, "💳"),
)

DEFAULT_CATEGORIES: tuple[tuple[str, str, str, int], ...] = (
    ("خدمات تلگرام", "ممبر، ویو، ری‌اکشن، تبلیغات و خدمات کانال", "✈️", 10),
    ("خدمات اینستاگرام", "فالوور، لایک، ویو، کامنت و خدمات پیج", "📸", 20),
    ("اشتراک هوش مصنوعی", "ChatGPT، Claude، Gemini، Midjourney و سایر ابزارها", "🤖", 30),
    ("سایر محصولات دیجیتال", "محصولات و سرویس‌های دیجیتال", "💎", 40),
)


async def create_schema(database: Database) -> None:
    # Initial free edition uses create_all. Alembic is included for controlled upgrades.
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def seed_database(
    session_factory: async_sessionmaker[AsyncSession], settings: AppSettings
) -> None:
    async with session_factory() as session, session.begin():
        await _seed_settings(session, settings)
        await _seed_modules(session)
        await _seed_categories(session)
        await _seed_admins(session, settings.admin_ids)


async def _seed_settings(session: AsyncSession, settings: AppSettings) -> None:
    existing = set((await session.scalars(select(Setting.key))).all())
    overrides = {
        "shop_name": settings.shop_name,
        "support_username": settings.support_username,
        "payments_enabled": str(settings.payments_live).lower(),
    }
    for key, value, value_type, public, description in DEFAULT_SETTINGS:
        if key not in existing:
            session.add(
                Setting(
                    key=key,
                    value=overrides.get(key, value),
                    value_type=value_type,
                    is_public=public,
                    description=description,
                )
            )


async def _seed_modules(session: AsyncSession) -> None:
    existing = set((await session.scalars(select(Module.name))).all())
    for name, display, enabled, core, order, text, emoji in DEFAULT_MODULES:
        if name not in existing:
            session.add(
                Module(
                    name=name,
                    display_name=display,
                    is_enabled=enabled,
                    is_core=core,
                    sort_order=order,
                    menu_text=text,
                    emoji=emoji,
                )
            )


async def _seed_categories(session: AsyncSession) -> None:
    if (await session.scalar(select(Category.id).limit(1))) is not None:
        return
    session.add_all(
        Category(name=name, description=description, emoji=emoji, sort_order=order)
        for name, description, emoji, order in DEFAULT_CATEGORIES
    )


async def _seed_admins(session: AsyncSession, telegram_ids: Iterable[int]) -> None:
    for telegram_id in telegram_ids:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(
                telegram_id=telegram_id,
                first_name="مدیر",
                language_code="fa",
                referral_code=secrets.token_urlsafe(6)[:10].upper(),
            )
            user.wallet = Wallet(balance=0)
            session.add(user)
            await session.flush()
        admin = await session.scalar(select(Admin).where(Admin.user_id == user.id))
        if admin is None:
            session.add(Admin(user_id=user.id, role=UserRole.OWNER, permissions={"*": True}))
