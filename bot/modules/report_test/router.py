from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
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


@router.channel_post()
async def auto_bind_from_private_channel_activity(
    message: Message,
    session: AsyncSession,
    settings: AppSettings,
) -> None:
    """Auto-bind from ordinary activity in an eligible private channel.

    This removes the need for a visible /bindreporttest command. The campaign is
    stored by Telegram numeric chat ID, so rotating private invite links does not
    change the destination.
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
            force=False,
        )
        if bound:
            logger.info(
                "Private report test channel auto-detected from channel activity chat_id=%s",
                message.chat.id,
            )
    except Exception:
        logger.exception(
            "Failed to auto-detect private report test channel chat_id=%s",
            message.chat.id,
        )
