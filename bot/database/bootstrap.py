from __future__ import annotations

import secrets
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import AppSettings
from bot.database.base import Base
from bot.database.catalog_seed import DEFAULT_CATEGORIES, DEFAULT_PRODUCTS
from bot.database.enums import UserRole
from bot.database.models import Admin, Category, Module, Product, Setting, User, Wallet
from bot.database.product_content import PRODUCT_CONTENT_VERSION
from bot.database.session import Database

DEFAULT_SETTINGS: tuple[tuple[str, str, str, bool, str], ...] = (
    ("shop_name", "Persian Shop", "str", True, "نام فروشگاه"),
    ("currency", "تومان", "str", True, "واحد پول"),
    ("support_username", "", "str", True, "نام کاربری پشتیبانی"),
    (
        "welcome_text",
        "سلام {first_name} 👋\n"
        "به آروان‌کوین خوش اومدی.\n"
        "اینجا قراره اشتراک سرویس‌های محبوب، اکانت‌های پرمیوم و ابزارهای هوش "
        "مصنوعی رو سریع، مطمئن و بدون دردسر تهیه کنی.\n\n"
        "⚡️ تحویل فوری بعد از ثبت سفارش\n"
        "🛡 پشتیبانی و گارانتی\n"
        "💎 اکانت‌های تست‌شده و مطمئن\n"
        "🎵 اشتراک موزیک، فیلم، VPN و AI\n"
        "💰 قیمت اقتصادی و مناسب\n\n"
        "سرویس موردنظرت رو از منوی محصولات انتخاب کن و چند دقیقه بعد تحویل بگیر 🚀",
        "str",
        True,
        "پیام خوش‌آمد؛ متغیرهای {first_name}، {balance} و {currency} مجازند",
    ),
    ("referral_reward", "0", "int", True, "پاداش دعوت پس از اولین سفارش تکمیل‌شده"),
    ("payments_enabled", "false", "bool", False, "فعال‌سازی نمایشی پرداخت"),
    ("maintenance_mode", "false", "bool", True, "حالت تعمیرات"),
    ("wallet_card_enabled", "true", "bool", False, "فعال بودن شارژ کارت"),
    ("wallet_card_number", "6219861440311393", "str", False, "شماره کارت شارژ دستی"),
    ("wallet_card_holder", "میرزایی", "str", False, "نام صاحب کارت"),
    (
        "wallet_card_text",
        "❌ این تراکنش به مدت یک ساعت اعتبار دارد؛ پس از آن امکان پرداخت این "
        "تراکنش وجود ندارد.\n"
        "‼️ مبلغ باید همان مبلغی که در بالا ذکر شده واریز شود.\n"
        "‼️ امکان برداشت وجه از کیف پول وجود ندارد.\n"
        "‼️ مسئولیت واریز اشتباهی با شماست.\n\n"
        "بعد از پرداخت، دکمه «پرداخت کردم | ارسال رسید» را بزنید و سپس تصویر رسید "
        "را ارسال کنید.\n"
        "💵 بعد از تأیید پرداخت توسط ادمین، کیف پول شما شارژ خواهد شد و در صورتی "
        "که سفارشی داشته باشید انجام می‌شود.",
        "str",
        False,
        "راهنمای کارت",
    ),
    ("wallet_crypto_enabled", "true", "bool", False, "فعال بودن شارژ رمزارز"),
    ("wallet_crypto_network", "BEP20", "str", False, "شبکه رمزارز"),
    (
        "wallet_crypto_address",
        "0xd7ab9C72A65D036D8438fD208578AE1FAd07dF7e",
        "str",
        False,
        "آدرس کیف پول رمزارز",
    ),
    (
        "wallet_crypto_text",
        "فقط USDT را روی شبکه BEP20 ارسال کنید. انتخاب شبکه اشتباه باعث از دست رفتن "
        "دارایی می‌شود؛ هش تراکنش و تصویر رسید لازم است.",
        "str",
        False,
        "راهنمای رمزارز",
    ),
    ("forced_join_enabled", "false", "bool", False, "قفل عضویت کانال"),
)

