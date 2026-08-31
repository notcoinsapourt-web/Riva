from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback, TicketCallback
from bot.core.formatting import TICKET_STATUS_FA, dt, h
from bot.core.states import TicketCreateState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import TicketSender
from bot.database.models import User
from bot.services.notifications import NotificationService
from bot.services.settings import SettingsService
from bot.services.tickets import TicketService

router = Router(name="tickets")


@router.callback_query(NavCallback.filter(F.action == "tickets"))
async def tickets_home(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    await state.clear()
    await SettingsService(session).require_module("tickets")
    tickets = await TicketService(session).user_tickets(db_user.id)
    rows = [
        [
            button(
                f"{TICKET_STATUS_FA[item.status].split()[0]} {item.number} • {item.subject[:22]}",
                callback_data=TicketCallback(action="detail", ticket_id=item.id).pack(),
            )
        ]
        for item in tickets
    ]
    rows.extend(
        [
            [
                button(
                    "➕ تیکت جدید",
                    callback_data=TicketCallback(action="new").pack(),
                    style="success",
                )
            ],
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
        ]
    )
    await edit_or_send(
        callback,
        "<b>🎧 پشتیبانی</b>\n\n"
        + ("تیکت موردنظر را انتخاب کنید." if tickets else "هنوز تیکتی ثبت نکرده‌اید."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(TicketCallback.filter(F.action == "new"))
async def new_ticket(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TicketCreateState.subject)
    await edit_or_send(
        callback,
        "<b>📝 تیکت جدید</b>\n\nموضوع کوتاه تیکت را ارسال کنید.",
        reply_markup=keyboard(
            [button("لغو", callback_data=NavCallback(action="tickets").pack(), style="danger")]
        ),
    )


@router.message(TicketCreateState.subject, F.text)
async def ticket_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(subject=message.text.strip())
    await state.set_state(TicketCreateState.message)
    await message.answer("حالا متن کامل درخواست یا مشکل را ارسال کنید.")


@router.message(TicketCreateState.message, F.text)
async def ticket_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    ticket = await TicketService(session).create(
        user_id=db_user.id, subject=str(data["subject"]), text=message.text
    )
    await state.clear()
    await message.answer(
        "<b>✅ تیکت ثبت شد</b>\n\n"
        f"شماره: <code>{ticket.number}</code>\n"
        "پاسخ پشتیبانی از طریق همین ربات ارسال می‌شود.",
        reply_markup=keyboard(
            [button("🎧 تیکت‌ها", callback_data=NavCallback(action="tickets").pack())]
        ),
    )
    await NotificationService(session, bot).notify_admins(
        "<b>🎧 تیکت جدید</b>\n\n"
        f"شماره: <code>{ticket.number}</code>\n"
        f"موضوع: {h(ticket.subject)}\n"
        f"کاربر: <code>{db_user.telegram_id}</code>"
    )


@router.callback_query(TicketCallback.filter(F.action == "detail"))
async def ticket_detail(
    callback: CallbackQuery,
    callback_data: TicketCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    ticket = await TicketService(session).get(callback_data.ticket_id)
    if ticket.user_id != db_user.id:
        await callback.answer("دسترسی غیرمجاز.", show_alert=True)
        return
    messages = "\n\n".join(
        (
            f"<b>{'شما' if item.sender_type == TicketSender.USER else 'پشتیبانی'}</b>"
            f" • {dt(item.created_at)}\n{h(item.text)}"
        )
        for item in ticket.messages[-8:]
    )
    await edit_or_send(
        callback,
        f"<b>🎫 {ticket.number}</b>\n"
        f"موضوع: {h(ticket.subject)}\n"
        f"وضعیت: {TICKET_STATUS_FA[ticket.status]}\n\n"
        f"{messages}",
        reply_markup=keyboard(
            [button("↩️ تیکت‌ها", callback_data=NavCallback(action="tickets").pack())]
        ),
    )
