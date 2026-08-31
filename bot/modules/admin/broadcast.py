from __future__ import annotations

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.states import AdminBroadcastState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.notifications import NotificationService
from bot.services.users import UserService

router = protected_router("broadcast")


@router.callback_query(AdminCallback.filter((F.section == "broadcast") & (F.action == "start")))
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastState.content)
    await edit_or_send(
        callback,
        "<b>📢 پیام همگانی</b>\n\nمتن پیام را ارسال کنید. قالب‌بندی HTML پشتیبانی می‌شود.",
        reply_markup=keyboard(
            [
                button(
                    "لغو",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                    style="danger",
                )
            ]
        ),
    )


@router.message(AdminBroadcastState.content, F.text)
async def broadcast_content(message: Message, state: FSMContext) -> None:
    if len(message.text) > 3900:
        await message.answer("پیام طولانی است؛ آن را کوتاه‌تر از ۳۹۰۰ نویسه کنید.")
        return
    await state.update_data(content=message.text)
    await state.set_state(AdminBroadcastState.confirm)
    await message.answer(
        "<b>پیش‌نمایش پیام</b>\n\n" + message.text + "\n\nآیا برای همه ارسال شود؟",
        reply_markup=keyboard(
            [
                button(
                    "ارسال برای همه",
                    callback_data=AdminCallback(section="broadcast", action="confirm").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "لغو",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                    style="danger",
                )
            ],
        ),
    )


@router.callback_query(
    AdminBroadcastState.confirm,
    AdminCallback.filter((F.section == "broadcast") & (F.action == "confirm")),
)
async def broadcast_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    content = str(data["content"])
    ids = await UserService(session).active_telegram_ids()
    await callback.answer("ارسال آغاز شد.")
    sent, failed = await NotificationService(session, bot).send_many(ids, content)
    await ActivityLogService(session).record(
        "broadcast.sent",
        actor_user_id=db_user.id,
        entity_type="broadcast",
        details={"sent": sent, "failed": failed},
    )
    await state.clear()
    if callback.message:
        await callback.message.answer(
            f"<b>✅ ارسال تمام شد</b>\n\nموفق: {sent}\nناموفق: {failed}",
            reply_markup=keyboard(
                [
                    button(
                        "↩️ پنل مدیریت",
                        callback_data=AdminCallback(section="dashboard", action="show").pack(),
                    )
                ]
            ),
        )
