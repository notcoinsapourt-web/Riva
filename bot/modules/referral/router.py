from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.formatting import money
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import Referral, User
from bot.services.settings import SettingsService

router = Router(name="referral")


@router.callback_query(NavCallback.filter(F.action == "referral"))
async def referral_home(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
) -> None:
    settings = SettingsService(session)
    await settings.require_module("referral")
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{db_user.referral_code}"
    invited = (
        await session.scalar(
            select(func.count(Referral.id)).where(Referral.referrer_id == db_user.id)
        )
        or 0
    )
    rewarded = (
        await session.scalar(
            select(func.coalesce(func.sum(Referral.reward_amount), 0)).where(
                Referral.referrer_id == db_user.id
            )
        )
        or 0
    )
    reward = await settings.get_int("referral_reward", 0)
    intro = await settings.module_content("referral", "<b>🎁 دعوت دوستان</b>")
    await edit_or_send(
        callback,
        intro + "\n\n"
        "لینک اختصاصی شما:\n"
        f"<code>{link}</code>\n\n"
        f"👥 تعداد دعوت‌ها: <b>{invited}</b>\n"
        f"💎 پاداش دریافت‌شده: <b>{money(rewarded)}</b>\n"
        f"🎯 پاداش هر دعوت موفق: <b>{money(reward)}</b>\n\n"
        "پاداش پس از تکمیل اولین سفارش دوست شما ثبت می‌شود.",
        reply_markup=keyboard(
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())]
        ),
    )
