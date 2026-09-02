from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import AppSettings, get_settings
from bot.core.emojis import valid_custom_emoji_id
from bot.database.models import ActivityLog, Product
from bot.services.logs import ActivityLogService
from bot.services.orders import OrderService
from bot.services.settings import SettingsService

logger = logging.getLogger(__name__)

REPORT_ACTION = "order.channel_report_sent"


@dataclass(frozen=True, slots=True)
class ReportDelivery:
    chat_id: int
    message_id: int
    premium_emoji_used: bool


@dataclass(frozen=True, slots=True)
class OrderReportPayload:
    buyer: str
    product_name: str
    quantity: int
    amount: int
    created_at: datetime
    product_emoji: str = "💎"
    is_test: bool = False


class OrderReportService:
    """Publish safe, product-agnostic order reports without affecting checkout."""

    _locks: ClassVar[defaultdict[tuple[int, int], asyncio.Lock]] = defaultdict(asyncio.Lock)

    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        settings: AppSettings | None = None,
    ) -> None:
        self.session = session
        self.bot = bot
        self.settings = settings or get_settings()

    async def send_order(self, order_id: int) -> bool:
        """Send one order once per running database, swallowing Telegram failures."""

        if self.settings.order_report_target is None:
            return False

        lock_key = (id(asyncio.get_running_loop()), order_id)
        async with self._locks[lock_key]:
            existing = await self.session.scalar(
                select(ActivityLog.id)
                .where(
                    ActivityLog.action == REPORT_ACTION,
                    ActivityLog.entity_type == "order",
                    ActivityLog.entity_id == str(order_id),
                )
                .limit(1)
            )
            if existing is not None:
                return True

            try:
                order = await OrderService(self.session).get(order_id)
                shop_name = await SettingsService(self.session).get(
                    "shop_name", self.settings.shop_name
                )
                product_emoji_id = valid_custom_emoji_id(
                    order.product.custom_emoji_id if order.product else None
                )
                button_emoji_id = valid_custom_emoji_id(
                    self.settings.order_report_button_emoji_id
                ) or product_emoji_id
                payload = OrderReportPayload(
                    buyer=mask_identifier(order.user.telegram_id),
                    product_name=order.product_name,
                    quantity=order.quantity,
                    amount=order.total_amount,
                    created_at=order.created_at,
                    product_emoji=order.product.emoji if order.product else "💎",
                )
                delivery = await self._deliver(
                    payload,
                    shop_name=shop_name,
                    product_custom_emoji_id=product_emoji_id,
                    button_custom_emoji_id=button_emoji_id,
                    verify_permissions=False,
                )
            except TelegramAPIError as exc:
                logger.warning("Order report delivery failed for order %s: %s", order_id, exc)
                return False
            except Exception:
                logger.exception("Unexpected order report failure for order %s", order_id)
                return False

            try:
                await ActivityLogService(self.session).record(
                    REPORT_ACTION,
                    entity_type="order",
                    entity_id=order_id,
                    details={
                        "chat_id": delivery.chat_id,
                        "message_id": delivery.message_id,
                        "premium_emoji_used": delivery.premium_emoji_used,
                    },
                )
            except Exception:
                logger.exception(
                    "Order report was sent but its idempotency log could not be recorded: %s",
                    order_id,
                )
            return True

    async def send_test(self) -> ReportDelivery:
        """Send a controlled test through exactly the same report renderer/delivery path."""

        shop_name = await SettingsService(self.session).get(
            "shop_name", self.settings.shop_name
        )
        existing_emoji_id = await self.session.scalar(
            select(Product.custom_emoji_id)
            .where(
                Product.custom_emoji_id.is_not(None),
                Product.custom_emoji_id != "",
            )
            .order_by(Product.id)
            .limit(1)
        )
        product_emoji_id = valid_custom_emoji_id(existing_emoji_id)
        button_emoji_id = valid_custom_emoji_id(
            self.settings.order_report_button_emoji_id
        ) or product_emoji_id
        return await self._deliver(
            OrderReportPayload(
                buyer="09******123",
                product_name="Telegram Stars - Test Order",
                quantity=1,
                amount=10_000,
                created_at=datetime.now(UTC),
                product_emoji="⭐",
                is_test=True,
            ),
            shop_name=shop_name,
            product_custom_emoji_id=product_emoji_id,
            button_custom_emoji_id=button_emoji_id,
            verify_permissions=True,
        )

    async def _deliver(
        self,
        payload: OrderReportPayload,
        *,
        shop_name: str,
        product_custom_emoji_id: str | None,
        button_custom_emoji_id: str | None,
        verify_permissions: bool,
    ) -> ReportDelivery:
        target = self.settings.order_report_target
        if target is None:
            raise RuntimeError("ORDER_REPORT_CHANNEL_ID is not configured.")

        chat = await self.bot.get_chat(target)
        me = await self.bot.get_me()
        if verify_permissions:
            member = await self.bot.get_chat_member(chat.id, me.id)
            status = getattr(member.status, "value", str(member.status))
            if status not in {"administrator", "creator"}:
                raise RuntimeError(
                    f"Bot must be an administrator in report channel; current status={status}"
                )
            if status == "administrator" and getattr(member, "can_post_messages", True) is False:
                raise RuntimeError("Bot administrator is missing can_post_messages permission.")

        username = me.username or ""
        rich_text = build_report_text(
            payload,
            shop_name=shop_name,
            bot_username=username,
            timezone_name=self.settings.timezone,
            custom_emoji_id=product_custom_emoji_id,
        )
        fallback_text = build_report_text(
            payload,
            shop_name=shop_name,
            bot_username=username,
            timezone_name=self.settings.timezone,
            custom_emoji_id=None,
        )
        rich_markup = build_cta_markup(username, button_custom_emoji_id)
        fallback_markup = build_cta_markup(username, None)

        premium_requested = bool(product_custom_emoji_id or button_custom_emoji_id)
        try:
            message = await self.bot.send_message(
                chat.id,
                rich_text if premium_requested else fallback_text,
                reply_markup=rich_markup if premium_requested else fallback_markup,
            )
            premium_used = premium_requested
        except TelegramBadRequest as exc:
            if not premium_requested:
                raise
            logger.warning(
                "Telegram rejected a Premium Emoji in order report; retrying with Unicode: %s",
                exc,
            )
            message = await self.bot.send_message(
                chat.id,
                fallback_text,
                reply_markup=fallback_markup,
            )
            premium_used = False

        logger.info(
            "Order report sent chat_id=%s message_id=%s premium_emoji_used=%s",
            chat.id,
            message.message_id,
            premium_used,
        )
        return ReportDelivery(
            chat_id=chat.id,
            message_id=message.message_id,
            premium_emoji_used=premium_used,
        )


