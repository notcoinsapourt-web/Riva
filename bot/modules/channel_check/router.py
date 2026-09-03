from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.channels import ChannelService

router = Router(name="channel_check")


@router.callback_query(F.data == "check_channel_membership")
async def check_membership(callback: CallbackQuery, session: AsyncSession) -> None:
    user = callback.from_user
    missing = await ChannelService(session).missing_for(callback.bot, user.id)
    if missing:
        await callback.answer("هنوز در همه کانال‌ها عضو نشده‌اید.", show_alert=True)
        return

    await callback.answer("عضویت تایید شد.")
    await callback.message.delete()
    await callback.bot.send_message(user.id, "✅ عضویت شما تایید شد. اکنون می‌توانید از ربات استفاده کنید.")
