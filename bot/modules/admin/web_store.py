from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import dt, h, money
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.web_models import WebDeposit, WebOrder, WebUser, WebWallet, WebWalletTransaction
from bot.modules.admin.common import protected_router

router = protected_router("web_store")

ORDER_STATUS = {
    "pending": "🟡 در انتظار بررسی",
    "approved": "🔵 تأیید شده",
    "processing": "🟣 در حال انجام",
    "completed": "🟢 تکمیل شده",
    "cancelled": "🔴 لغو شده",
}
DEPOSIT_STATUS = {
    "pending": "🟡 در انتظار بررسی",
    "approved": "🟢 تأیید شده",
    "rejected": "🔴 رد شده",
}
ORDER_TRANSITIONS = {
    "pending": ("approved", "cancelled"),
    "approved": ("processing", "cancelled"),
    "processing": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}


class WebOrderNoteState(StatesGroup):
    text = State()


async def _locked_wallet(session: AsyncSession, user_id: int, now: datetime) -> WebWallet:
    wallet = await session.scalar(
        select(WebWallet).where(WebWallet.user_id == user_id).with_for_update()
    )
    if wallet is not None:
        return wallet

    # Defensive repair for accounts created before the wallet table/flow existed.
    wallet = WebWallet(user_id=user_id, balance=0, created_at=now, updated_at=now)
    session.add(wallet)
    await session.flush()
    return wallet


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "show")))
async def site_hub(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    pending_orders = int(
        await session.scalar(
            select(func.count())
            .select_from(WebOrder)
            .where(WebOrder.status.in_(["pending", "approved", "processing"]))
        )
        or 0
    )
    pending_deposits = int(
        await session.scalar(
            select(func.count()).select_from(WebDeposit).where(WebDeposit.status == "pending")
        )
        or 0
    )
    users = int(await session.scalar(select(func.count()).select_from(WebUser)) or 0)
    text = (
        "<b>🌐 بخش سایت Persian Shop</b>\n"
        "<i>مدیریت مستقل سفارش‌ها و حساب‌های وب</i>\n\n"
        f"📦 سفارش نیازمند پیگیری: <b>{pending_orders}</b>\n"
        f"💳 شارژ در انتظار تأیید: <b>{pending_deposits}</b>\n"
        f"👥 کاربران سایت: <b>{users}</b>\n\n"
        "سفارش‌های این بخش از سایت ثبت شده‌اند و از سفارش‌های تلگرام جدا نگهداری می‌شوند."
    )
    await edit_or_send(
        callback,
        text,
        reply_markup=keyboard(
            [
                button(
                    "📦 سفارش‌های سایت",
                    callback_data=AdminCallback(section="web", action="orders").pack(),
                    style="primary",
                )
            ],
            [
                button(
                    "💳 شارژهای سایت",
                    callback_data=AdminCallback(section="web", action="deposits").pack(),
                )
            ],
            [
                button(
                    "👥 کاربران سایت",
                    callback_data=AdminCallback(section="web", action="users").pack(),
                )
            ],
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ],
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "orders")))
async def web_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(WebOrder, WebUser.email)
        .join(WebUser, WebUser.id == WebOrder.user_id)
        .order_by(WebOrder.created_at.desc())
        .limit(30)
    )
    rows = []
    orders = result.all()
    for order, email in orders:
        icon = ORDER_STATUS.get(order.status, "⚪️").split()[0]
        rows.append(
            [
                button(
                    f"{icon} {order.number} • {money(order.total_amount)}",
                    callback_data=AdminCallback(
                        section="web", action="order", entity_id=int(order.id)
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            button(
                "↩️ بخش سایت",
                callback_data=AdminCallback(section="web", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>📦 سفارش‌های سایت</b>\n\n"
        + ("آخرین سفارش‌های ثبت‌شده:" if orders else "هنوز سفارش سایتی ثبت نشده است."),
        reply_markup=keyboard(*rows),
    )


async def show_order(
    event: Message | CallbackQuery, order_id: int, session: AsyncSession
) -> None:
    row = (
        await session.execute(
            select(WebOrder, WebUser.email, WebUser.phone)
            .join(WebUser, WebUser.id == WebOrder.user_id)
            .where(WebOrder.id == order_id)
        )
    ).first()
    if not row:
        await edit_or_send(event, "سفارش پیدا نشد.")
        return
    order, email, phone = row
    transitions = ORDER_TRANSITIONS.get(order.status, ())
    labels = {
        "approved": "✅ تأیید سفارش",
        "processing": "⚙️ شروع انجام",
        "completed": "🎉 تکمیل سفارش",
        "cancelled": "❌ لغو و بازپرداخت",
    }
    rows = []
    for status in transitions:
        rows.append(
            [
                button(
                    labels[status],
                    callback_data=AdminCallback(
                        section="web", action=f"os_{status}", entity_id=int(order.id)
                    ).pack(),
                    style="danger" if status == "cancelled" else "success",
                )
            ]
        )
    rows.extend(
        [
            [
                button(
                    "📝 یادداشت مدیریت",
                    callback_data=AdminCallback(
                        section="web", action="note", entity_id=int(order.id)
                    ).pack(),
                )
            ],
            [
                button(
                    "↩️ سفارش‌های سایت",
                    callback_data=AdminCallback(section="web", action="orders").pack(),
                )
            ],
        ]
    )
    note = (
        f"\n\n<b>یادداشت مدیریت</b>\n{h(order.admin_note)}"
        if order.admin_note
        else ""
    )
    refund = "\n♻️ مبلغ به کیف پول برگشت داده شده است." if order.refunded_at else ""
    await edit_or_send(
        event,
        f"<b>🌐 سفارش سایت {h(order.number)}</b>\n\n"
        f"وضعیت: {ORDER_STATUS.get(order.status, h(order.status))}\n"
        f"محصول: <b>{h(order.product_name)}</b>\n"
        f"تعداد: <b>{order.quantity:,}</b>\n"
        f"مبلغ: <b>{money(order.total_amount)}</b>\n"
        f"ایمیل: <code>{h(email)}</code>\n"
        f"موبایل: <code>{h(phone or 'ثبت نشده')}</code>\n"
        f"زمان ثبت: {dt(order.created_at)}\n\n"
        f"<b>اطلاعات سفارش</b>\n<code>{h(order.customer_input or '—')}</code>"
        f"{note}{refund}",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "order")))
async def web_order_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    await show_order(callback, callback_data.entity_id, session)


@router.callback_query(AdminCallback.filter((F.section == "web") & F.action.startswith("os_")))
async def web_order_status(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    new_status = callback_data.action.removeprefix("os_")
    now = datetime.now(timezone.utc)
    order = await session.scalar(
        select(WebOrder)
        .where(WebOrder.id == callback_data.entity_id)
        .with_for_update()
    )
    if not order:
        await callback.answer("سفارش پیدا نشد.", show_alert=True)
        return
    if new_status not in ORDER_TRANSITIONS.get(order.status, ()):
        await callback.answer("این تغییر وضعیت مجاز نیست.", show_alert=True)
        return

    if new_status == "cancelled" and order.refunded_at is None:
        wallet = await _locked_wallet(session, order.user_id, now)
        before = int(wallet.balance)
        after = before + int(order.total_amount)
        wallet.balance = after
        wallet.updated_at = now
        session.add(
            WebWalletTransaction(
                wallet_id=wallet.id,
                transaction_type="refund",
                amount=order.total_amount,
                balance_before=before,
                balance_after=after,
                description=f"بازپرداخت سفارش {order.number}",
                reference_type="web_order",
                reference_id=str(order.id),
                idempotency_key=f"web-order-refund:{order.id}",
                created_at=now,
            )
        )
        order.refunded_at = now
        order.cancelled_at = now
    elif new_status == "completed":
        order.completed_at = now

    order.status = new_status
    order.updated_at = now
    await session.commit()
    await callback.answer("وضعیت سفارش به‌روزرسانی شد.")
    await show_order(callback, int(order.id), session)


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "note")))
async def ask_web_order_note(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    order = await session.get(WebOrder, callback_data.entity_id)
    if not order:
        await callback.answer("سفارش پیدا نشد.", show_alert=True)
        return
    await state.set_state(WebOrderNoteState.text)
    await state.set_data({"web_order_id": int(order.id)})
    await edit_or_send(
        callback,
        f"<b>📝 یادداشت سفارش {h(order.number)}</b>\n\nمتن یادداشت مدیریت را ارسال کنید. این متن در حساب کاربر سایت نیز نمایش داده می‌شود.",
        reply_markup=keyboard(
            [
                button(
                    "لغو",
                    callback_data=AdminCallback(
                        section="web", action="order", entity_id=int(order.id)
                    ).pack(),
                    style="danger",
                )
            ]
        ),
    )


@router.message(WebOrderNoteState.text)
async def save_web_order_note(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    data = await state.get_data()
    order_id = int(data.get("web_order_id", 0))
    order = await session.get(WebOrder, order_id)
    if not order:
        await state.clear()
        await message.answer("سفارش پیدا نشد.")
        return
    order.admin_note = (message.text or "").strip()[:2000] or None
    order.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await state.clear()
    await show_order(message, order_id, session)


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "deposits")))
async def web_deposits(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(WebDeposit, WebUser.email)
        .join(WebUser, WebUser.id == WebDeposit.user_id)
        .order_by(WebDeposit.created_at.desc())
        .limit(30)
    )
    items = result.all()
    rows = []
    for deposit, email in items:
        icon = DEPOSIT_STATUS.get(deposit.status, "⚪️").split()[0]
        rows.append(
            [
                button(
                    f"{icon} {deposit.number} • {money(deposit.amount)}",
                    callback_data=AdminCallback(
                        section="web", action="deposit", entity_id=int(deposit.id)
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            button(
                "↩️ بخش سایت",
                callback_data=AdminCallback(section="web", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>💳 شارژهای سایت</b>\n\n"
        + ("آخرین درخواست‌ها:" if items else "هنوز درخواست شارژی ثبت نشده است."),
        reply_markup=keyboard(*rows),
    )


async def show_deposit(
    event: Message | CallbackQuery, deposit_id: int, session: AsyncSession
) -> None:
    row = (
        await session.execute(
            select(WebDeposit, WebUser.email)
            .join(WebUser, WebUser.id == WebDeposit.user_id)
            .where(WebDeposit.id == deposit_id)
        )
    ).first()
    if not row:
        await edit_or_send(event, "درخواست شارژ پیدا نشد.")
        return
    deposit, email = row
    rows = [
        [
            button(
                "🧾 مشاهده رسید",
                callback_data=AdminCallback(
                    section="web", action="proof", entity_id=int(deposit.id)
                ).pack(),
            )
        ]
    ]
    if deposit.status == "pending":
        rows.extend(
            [
                [
                    button(
                        "✅ تأیید و شارژ کیف پول",
                        callback_data=AdminCallback(
                            section="web", action="da", entity_id=int(deposit.id)
                        ).pack(),
                        style="success",
                    )
                ],
                [
                    button(
                        "❌ رد درخواست",
                        callback_data=AdminCallback(
                            section="web", action="dr", entity_id=int(deposit.id)
                        ).pack(),
                        style="danger",
                    )
                ],
            ]
        )
    rows.append(
        [
            button(
                "↩️ شارژهای سایت",
                callback_data=AdminCallback(section="web", action="deposits").pack(),
            )
        ]
    )
    tx_hash = (
        f"\nهش تراکنش: <code>{h(deposit.transaction_hash)}</code>"
        if deposit.transaction_hash
        else ""
    )
    await edit_or_send(
        event,
        f"<b>💳 شارژ سایت {h(deposit.number)}</b>\n\n"
        f"وضعیت: {DEPOSIT_STATUS.get(deposit.status, h(deposit.status))}\n"
        f"کاربر: <code>{h(email)}</code>\n"
        f"مبلغ: <b>{money(deposit.amount)}</b>\n"
        f"روش: <b>{'کارت‌به‌کارت' if deposit.method == 'card' else 'USDT'}</b>\n"
        f"زمان ثبت: {dt(deposit.created_at)}{tx_hash}",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "deposit")))
async def web_deposit_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    await show_deposit(callback, callback_data.entity_id, session)


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "proof")))
async def web_deposit_proof(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    deposit = await session.get(WebDeposit, callback_data.entity_id)
    if not deposit or not callback.message:
        await callback.answer("رسید پیدا نشد.", show_alert=True)
        return
    await callback.message.answer_document(
        BufferedInputFile(
            deposit.proof_bytes,
            filename=deposit.proof_name or f"{deposit.number}.jpg",
        ),
        caption=f"🧾 رسید {deposit.number} • {money(deposit.amount)}",
    )
    await callback.answer()


@router.callback_query(AdminCallback.filter((F.section == "web") & F.action.in_({"da", "dr"})))
async def review_web_deposit(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    deposit = await session.scalar(
        select(WebDeposit)
        .where(WebDeposit.id == callback_data.entity_id)
        .with_for_update()
    )
    if not deposit:
        await callback.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if deposit.status != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    if callback_data.action == "da":
        wallet = await _locked_wallet(session, deposit.user_id, now)
        before = int(wallet.balance)
        after = before + int(deposit.amount)
        wallet.balance = after
        wallet.updated_at = now
        session.add(
            WebWalletTransaction(
                wallet_id=wallet.id,
                transaction_type="deposit",
                amount=deposit.amount,
                balance_before=before,
                balance_after=after,
                description=f"تأیید شارژ {deposit.number}",
                reference_type="web_deposit",
                reference_id=str(deposit.id),
                idempotency_key=f"web-deposit:{deposit.id}",
                created_at=now,
            )
        )
        deposit.status = "approved"
    else:
        deposit.status = "rejected"

    deposit.reviewed_by_telegram_id = callback.from_user.id
    deposit.reviewed_at = now
    await session.commit()

    if callback_data.action == "da":
        await callback.answer("رسید تأیید شد و موجودی کیف پول افزایش یافت.", show_alert=True)
    else:
        await callback.answer("درخواست شارژ رد شد.", show_alert=True)
    await show_deposit(callback, int(deposit.id), session)


@router.callback_query(AdminCallback.filter((F.section == "web") & (F.action == "users")))
async def web_users(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(WebUser, WebWallet.balance)
        .outerjoin(WebWallet, WebWallet.user_id == WebUser.id)
        .order_by(WebUser.created_at.desc())
        .limit(30)
    )
    items = result.all()
    text_rows = [
        f"• <code>{h(user.email)}</code> — <b>{money(int(balance or 0))}</b>"
        + (f" — {h(user.phone)}" if user.phone else "")
        for user, balance in items
    ]
    await edit_or_send(
        callback,
        "<b>👥 کاربران سایت</b>\n\n"
        + ("\n".join(text_rows) if text_rows else "هنوز کاربری در سایت ثبت‌نام نکرده است."),
        reply_markup=keyboard(
            [
                button(
                    "↩️ بخش سایت",
                    callback_data=AdminCallback(section="web", action="show").pack(),
                )
            ]
        ),
    )