def mask_identifier(value: object) -> str:
    text = str(value).strip()
    if len(text) <= 4:
        return "*" * max(4, len(text))
    return f"{text[:2]}******{text[-2:]}"


def build_report_text(
    payload: OrderReportPayload,
    *,
    shop_name: str,
    bot_username: str,
    timezone_name: str,
    custom_emoji_id: str | None,
) -> str:
    safe_shop = escape(shop_name.strip() or "Persian Shop")
    safe_product = escape(payload.product_name.strip() or "محصول")
    quantity = max(1, int(payload.quantity))
    quantity_suffix = f" × {quantity:,}" if quantity != 1 else ""
    product_icon = _premium_icon(payload.product_emoji, custom_emoji_id)
    status = "#خرید_موفق #تست" if payload.is_test else "#خرید_موفق"
    bot_line = (
        f'<a href="https://t.me/{escape(bot_username)}">@{escape(bot_username)}</a>'
        if bot_username
        else "ربات فروشگاه"
    )
    timestamp = format_timestamp(payload.created_at, timezone_name)
    return (
        f"<b>گزارشات {safe_shop} | خرید از {safe_shop}</b>\n\n"
        f"🛍 گزارش <b>{status}</b>\n\n"
        f"🐸 خریدار: <code>{escape(payload.buyer)}</code>\n"
        f"{product_icon} سفارش: <b>{safe_product}{quantity_suffix}</b>\n"
        f"💸 مبلغ پرداخت شده: <b>{int(payload.amount):,} تومان</b>\n\n"
        f"📺 <code>{timestamp}</code>\n\n"
        f"🤖 {bot_line}"
    )


def build_cta_markup(
    bot_username: str,
    custom_emoji_id: str | None,
) -> InlineKeyboardMarkup:
    username = bot_username.strip().lstrip("@")
    url = f"https://t.me/{username}" if username else "https://t.me/"
    emoji_id = valid_custom_emoji_id(custom_emoji_id)
    payload: dict[str, object] = {
        "text": "\u200f| برای خرید اقدام کن!" if emoji_id else "🤖 | برای خرید اقدام کن!",
        "url": url,
        "style": "primary",
    }
    if emoji_id:
        payload["icon_custom_emoji_id"] = emoji_id
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(**payload)]]  # type: ignore[arg-type]
    )


def format_timestamp(value: datetime, timezone_name: str) -> str:
    timestamp = value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = UTC
    return timestamp.astimezone(timezone).strftime("%Y/%m/%d %H:%M:%S")


def _premium_icon(fallback: str, custom_emoji_id: str | None) -> str:
    safe_fallback = escape((fallback or "💎").strip() or "💎")
    emoji_id = valid_custom_emoji_id(custom_emoji_id)
    if emoji_id is None:
        return safe_fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{safe_fallback}</tg-emoji>'
