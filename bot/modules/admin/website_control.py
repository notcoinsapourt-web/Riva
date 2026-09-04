from __future__ import annotations

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.filters import HasAdminRole
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import UserRole
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.settings import SettingsService

router = protected_router("website_control")

WEBSITE_MAINTENANCE_KEY = "website_maintenance"


async def _enabled(session: AsyncSession) -> bool:
    return await SettingsService(session).get_bool(WEBSITE_MAINTENANCE_KEY, False)


async def show_site_control(event: Message | CallbackQuery, session: AsyncSession) -> None:
    enabled = await _enabled(session)
    status = "🔴 آفلاین / در حال بروزرسانی" if enabled else "🟢 آنلاین"
    toggle_text = "🟢 آنلاین کردن سایت" if enabled else "🔴 آفلاین کردن سایت"
    toggle_style = "success" if enabled else "danger"
    await edit_or_send(
        event,
        "<b>🌐 کنترل سایت Persian Shop</b>\n\n"
        f"وضعیت سایت: <b>{status}</b>\n\n"
        "در حالت آفلاین، ربات فعال می‌ماند و کاربران سایت صفحه اختصاصی «در حال تعمیر و بروزرسانی» را می‌بینند. "
        "حساب‌ها، سفارش‌ها و موجودی‌ها حذف یا ریست نمی‌شوند.",
        reply_markup=keyboard(
            [button(toggle_text, callback_data=AdminCallback(section="website", action="toggle").pack(), style=toggle_style)],
            [button("📦 مدیریت سفارش‌های سایت", callback_data=AdminCallback(section="web", action="show").pack(), style="primary")],
            [button("↩️ پنل مدیریت", callback_data=AdminCallback(section="dashboard", action="show").pack())],
        ),
    )


async def set_site_state(session: AsyncSession, db_user: User, *, enabled: bool) -> None:
    await SettingsService(session).set(
        WEBSITE_MAINTENANCE_KEY,
        enabled,
        value_type="bool",
        description="When enabled, the public website shows the branded maintenance page while the bot stays online.",
    )
    await ActivityLogService(session).record(
        "website.maintenance_enabled" if enabled else "website.maintenance_disabled",
        actor_user_id=db_user.id,
        entity_type="setting",
        entity_id=WEBSITE_MAINTENANCE_KEY,
        details={"website_offline": enabled, "bot_affected": False},
    )


@router.message(Command("site"), HasAdminRole(UserRole.OWNER, UserRole.ADMIN))
async def site_command(message: Message, session: AsyncSession) -> None:
    await show_site_control(message, session)


@router.message(Command("site_offline"), HasAdminRole(UserRole.OWNER, UserRole.ADMIN))
async def site_offline(message: Message, session: AsyncSession, db_user: User) -> None:
    await set_site_state(session, db_user, enabled=True)
    await show_site_control(message, session)


@router.message(Command("site_online"), HasAdminRole(UserRole.OWNER, UserRole.ADMIN))
async def site_online(message: Message, session: AsyncSession, db_user: User) -> None:
    await set_site_state(session, db_user, enabled=False)
    await show_site_control(message, session)


@router.callback_query(
    AdminCallback.filter((F.section == "website") & (F.action == "show")),
    HasAdminRole(UserRole.OWNER, UserRole.ADMIN),
)
async def site_show(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await show_site_control(callback, session)


@router.callback_query(
    AdminCallback.filter((F.section == "website") & (F.action == "toggle")),
    HasAdminRole(UserRole.OWNER, UserRole.ADMIN),
)
async def site_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    enabled = not await _enabled(session)
    await set_site_state(session, db_user, enabled=enabled)
    await callback.answer("سایت آفلاین شد." if enabled else "سایت آنلاین شد.")
    await show_site_control(callback, session)
