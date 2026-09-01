from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.models import RequiredChannel
from bot.services.settings import SettingsService


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all(self) -> list[RequiredChannel]:
        return list(
            (
                await self.session.scalars(
                    select(RequiredChannel).order_by(RequiredChannel.sort_order, RequiredChannel.id)
                )
            ).all()
        )

    async def active(self) -> list[RequiredChannel]:
        if not await SettingsService(self.session).get_bool("forced_join_enabled"):
            return []
        return list(
            (
                await self.session.scalars(
                    select(RequiredChannel)
                    .where(RequiredChannel.is_active.is_(True))
                    .order_by(RequiredChannel.sort_order, RequiredChannel.id)
                )
            ).all()
        )

    async def add(self, bot: Bot, raw: str) -> RequiredChannel:
        parts = [part.strip() for part in raw.split("|", maxsplit=1)]
        reference = parts[0]
        if reference.lstrip("-").isdigit():
            chat_ref: int | str = int(reference)
        else:
            chat_ref = "@" + reference.lstrip("@").removeprefix("https://t.me/")
        try:
            chat = await bot.get_chat(chat_ref)
        except TelegramAPIError as exc:
            raise ValidationError(
                "کانال پیدا نشد. ربات را مدیر کانال کنید و @username یا شناسه عددی را بفرستید."
            ) from exc
        username = getattr(chat, "username", None)
        invite_link = parts[1] if len(parts) > 1 else ""
        if not invite_link and username:
            invite_link = f"https://t.me/{username}"
        if not invite_link:
            raise ValidationError(
                "برای کانال خصوصی، شناسه و لینک دعوت را با | بفرستید؛ نمونه: -100123 | https://t.me/+..."
            )
        existing = await self.session.scalar(
            select(RequiredChannel).where(RequiredChannel.chat_id == chat.id)
        )
        if existing:
            existing.title = chat.title or str(chat.id)
            existing.username = username
            existing.invite_link = invite_link[:300]
            existing.is_active = True
            channel = existing
        else:
            channel = RequiredChannel(
                chat_id=chat.id,
                title=chat.title or str(chat.id),
                username=username,
                invite_link=invite_link[:300],
            )
            self.session.add(channel)
        await self.session.commit()
        return channel

    async def get(self, channel_id: int) -> RequiredChannel:
        channel = await self.session.get(RequiredChannel, channel_id)
        if channel is None:
            raise NotFoundError("کانال پیدا نشد.")
        return channel

    async def toggle(self, channel_id: int) -> RequiredChannel:
        channel = await self.get(channel_id)
        channel.is_active = not channel.is_active
        await self.session.commit()
        return channel

    async def delete(self, channel_id: int) -> None:
        channel = await self.get(channel_id)
        await self.session.delete(channel)
        await self.session.commit()

    async def missing_for(self, bot: Bot, telegram_id: int) -> list[RequiredChannel]:
        missing = []
        for channel in await self.active():
            try:
                member = await bot.get_chat_member(channel.chat_id, telegram_id)
                joined = member.status in {
                    ChatMemberStatus.CREATOR,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.MEMBER,
                } or (member.status == ChatMemberStatus.RESTRICTED and member.is_member)
            except TelegramAPIError:
                joined = False
            if not joined:
                missing.append(channel)
        return missing
