from __future__ import annotations

from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback, NavCallback
from bot.core.filters import HasAdminRole
from bot.core.formatting import money
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import UserRole
from bot.database.models import Admin, User
from bot.modules.admin.common import protected_router
from bot.services.admin import AdminDashboardService
from bot.services.logs import ActivityLogService
from bot.services.maintenance import MaintenanceModeService

router = protected_router("dashboard")


@router.message(Command("admin"))
async def admin_command(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await show_dashboard(message, session=session)


@router.callback_query(NavCallback.filter(F.action == "admin"))
@router.callback_query(AdminCallback.filter((F.section == "dashboard") & (F.action == "show")))
async def dashboard_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    await show_dashboard(callback, session=session)


async def show_dashboard(event: Message | CallbackQuery, *, session: AsyncSession) -> None:
    data = await AdminDashboardService(session).metrics()
    role = await session.scalar(
        select(Admin.role)
        .join(User, User.id == Admin.user_id)
        .where(User.telegram_id == event.from_user.id, Admin.is_active.is_(True))
    )
    maintenance_enabled = await MaintenanceModeService(session).is_enabled()
    if role in {UserRole.OWNER, UserRole.ADMIN}:
        user_access = "🔴 خاموش" if maintenance_enabled else "🟢 فعال"
        text = (
            "<b>👑 مدیریت Persian Shop</b>\n"
            "<i>مرکز کنترل فروشگاه دیجیتال</i>\n\n"
            f"🤖 دسترسی کاربران: <b>{user_access}</b>\n\n"
            f"📦 سفارش جدید: <b>{data['pending_orders']}</b>\n"
            f"🎧 تیکت باز: <b>{data['open_tickets']}</b>\n"
            f"💎 محصول فعال: <b>{data['active_products']}</b>\n"
            f"👥 کل کاربران: <b>{data['users']}</b> (+{data['new_users']} ماه اخیر)\n"
            f"💰 درآمد کل: <b>{money(data['revenue'])}</b>\n"
            f"📈 درآمد ۳۰ روز: <b>{money(data['monthly_revenue'])}</b>"
        )
    elif role == UserRole.OPERATOR:
        text = (
            f"<b>⚙️ پنل اپراتور</b>\n\n📦 سفارش‌های در انتظار بررسی: "
            f"<b>{data['pending_orders']}</b>"
        )
    else:
        text = f"<b>🎧 پنل پشتیبانی</b>\n\nتیکت‌های نیازمند رسیدگی: <b>{data['open_tickets']}</b>"
    rows = []
    if role in {UserRole.OWNER, UserRole.ADMIN}:
        rows.extend(
            [
                [
                    button(
                        "🟢 روشن کردن ربات برای کاربران"
                        if maintenance_enabled
                        else "🔴 خاموش کردن ربات برای کاربران",
                        callback_data=AdminCallback(
                            section="dashboard", action="maintenance_toggle"
                        ).pack(),
                        style="success" if maintenance_enabled else "danger",
                    )
                ],
                [
                    button(
                        "📦 سفارش‌ها",
                        callback_data=AdminCallback(section="orders", action="list").pack(),
                        style="primary",
                    ),
                    button(
                        "💎 محصولات",
                        callback_data=AdminCallback(section="products", action="list").pack(),
                    ),
                ],
                [
                    button(
                        "🗂 دسته‌بندی‌ها",
                        callback_data=AdminCallback(section="categories", action="list").pack(),
                    ),
                    button(
                        "👥 کاربران",
                        callback_data=AdminCallback(section="users", action="list").pack(),
                    ),
                ],
                [
                    button(
                        "💰 درآمد",
                        callback_data=AdminCallback(section="revenue", action="show").pack(),
                    ),
                    button(
                        "🎟 تخفیف‌ها",
                        callback_data=AdminCallback(section="coupons", action="list").pack(),
                    ),
                ],
                [
                    button(
                        "📢 پیام همگانی",
                        callback_data=AdminCallback(section="broadcast", action="start").pack(),
                    ),
                    button(
                        "🎧 تیکت‌ها",
                        callback_data=AdminCallback(section="tickets", action="list").pack(),
                    ),
                ],
                [
                    button(
                        "⚙️ تنظیمات",
                        callback_data=AdminCallback(section="settings", action="list").pack(),
                    ),
                    button(
                        "🧩 مدیریت ماژول‌ها",
                        callback_data=AdminCallback(section="modules", action="list").pack(),
                    ),
                ],
                [
                    button(
                        "💳 شارژهای دستی",
                        callback_data=AdminCallback(section="deposits", action="list").pack(),
                    ),
                    button(
                        "📣 قفل عضویت",
                        callback_data=AdminCallback(section="channels", action="list").pack(),
                    ),
                ],
            ]
        )
    elif role == UserRole.OPERATOR:
        rows.append(
            [
                button(
                    "📦 مدیریت سفارش‌ها",
                    callback_data=AdminCallback(section="orders", action="list").pack(),
                    style="primary",
                )
            ]
        )
    elif role == UserRole.SUPPORT:
        rows.append(
            [
                button(
                    "🎧 مدیریت تیکت‌ها",
                    callback_data=AdminCallback(section="tickets", action="list").pack(),
                    style="primary",
                )
            ]
        )
    rows.append([button("🏠 خروج از مدیریت", callback_data=NavCallback(action="home").pack())])
    markup = keyboard(*rows)
    await edit_or_send(event, text, reply_markup=markup)


@router.callback_query(
    AdminCallback.filter(
        (F.section == "dashboard") & (F.action == "maintenance_toggle")
    ),
    HasAdminRole(UserRole.OWNER, UserRole.ADMIN),
)
async def maintenance_toggle(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
) -> None:
    enabled = await MaintenanceModeService(session).toggle()
    await ActivityLogService(session).record(
        "maintenance.enabled" if enabled else "maintenance.disabled",
        actor_user_id=db_user.id,
        entity_type="setting",
        entity_id="maintenance_mode",
        details={"users_blocked": enabled},
    )
    await show_dashboard(callback, session=session)


@router.callback_query(
    AdminCallback.filter((F.section == "revenue") & (F.action == "show")),
    HasAdminRole(UserRole.OWNER, UserRole.ADMIN),
)
async def revenue(callback: CallbackQuery, session: AsyncSession) -> None:
    data = await AdminDashboardService(session).metrics()
    await edit_or_send(
        callback,
        "<b>💰 گزارش درآمد</b>\n\n"
        f"درآمد سفارش‌های تکمیل‌شده: <b>{money(data['revenue'])}</b>\n"
        f"درآمد ۳۰ روز اخیر: <b>{money(data['monthly_revenue'])}</b>\n\n"
        "تنها سفارش‌هایی که به وضعیت «تکمیل شده» رسیده‌اند در درآمد محاسبه می‌شوند.",
        reply_markup=keyboard(
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ]
        ),
    )
