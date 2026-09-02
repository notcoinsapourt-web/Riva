from __future__ import annotations

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import TICKET_STATUS_FA, dt, h
from bot.core.language import translate_text
from bot.core.states import AdminMessageState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import TicketSender, TicketStatus
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.tickets import TicketService
from bot.services.users import UserService

router = protected_router("tickets")


@router.callback_query(AdminCallback.filter((F.section == "tickets") & (F.action == "list")))
async def tickets_list(callback: CallbackQuery, session: AsyncSession) -> None:
    tickets = await TicketService(session).open_tickets()
    rows = [
        [
            button(
                f"{TICKET_STATUS_FA[item.status].split()[0]} {item.number} • {item.subject[:22]}",
                callback_data=AdminCallback(
                    section="tickets", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in tickets
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
        "<b>🎧 مدیریت تیکت‌ها</b>\n\n"
        + ("تیکت موردنظر را انتخاب کنید." if tickets else "تیکت بازی وجود ندارد."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "tickets") & (F.action == "detail")))
async def ticket_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    ticket = await TicketService(session).get(callback_data.entity_id)
    user = await UserService(session).get_by_id(ticket.user_id)
    messages = "\n\n".join(
        f"<b>{'مشتری' if item.sender_type == TicketSender.USER else 'پشتیبانی'}</b>"
        f" • {dt(item.created_at)}\n{h(item.text)}"
        for item in ticket.messages[-10:]
    )
    rows = []
    if ticket.status != TicketStatus.CLOSED:
        rows.extend(
            [
                [
                    button(
                        "↩️ پاسخ به تیکت",
                        callback_data=AdminCallback(
                            section="tickets", action="reply", entity_id=ticket.id
                        ).pack(),
                        style="success",
                    )
                ],
                [
                    button(
                        "🔒 بستن تیکت",
                        callback_data=AdminCallback(
                            section="tickets", action="close", entity_id=ticket.id
                        ).pack(),
                        style="danger",
                    )
                ],
            ]
        )
    rows.append(
        [
            button(
                "↩️ تیکت‌ها",
                callback_data=AdminCallback(section="tickets", action="list").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        f"<b>🎫 {ticket.number}</b>\n"
        f"موضوع: {h(ticket.subject)}\n"
        f"کاربر: {h(user.first_name)} • <code>{user.telegram_id}</code>\n"
        f"وضعیت: {TICKET_STATUS_FA[ticket.status]}\n\n{messages}",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "tickets") & (F.action == "reply")))
async def ticket_reply_start(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    ticket = await TicketService(session).get(callback_data.entity_id)
    user = await UserService(session).get_by_id(ticket.user_id)
    await state.set_state(AdminMessageState.text)
    await state.set_data(
        {
            "purpose": "ticket_reply",
            "ticket_id": ticket.id,
            "target_telegram_id": user.telegram_id,
            "return_section": "tickets",
            "return_entity_id": ticket.id,
        }
    )
    await edit_or_send(callback, f"پاسخ تیکت <code>{ticket.number}</code> را ارسال کنید.")


@router.callback_query(AdminCallback.filter((F.section == "tickets") & (F.action == "close")))
async def ticket_close(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
) -> None:
    ticket = await TicketService(session).close(callback_data.entity_id)
    user = await UserService(session).get_by_id(ticket.user_id)
    await ActivityLogService(session).record(
        "ticket.closed",
        actor_user_id=db_user.id,
        entity_type="ticket",
        entity_id=ticket.id,
    )
    try:
        await bot.send_message(
            user.telegram_id,
            translate_text(
                f"🔒 تیکت <code>{ticket.number}</code> توسط پشتیبانی بسته شد.",
                user.language_code,
            ),
        )
    except TelegramAPIError:
        pass
    await ticket_detail(
        callback,
        AdminCallback(section="tickets", action="detail", entity_id=ticket.id),
        session,
    )
