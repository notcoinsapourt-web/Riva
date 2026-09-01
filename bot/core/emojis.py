from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import TypeVar

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import TelegramMethod
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

logger = logging.getLogger(__name__)
TelegramResult = TypeVar("TelegramResult")

# Central premium icon registry. Put valid numeric custom_emoji_id values here to
# change matching buttons across the entire bot without editing individual routers.
PREMIUM_EMOJIS: dict[str, str | None] = {
    "shop": None,
    "products": None,
    "orders": None,
    "wallet": None,
    "profile": None,
    "settings": None,
    "home": None,
    "back": None,
    "support": None,
    "users": None,
    "categories": None,
    "coupons": None,
    "broadcast": None,
    "revenue": None,
    "admin": None,
    "referral": None,
    "add": None,
    "edit": None,
    "delete": None,
    "success": None,
    "cancel": None,
    "quantity": None,
    "buy": None,
    "info": None,
    "next": None,
    "previous": None,
}

FALLBACK_EMOJIS: dict[str, str] = {
    "shop": "🛍",
    "products": "💎",
    "orders": "📦",
    "wallet": "💰",
    "profile": "👤",
    "settings": "⚙️",
    "home": "🏠",
    "back": "↩️",
    "support": "🎧",
    "users": "👥",
    "categories": "🗂",
    "coupons": "🎟",
    "broadcast": "📢",
    "revenue": "📈",
    "admin": "👑",
    "referral": "🎁",
    "add": "➕",
    "edit": "✏️",
    "delete": "🗑",
    "success": "✅",
    "cancel": "❌",
    "quantity": "🔢",
    "buy": "🛒",
    "info": "ℹ️",
    "next": "▶️",
    "previous": "◀️",
}

KEYWORDS: tuple[tuple[str, str], ...] = (
    ("منوی اصلی", "home"),
    ("بازگشت", "back"),
    ("محصول", "products"),
    ("سفارش", "orders"),
    ("کیف پول", "wallet"),
    ("موجودی", "wallet"),
    ("حساب", "profile"),
    ("تنظیمات", "settings"),
    ("پشتیبانی", "support"),
    ("تیکت", "support"),
    ("کاربر", "users"),
    ("دسته", "categories"),
    ("تخفیف", "coupons"),
    ("پیام همگانی", "broadcast"),
    ("درآمد", "revenue"),
    ("مدیریت", "admin"),
    ("دعوت", "referral"),
    ("افزودن", "add"),
    ("ویرایش", "edit"),
    ("حذف", "delete"),
    ("لغو", "cancel"),
    ("تعداد", "quantity"),
    ("خرید", "buy"),
    ("بعدی", "next"),
    ("قبلی", "previous"),
)


@dataclass(frozen=True, slots=True)
class ResolvedButtonEmoji:
    text: str
    custom_emoji_id: str | None
    fallback_text: str


_BUTTON_FALLBACKS: dict[tuple[str, str, str], str] = {}


def valid_custom_emoji_id(value: str | None) -> str | None:
    clean = (value or "").strip()
    return clean if clean.isdecimal() else None


def resolve_button_emoji(
    text: str,
    *,
    custom_emoji_id: str | None = None,
    emoji_key: str | None = None,
) -> ResolvedButtonEmoji:
    key, fallback = _detect_key(text, emoji_key)
    emoji_id = valid_custom_emoji_id(custom_emoji_id)
    if emoji_id and fallback is None:
        fallback = _leading_emoji_token(text)
    if emoji_id is None and key:
        emoji_id = valid_custom_emoji_id(PREMIUM_EMOJIS.get(key))
    if emoji_id is None:
        return ResolvedButtonEmoji(text=text, custom_emoji_id=None, fallback_text=text)

    clean_text = text
    if fallback and clean_text.startswith(fallback):
        clean_text = clean_text[len(fallback) :].lstrip(" •|-")
    fallback_text = (
        text if fallback and text.startswith(fallback) else _with_fallback(text, fallback)
    )
    return ResolvedButtonEmoji(
        text=clean_text or text,
        custom_emoji_id=emoji_id,
        fallback_text=fallback_text,
    )


