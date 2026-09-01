from __future__ import annotations

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback, ChannelCallback
from bot.core.formatting import h
from bot.core.states import AdminChannelState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.channels import ChannelService
from bot.services.logs import ActivityLogService
from bot.services.settings import SettingsService

router = protected_router("settings")


@router.callback_query(AdminCallback.filter((F.section == "channels") & (F.action == "list")))
async def channels_list(callback: CallbackQuery, session: AsyncSession) -> None:
    service = ChannelService(session)
    enabled = await SettingsService(session).get_bool("forced_join_enabled")
    channels = await service.all()
    rows = [
        [
            button(
                f"{'🟢' if item.is_active else '⚫'} {item.title}",
                callback_data=ChannelCallback(action="detail", channel_id=item.id).pack(),
            )
        ]
        for item in channels
    ]
    rows.extend(
        [
            [
                button(
                    "⏸ غیرفعال‌کردن قفل" if enabled else "▶️ فعال‌کردن قفل",
                    callback_data=ChannelCallback(action="global_toggle").pack(),
                    style="danger" if enabled else "success",
                )
            ],
            [
                button(
                    "➕ افزودن کانال",
                    callback_data=ChannelCallback(action="add").pack(),
                    style="success",
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
        callback,
        "<b>📣 قفل عضویت کانال</b>\n\n"
        f"وضعیت کلی: <b>{'فعال' if enabled else 'غیرفعال'}</b>\n"
        f"تعداد کانال‌ها: <b>{len(channels)}</b>\n\n"
        "برای بررسی عضویت، ربات باید مدیر هر کانال باشد.",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(ChannelCallback.filter(F.action == "global_toggle"))
async def global_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    settings = SettingsService(session)
    enabled = await settings.get_bool("forced_join_enabled")
    await settings.set("forced_join_enabled", not enabled, value_type="bool")
    await channels_list(callback, session)


@router.callback_query(ChannelCallback.filter(F.action == "add"))
async def add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminChannelState.channel)
    await edit_or_send(
        callback,
        "<b>➕ افزودن کانال اجباری</b>\n\n"
        "ربات را در کانال مدیر کنید، سپس یکی از این قالب‌ها را بفرستید:\n"
        "<code>@channelname</code>\n"
        "<code>-1001234567890 | https://t.me/+InviteLink</code>",
    )


@router.message(AdminChannelState.channel, F.text)
async def add_channel(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    channel = await ChannelService(session).add(bot, message.text.strip())
    await ActivityLogService(session).record(
        "required_channel.added",
        actor_user_id=db_user.id,
        entity_type="required_channel",
        entity_id=channel.id,
    )
    await state.clear()
    await message.answer(
        f"✅ کانال <b>{h(channel.title)}</b> اضافه شد.",
        reply_markup=keyboard(
            [
                button(
                    "مدیریت کانال‌ها",
                    callback_data=AdminCallback(section="channels", action="list").pack(),
                )
            ]
        ),
    )


@router.callback_query(ChannelCallback.filter(F.action == "detail"))
async def channel_detail(
    callback: CallbackQuery, callback_data: ChannelCallback, session: AsyncSession
) -> None:
    channel = await ChannelService(session).get(callback_data.channel_id)
    await edit_or_send(
        callback,
        f"<b>📣 {h(channel.title)}</b>\n\n"
        f"شناسه: <code>{channel.chat_id}</code>\n"
        f"وضعیت: {'🟢 فعال' if channel.is_active else '⚫ غیرفعال'}\n"
        f"لینک عضویت: {h(channel.invite_link)}",
        reply_markup=keyboard(
            [
                button(
                    "غیرفعال" if channel.is_active else "فعال",
                    callback_data=ChannelCallback(action="toggle", channel_id=channel.id).pack(),
                )
            ],
            [
                button(
                    "🗑 حذف کانال",
                    callback_data=ChannelCallback(action="delete", channel_id=channel.id).pack(),
                    style="danger",
                )
            ],
            [
                button(
                    "↩️ کانال‌ها",
                    callback_data=AdminCallback(section="channels", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(ChannelCallback.filter(F.action.in_({"toggle", "delete"})))
async def channel_action(
    callback: CallbackQuery, callback_data: ChannelCallback, session: AsyncSession
) -> None:
    service = ChannelService(session)
    if callback_data.action == "delete":
        await service.delete(callback_data.channel_id)
        await channels_list(callback, session)
    else:
        await service.toggle(callback_data.channel_id)
        await channel_detail(callback, callback_data, session)
