from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import AppSettings
from bot.services.report_test_campaign import bind_private_test_channel

logger = logging.getLogger(__name__)
router = Router(name="report-test-binding")


@router.my_chat_member()
async def bind_when_bot_becomes_channel_admin(
    update: ChatMemberUpdated,
    session: AsyncSession,
    settings: AppSettings,
) -> None:
    """Auto-bind the next private channel where an authorized admin promotes the bot."""

    if not settings.report_test_campaign_enabled:
        return
    if update.chat.type != ChatType.CHANNEL or update.chat.username:
        return
    if update.new_chat_member.status not in {
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }:
        return

    try:
        await bind_private_test_channel(
            session,
            update.bot,
            settings,
            update.chat.id,
            actor_user_id=update.from_user.id,
            force=False,
        )
    except Exception:
        logger.exception(
            "Failed to auto-bind private report test channel chat_id=%s",
            update.chat.id,
        )


@router.channel_post(Command("bindreporttest"))
async def bind_from_private_channel_command(
    message: Message,
    session: AsyncSession,
    settings: AppSettings,
) -> None:
    """Fallback binding path when the bot was already an admin before deployment.

    The bind command is deleted after success so the private test channel stays
    visually identical to the final report channel.
    """

    if not settings.report_test_campaign_enabled:
        return
    if message.chat.type != ChatType.CHANNEL or message.chat.username:
        return

    try:
        bound = await bind_private_test_channel(
            session,
            message.bot,
            settings,
            message.chat.id,
            actor_user_id=None,
            force=True,
        )
        if not bound:
            return

        try:
            await message.delete()
        except TelegramAPIError:
            logger.warning(
                "Private report test channel bound but bind command could not be deleted chat_id=%s",
                message.chat.id,
            )

        logger.info(
            "Private report test channel bound through /bindreporttest chat_id=%s",
            message.chat.id,
        )
    except Exception:
        logger.exception(
            "Failed to bind private report test channel from command chat_id=%s",
            message.chat.id,
        )