def remember_button_fallback(
    *, callback_data: str | None, text: str, custom_emoji_id: str, fallback_text: str
) -> None:
    _BUTTON_FALLBACKS[(callback_data or "", text, custom_emoji_id)] = fallback_text


def reply_button(text: str, *, emoji_key: str | None = None) -> KeyboardButton:
    resolved = resolve_button_emoji(text, emoji_key=emoji_key)
    if resolved.custom_emoji_id:
        remember_button_fallback(
            callback_data=None,
            text=resolved.text,
            custom_emoji_id=resolved.custom_emoji_id,
            fallback_text=resolved.fallback_text,
        )
    return KeyboardButton(
        text=resolved.text,
        icon_custom_emoji_id=resolved.custom_emoji_id,
    )


def extract_custom_emoji_id(message: Message) -> str | None:
    for entity in (*list(message.entities or ()), *list(message.caption_entities or ())):
        value = valid_custom_emoji_id(entity.custom_emoji_id)
        if value:
            return value
    return None


async def validate_custom_emoji(bot: Bot, emoji_id: str) -> bool:
    value = valid_custom_emoji_id(emoji_id)
    if value is None:
        return False
    try:
        return bool(await bot.get_custom_emoji_stickers([value]))
    except TelegramBadRequest:
        return False


class PremiumEmojiFallbackMiddleware(BaseRequestMiddleware):
    """Retry rejected keyboard icons once with their Unicode fallback text."""

    async def __call__(self, make_request, bot: Bot, method: TelegramMethod[TelegramResult]):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            if not _is_custom_emoji_error(exc):
                raise
            markup = getattr(method, "reply_markup", None)
            fallback_markup = keyboard_without_premium(markup)
            if fallback_markup is None:
                raise
            logger.warning("Telegram rejected premium keyboard icons; retrying with Unicode")
            return await make_request(
                bot, method.model_copy(update={"reply_markup": fallback_markup})
            )


def keyboard_without_premium(
    markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None,
) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | None:
    if isinstance(markup, InlineKeyboardMarkup):
        rows = [[_inline_without_premium(item) for item in row] for row in markup.inline_keyboard]
        return InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(markup, ReplyKeyboardMarkup):
        rows = [[_reply_without_premium(item) for item in row] for row in markup.keyboard]
        return markup.model_copy(update={"keyboard": rows})
    return None


def _inline_without_premium(item: InlineKeyboardButton) -> InlineKeyboardButton:
    emoji_id = item.icon_custom_emoji_id
    if not emoji_id:
        return item
    fallback = _BUTTON_FALLBACKS.get(
        (item.callback_data or "", item.text, emoji_id),
        item.text,
    )
    return item.model_copy(update={"text": fallback, "icon_custom_emoji_id": None})


def _reply_without_premium(item: KeyboardButton) -> KeyboardButton:
    emoji_id = item.icon_custom_emoji_id
    if not emoji_id:
        return item
    fallback = _BUTTON_FALLBACKS.get(("", item.text, emoji_id), item.text)
    return item.model_copy(update={"text": fallback, "icon_custom_emoji_id": None})


def _detect_key(text: str, requested: str | None) -> tuple[str | None, str | None]:
    if requested in FALLBACK_EMOJIS:
        return requested, FALLBACK_EMOJIS[requested]
    for key, fallback in sorted(
        FALLBACK_EMOJIS.items(), key=lambda item: len(item[1]), reverse=True
    ):
        if text.startswith(fallback):
            return key, fallback
    for keyword, key in KEYWORDS:
        if keyword in text:
            return key, FALLBACK_EMOJIS[key]
    return None, None


def _with_fallback(text: str, fallback: str | None) -> str:
    return f"{fallback} {text}" if fallback else text


def _leading_emoji_token(text: str) -> str | None:
    token, separator, _ = text.partition(" ")
    if not separator or any(character.isalnum() for character in token):
        return None
    return (
        token
        if any(unicodedata.category(character) in {"So", "Sk"} for character in token)
        else None
    )


def _is_custom_emoji_error(exc: TelegramBadRequest) -> bool:
    message = str(exc).lower()
    return "custom emoji" in message or "icon_custom_emoji_id" in message
