from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import h
from bot.core.states import AdminAccessState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import UserRole
from bot.database.models import User
from bot.modules.admin.common import owner_router
from bot.services.admin import AdminAccessService
from bot.services.logs import ActivityLogService
from bot.services.users import UserService

router = owner_router("access")

ROLE_LABELS = {
    UserRole.OWNER: "مالک",
    UserRole.ADMIN: "مدیر",
    UserRole.OPERATOR: "اپراتور سفارش",
    UserRole.SUPPORT: "پشتیبان",
}


@router.callback_query(AdminCallback.filter((F.section == "admins") & (F.action == "list")))
async def admins_list(callback: CallbackQuery, session: AsyncSession) -> None:
    admins = await AdminAccessService(session).list()
    rows = [
        [
            button(
                f"{'🟢' if item.is_active else '⚫'} {item.user.first_name}"
                f" • {ROLE_LABELS.get(item.role, item.role.value)}",
                callback_data=AdminCallback(
                    section="admins", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in admins
    ]
    rows.extend(
        [
            [
                button(
                    "➕ افزودن مدیر",
                    callback_data=AdminCallback(section="admins", action="add").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "↩️ کاربران",
                    callback_data=AdminCallback(section="users", action="list").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        callback,
        "<b>🛡 مدیران و سطح دسترسی</b>\n\n"
        "مالک به همه بخش‌ها دسترسی دارد. نقش‌های دیگر برای توسعه سطح دسترسی دقیق در مدل داده "
        "ذخیره می‌شوند.",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "admins") & (F.action == "detail")))
async def admin_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    admin = await AdminAccessService(session).get(callback_data.entity_id)
    rows = [
        [
            button(
                label,
                callback_data=AdminCallback(
                    section="admins", action=f"role_{role.value}", entity_id=admin.id
                ).pack(),
                style="primary" if admin.role == role else None,
            )
            for role, label in ROLE_LABELS.items()
        ],
        [
            button(
                "⛔ غیرفعال‌سازی",
                callback_data=AdminCallback(
                    section="admins", action="deactivate", entity_id=admin.id
                ).pack(),
                style="danger",
            )
        ],
        [
            button(
                "↩️ مدیران",
                callback_data=AdminCallback(section="admins", action="list").pack(),
            )
        ],
    ]
    await edit_or_send(
        callback,
        f"<b>🛡 {h(admin.user.first_name)} {h(admin.user.last_name or '')}</b>\n\n"
        f"Telegram ID: <code>{admin.user.telegram_id}</code>\n"
        f"نقش: <b>{ROLE_LABELS.get(admin.role, admin.role.value)}</b>\n"
        f"وضعیت: {'🟢 فعال' if admin.is_active else '⚫ غیرفعال'}",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "admins") & (F.action == "add")))
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminAccessState.telegram_id)
    await edit_or_send(
        callback,
        "<b>➕ افزودن مدیر</b>\n\n"
        "Telegram ID کاربری را ارسال کنید. کاربر باید قبلاً ربات را Start کرده باشد.",
    )


@router.message(AdminAccessState.telegram_id, F.text)
async def admin_add_id(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("شناسه باید فقط عدد باشد.")
        return
    target = await UserService(session).get_by_telegram_id(int(raw))
    await state.update_data(target_telegram_id=target.telegram_id)
    await message.answer(
        f"نقش <b>{h(target.first_name)}</b> را انتخاب کنید.",
        reply_markup=_role_keyboard(prefix="addrole"),
    )


@router.callback_query(
    AdminAccessState.telegram_id,
    AdminCallback.filter((F.section == "admins") & F.action.startswith("addrole_")),
)
async def admin_add_role(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    role = UserRole(callback_data.action.removeprefix("addrole_"))
    admin = await AdminAccessService(session).add(int(data["target_telegram_id"]), role)
    await ActivityLogService(session).record(
        "admin.added",
        actor_user_id=db_user.id,
        entity_type="admin",
        entity_id=admin.id,
        details={"role": role.value},
    )
    await state.clear()
    await admin_detail(
        callback,
        AdminCallback(section="admins", action="detail", entity_id=admin.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "admins") & F.action.startswith("role_")))
async def admin_set_role(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    role = UserRole(callback_data.action.removeprefix("role_"))
    admin = await AdminAccessService(session).set_role(callback_data.entity_id, role)
    await ActivityLogService(session).record(
        "admin.role_changed",
        actor_user_id=db_user.id,
        entity_type="admin",
        entity_id=admin.id,
        details={"role": role.value},
    )
    await admin_detail(callback, callback_data, session)


@router.callback_query(AdminCallback.filter((F.section == "admins") & (F.action == "deactivate")))
async def admin_deactivate(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    admin = await AdminAccessService(session).deactivate(callback_data.entity_id)
    await ActivityLogService(session).record(
        "admin.deactivated",
        actor_user_id=db_user.id,
        entity_type="admin",
        entity_id=admin.id,
    )
    await admins_list(callback, session)


def _role_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return keyboard(
        *[
            [
                button(
                    label,
                    callback_data=AdminCallback(
                        section="admins", action=f"{prefix}_{role.value}"
                    ).pack(),
                )
            ]
            for role, label in ROLE_LABELS.items()
        ]
    )
