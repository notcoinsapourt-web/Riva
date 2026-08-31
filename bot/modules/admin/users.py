from __future__ import annotations

import secrets

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.callbacks import AdminCallback
from bot.core.formatting import dt, h, money
from bot.core.states import AdminMessageState, AdminUserSearchState, AdminWalletState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import TransactionType, UserRole
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.users import UserService
from bot.services.wallet import WalletService

router = protected_router("users")


@router.callback_query(AdminCallback.filter((F.section == "users") & (F.action == "list")))
async def users_list(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    users = list(
        (
            await session.scalars(
                select(User)
                .options(selectinload(User.wallet))
                .order_by(User.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    await _render_users(
        callback,
        users,
        title="آخرین کاربران",
        show_admins=bool(db_user.admin and db_user.admin.role == UserRole.OWNER),
    )


async def _render_users(
    event: Message | CallbackQuery,
    users: list[User],
    *,
    title: str,
    show_admins: bool = False,
) -> None:
    rows = [
        [
            button(
                f"{'⛔' if item.is_blocked else '👤'} {item.first_name} • {item.telegram_id}",
                callback_data=AdminCallback(
                    section="users", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in users
    ]
    if show_admins:
        rows.append(
            [
                button(
                    "🛡 مدیران و دسترسی‌ها",
                    callback_data=AdminCallback(section="admins", action="list").pack(),
                )
            ]
        )
    rows.extend(
        [
            [
                button(
                    "🔎 جستجوی کاربر",
                    callback_data=AdminCallback(section="users", action="search").pack(),
                )
            ],
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        event,
        f"<b>👥 {h(title)}</b>\n\n"
        + ("کاربر موردنظر را انتخاب کنید." if users else "نتیجه‌ای پیدا نشد."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "users") & (F.action == "search")))
async def user_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserSearchState.query)
    await edit_or_send(
        callback,
        "<b>🔎 جستجوی کاربر</b>\n\nشناسه تلگرام، نام یا نام کاربری را ارسال کنید.",
    )


@router.message(AdminUserSearchState.query, F.text)
async def user_search_result(message: Message, session: AsyncSession, state: FSMContext) -> None:
    users = await UserService(session).search(message.text)
    await state.clear()
    await _render_users(message, users, title="نتیجه جستجو")


@router.callback_query(AdminCallback.filter((F.section == "users") & (F.action == "detail")))
async def user_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    user = await UserService(session).get_by_id(callback_data.entity_id)
    await edit_or_send(
        callback,
        f"<b>👤 {h(user.first_name)} {h(user.last_name or '')}</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{h(user.username or '—')}\n"
        f"موجودی: <b>{money(user.wallet.balance)}</b>\n"
        f"عضویت: {dt(user.created_at)}\n"
        f"آخرین فعالیت: {dt(user.last_seen_at)}\n"
        f"وضعیت: {'⛔ مسدود' if user.is_blocked else '🟢 فعال'}",
        reply_markup=keyboard(
            [
                button(
                    "➕ افزایش موجودی",
                    callback_data=AdminCallback(
                        section="users", action="credit", entity_id=user.id
                    ).pack(),
                    style="success",
                ),
                button(
                    "➖ کاهش موجودی",
                    callback_data=AdminCallback(
                        section="users", action="debit", entity_id=user.id
                    ).pack(),
                    style="danger",
                ),
            ],
            [
                button(
                    "✉️ ارسال پیام",
                    callback_data=AdminCallback(
                        section="users", action="message", entity_id=user.id
                    ).pack(),
                )
            ],
            [
                button(
                    "✅ رفع مسدودی" if user.is_blocked else "⛔ مسدود کردن",
                    callback_data=AdminCallback(
                        section="users", action="block", entity_id=user.id
                    ).pack(),
                    style="success" if user.is_blocked else "danger",
                )
            ],
            [
                button(
                    "↩️ کاربران",
                    callback_data=AdminCallback(section="users", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "users") & F.action.in_({"credit", "debit"}))
)
async def wallet_adjust_start(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    await state.set_state(AdminWalletState.amount)
    await state.set_data(
        {
            "target_user_id": callback_data.entity_id,
            "sign": 1 if callback_data.action == "credit" else -1,
        }
    )
    await edit_or_send(callback, "مبلغ را به تومان و فقط با عدد ارسال کنید.")


@router.message(AdminWalletState.amount, F.text)
async def wallet_adjust_amount(message: Message, state: FSMContext) -> None:
    raw = message.text.replace(",", "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("مبلغ نامعتبر است؛ عدد مثبت ارسال کنید.")
        return
    await state.update_data(amount=int(raw))
    await state.set_state(AdminWalletState.reason)
    await message.answer("دلیل این تغییر موجودی را بنویسید.")


@router.message(AdminWalletState.reason, F.text)
async def wallet_adjust_reason(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    sign = int(data["sign"])
    target_id = int(data["target_user_id"])
    amount = int(data["amount"]) * sign
    transaction = await WalletService(session).adjust(
        user_id=target_id,
        amount=amount,
        transaction_type=(
            TransactionType.ADMIN_CREDIT if sign > 0 else TransactionType.ADMIN_DEBIT
        ),
        description=message.text.strip(),
        idempotency_key=f"admin-adjust:{db_user.id}:{secrets.token_urlsafe(10)}",
        reference_type="admin",
        reference_id=str(db_user.id),
    )
    await ActivityLogService(session).record(
        "wallet.adjusted",
        actor_user_id=db_user.id,
        entity_type="user",
        entity_id=target_id,
        details={"amount": amount, "transaction_id": transaction.id},
    )
    await state.clear()
    await message.answer(
        f"✅ موجودی تغییر کرد. مانده جدید: <b>{money(transaction.balance_after)}</b>",
        reply_markup=keyboard(
            [
                button(
                    "مشاهده کاربر",
                    callback_data=AdminCallback(
                        section="users", action="detail", entity_id=target_id
                    ).pack(),
                )
            ]
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "users") & (F.action == "block")))
async def block_user(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    user = await UserService(session).get_by_id(callback_data.entity_id)
    user = await UserService(session).set_blocked(user.id, not user.is_blocked)
    await ActivityLogService(session).record(
        "user.block_toggled",
        actor_user_id=db_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"blocked": user.is_blocked},
    )
    await user_detail(
        callback,
        AdminCallback(section="users", action="detail", entity_id=user.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "users") & (F.action == "message")))
async def user_message_start(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user = await UserService(session).get_by_id(callback_data.entity_id)
    await state.set_state(AdminMessageState.text)
    await state.set_data(
        {
            "purpose": "direct_message",
            "target_telegram_id": user.telegram_id,
            "return_section": "users",
            "return_entity_id": user.id,
        }
    )
    await edit_or_send(callback, f"پیام برای <b>{h(user.first_name)}</b> را ارسال کنید.")
