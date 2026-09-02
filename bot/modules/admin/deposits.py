from __future__ import annotations

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback, DepositCallback
from bot.core.formatting import dt, h, money
from bot.core.language import translate_text
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import DepositMethod, DepositStatus
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.deposits import DepositService

router = protected_router("settings")

STATUS_TEXT = {
    DepositStatus.PENDING: "🟡 در انتظار",
    DepositStatus.APPROVED: "🟢 تأییدشده",
    DepositStatus.REJECTED: "🔴 ردشده",
}


@router.callback_query(AdminCallback.filter((F.section == "deposits") & (F.action == "list")))
async def deposits_list(callback: CallbackQuery, session: AsyncSession) -> None:
    items = await DepositService(session).pending()
    rows = [
        [
            button(
                f"{item.number} • {money(item.amount)}",
                callback_data=DepositCallback(action="detail", request_id=item.id).pack(),
            )
        ]
        for item in items
    ]
    rows.append(
        [
            button(
                "↩️ پنل مدیریت",
                callback_data=AdminCallback(section="dashboard", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>💳 درخواست‌های شارژ دستی</b>\n\n"
        + (f"{len(items)} درخواست در انتظار بررسی است." if items else "درخواستی در انتظار نیست."),
        reply_markup=keyboard(*rows),
    )


async def _send_detail(event: CallbackQuery, request, bot: Bot) -> None:
    method = "کارت بانکی" if request.method == DepositMethod.CARD else "ارز دیجیتال"
    text = (
        f"<b>💳 شارژ {request.number}</b>\n\n"
        f"وضعیت: {STATUS_TEXT[request.status]}\n"
        f"روش: <b>{method}</b>\n"
        f"مبلغ: <b>{money(request.amount)}</b>\n"
        f"کاربر: {h(request.user.first_name)} • <code>{request.user.telegram_id}</code>\n"
        f"زمان: {dt(request.created_at)}"
    )
    if request.transaction_hash:
        text += f"\nهش تراکنش: <code>{h(request.transaction_hash)}</code>"
    markup = keyboard(
        [
            button(
                "✅ تأیید و افزایش موجودی",
                callback_data=DepositCallback(action="approve", request_id=request.id).pack(),
                style="success",
            )
        ],
        [
            button(
                "❌ رد درخواست",
                callback_data=DepositCallback(action="reject", request_id=request.id).pack(),
                style="danger",
            )
        ],
        [
            button(
                "↩️ درخواست‌ها", callback_data=AdminCallback(section="deposits", action="list").pack()
            )
        ],
    )
    await event.answer()
    message = event.message
    if not isinstance(message, Message):
        return
    if request.proof_file_type == "document":
        await bot.send_document(
            message.chat.id, request.proof_file_id, caption=text, reply_markup=markup
        )
    else:
        await bot.send_photo(
            message.chat.id, request.proof_file_id, caption=text, reply_markup=markup
        )


@router.callback_query(DepositCallback.filter(F.action == "detail"))
async def deposit_detail(
    callback: CallbackQuery, callback_data: DepositCallback, session: AsyncSession, bot: Bot
) -> None:
    await _send_detail(callback, await DepositService(session).get(callback_data.request_id), bot)


@router.callback_query(DepositCallback.filter(F.action.in_({"approve", "reject"})))
async def review_deposit(
    callback: CallbackQuery,
    callback_data: DepositCallback,
    session: AsyncSession,
    db_user: User,
    bot: Bot,
) -> None:
    service = DepositService(session)
    if callback_data.action == "approve":
        request = await service.approve(callback_data.request_id, db_user.id)
        user_text = (
            f"✅ درخواست شارژ <code>{request.number}</code> تأیید شد و "
            f"<b>{money(request.amount)}</b> به کیف پول شما اضافه شد."
        )
    else:
        request = await service.reject(callback_data.request_id, db_user.id)
        user_text = f"❌ درخواست شارژ <code>{request.number}</code> تأیید نشد."
    try:
        await bot.send_message(
            request.user.telegram_id,
            translate_text(user_text, request.user.language_code),
        )
    except TelegramAPIError:
        pass
    await callback.answer("نتیجه ثبت شد.", show_alert=True)
    await deposits_list(callback, session)
