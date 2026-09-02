from __future__ import annotations

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import h
from bot.core.language import translate_text
from bot.core.states import AdminMessageState
from bot.core.ui import button, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.tickets import TicketService
from bot.services.users import UserService

router = protected_router("messages")


@router.message(AdminMessageState.text, F.text)
async def send_admin_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    purpose = str(data["purpose"])
    target = int(data["target_telegram_id"])
    if purpose == "ticket_reply":
        ticket = await TicketService(session).reply(
            ticket_id=int(data["ticket_id"]),
            admin_user_id=db_user.id,
            text=message.text,
        )
        outgoing = f"<b>🎧 پاسخ پشتیبانی • {ticket.number}</b>\n\n{h(message.text)}"
        log_action = "ticket.replied"
        entity_type = "ticket"
        entity_id = ticket.id
    else:
        outgoing = f"<b>✉️ پیام مدیریت Persian Shop</b>\n\n{h(message.text)}"
        log_action = "user.messaged"
        entity_type = "user"
        entity_id = target
    delivered = True
    try:
        recipient = await UserService(session).get_by_telegram_id(target)
        await bot.send_message(target, translate_text(outgoing, recipient.language_code))
    except TelegramAPIError:
        delivered = False
    await ActivityLogService(session).record(
        log_action,
        actor_user_id=db_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return_section = str(data["return_section"])
    return_entity_id = int(data["return_entity_id"])
    await state.clear()
    await message.answer(
        "✅ پیام ارسال شد."
        if delivered
        else "⚠️ پیام ثبت شد، اما Telegram آن را به کاربر تحویل نداد.",
        reply_markup=keyboard(
            [
                button(
                    "بازگشت",
                    callback_data=AdminCallback(
                        section=return_section,
                        action="detail",
                        entity_id=return_entity_id,
                    ).pack(),
                )
            ]
        ),
    )