DEFAULT_MODULES: tuple[tuple[str, str, bool, bool, int, str | None, str | None], ...] = (
    ("catalog", "فروشگاه", True, True, 10, "فروشگاه", "🛍"),
    ("orders", "سفارش‌ها", True, True, 20, "سفارش‌های من", "📦"),
    ("referral", "دعوت دوستان", True, False, 30, "دعوت دوستان", "🎁"),
    ("profile", "حساب کاربری", True, False, 40, "حساب کاربری", "👤"),
    ("rules", "راهنما و قوانین", True, False, 50, "راهنما و قوانین", "📄"),
    ("wallet", "کیف پول", True, False, 60, "کیف پول", "💰"),
    ("tickets", "پشتیبانی", True, False, 70, "پشتیبانی", "🎧"),
    ("notifications", "اعلان‌ها", True, False, 80, None, "🔔"),
    ("payments", "پرداخت آنلاین", False, False, 90, None, "💳"),
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
        await _seed_products(session)
        await _seed_admins(session, settings.admin_ids)


async def _seed_settings(session: AsyncSession, settings: AppSettings) -> None:
    existing_items = list((await session.scalars(select(Setting))).all())
    existing = {item.key for item in existing_items}
    existing_by_key = {item.key: item for item in existing_items}
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
    legacy_welcome = next((item for item in existing_items if item.key == "welcome_text"), None)
    if legacy_welcome and legacy_welcome.value == "به فروشگاه دیجیتال Persian Shop خوش آمدید.":
        legacy_welcome.value = next(
            item[1] for item in DEFAULT_SETTINGS if item[0] == "welcome_text"
        )

    # Apply the requested payment destinations once. The version marker keeps
    # later edits made by the owner in the admin panel intact across restarts.
    wallet_seed_version = "20260901-guided-v2"
    if "wallet_payment_seed_version" not in existing:
        payment_defaults = {
            key: value
            for key, value, _value_type, _public, _description in DEFAULT_SETTINGS
            if key.startswith("wallet_")
        }
        for key, value in payment_defaults.items():
            item = existing_by_key.get(key)
            if item is not None:
                item.value = value
        session.add(
            Setting(
                key="wallet_payment_seed_version",
                value=wallet_seed_version,
                value_type="str",
                is_public=False,
                description="نسخه اولیه روش‌های شارژ دستی",
            )
        )

    card_copy_version = "20260901-reference-card-v1"
    if "wallet_card_copy_version" not in existing:
        card_text = existing_by_key.get("wallet_card_text")
        if card_text is not None:
            card_text.value = next(
                value for key, value, *_rest in DEFAULT_SETTINGS if key == "wallet_card_text"
            )
        session.add(
            Setting(
                key="wallet_card_copy_version",
                value=card_copy_version,
                value_type="str",
                is_public=False,
                description="نسخه متن راهنمای کارت‌به‌کارت",
            )
        )

    card_reference_version = "20260902-reference-card-v2"
    if "wallet_card_reference_version" not in existing:
        payment_reference = {
            key: value
            for key, value, _value_type, _public, _description in DEFAULT_SETTINGS
            if key in {"wallet_card_number", "wallet_card_holder", "wallet_card_text"}
        }
        for key, value in payment_reference.items():
            item = existing_by_key.get(key)
            if item is not None:
                item.value = value
        session.add(
            Setting(
                key="wallet_card_reference_version",
                value=card_reference_version,
                value_type="str",
                is_public=False,
                description="نسخه اطلاعات کارت مطابق نمونه مرجع",
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
    existing = set((await session.scalars(select(Category.name))).all())
    session.add_all(
        Category(
            name=category.name,
            description=category.description,
            emoji=category.emoji,
            sort_order=category.sort_order,
        )
        for category in DEFAULT_CATEGORIES
        if category.name not in existing
    )
    await session.flush()


async def _seed_products(session: AsyncSession) -> None:
    categories = {
        category.name: category for category in (await session.scalars(select(Category))).all()
    }
    existing_products = list((await session.scalars(select(Product))).all())
    existing = {(item.category_id, item.name): item for item in existing_products}
    existing_by_slug = {
        item.photo_file_id.split("?", 1)[0].rsplit("/", 1)[-1].removesuffix(".jpg"): item
        for item in existing_products
        if item.photo_file_id and "/assets/products" in item.photo_file_id
    }
    existing_by_position = {(item.category_id, item.sort_order): item for item in existing_products}
    content_setting = await session.scalar(
        select(Setting).where(Setting.key == "catalog_content_version")
    )
    refresh_content = content_setting is None or content_setting.value != PRODUCT_CONTENT_VERSION
    for product in DEFAULT_PRODUCTS:
        category = categories.get(product.category)
        if category is None:
            continue
        current = (
            existing_by_slug.get(product.image_slug)
            or existing.get((category.id, product.name))
            or existing_by_position.get((category.id, product.sort_order))
        )
        if current is not None:
            if refresh_content:
                current.name = product.name
                current.description = product.description
                current.input_prompt = product.input_prompt
            if current.photo_file_id and "/assets/products" in current.photo_file_id:
                current.photo_file_id = product.photo_url
            continue
        session.add(
            Product(
                category_id=category.id,
                name=product.name,
                description=product.description,
                price=product.price,
                photo_file_id=product.photo_url,
                emoji=product.emoji,
                input_prompt=product.input_prompt,
                sort_order=product.sort_order,
            )
        )
    if content_setting is None:
        session.add(
            Setting(
                key="catalog_content_version",
                value=PRODUCT_CONTENT_VERSION,
                value_type="str",
                is_public=False,
                description="نسخه متن اختصاصی محصولات",
            )
        )
    elif refresh_content:
        content_setting.value = PRODUCT_CONTENT_VERSION


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
