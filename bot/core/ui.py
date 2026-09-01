from __future__ import annotations

import html
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputRichMessage,
    Message,
    ReplyKeyboardMarkup,
)

from bot.core.emojis import (
    inline_button_fallback,
    keyboard_without_premium,
    remember_button_fallback,
    reply_button,
    resolve_button_emoji,
)

logger = logging.getLogger(__name__)


def button(
    text: str,
    *,
    callback_data: str,
    custom_emoji_id: str | None = None,
    style: str | None = None,
    emoji_key: str | None = None,
) -> InlineKeyboardButton:
    """Create a modern Telegram button with optional Bot API premium styling."""

    resolved = resolve_button_emoji(
        text,
        custom_emoji_id=custom_emoji_id,
        emoji_key=emoji_key,
    )
    payload: dict[str, object] = {"text": resolved.text, "callback_data": callback_data}
    if resolved.custom_emoji_id:
        payload["icon_custom_emoji_id"] = resolved.custom_emoji_id
        remember_button_fallback(
            callback_data=callback_data,
            text=resolved.text,
            custom_emoji_id=resolved.custom_emoji_id,
            fallback_text=resolved.fallback_text,
        )
    if style:
        payload["style"] = style
    return InlineKeyboardButton(**payload)  # type: ignore[arg-type]


def keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def persistent_home_keyboard() -> ReplyKeyboardMarkup:
    """Keep a large, single-tap home button below the Telegram composer."""

    return ReplyKeyboardMarkup(
        keyboard=[[reply_button("🏠 منو", emoji_key="home")]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یک گزینه را انتخاب کنید",
    )


async def edit_or_send(
    event: CallbackQuery | Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    rich_message = _rich_message_with_buttons(text, reply_markup)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            if rich_message is not None:
                try:
                    return await event.message.edit_text(rich_message=rich_message)
                except TelegramBadRequest as exc:
                    if "message is not modified" in str(exc).lower():
                        return event.message
                    logger.warning(
                        "Rich RTL keyboard was rejected; using standard keyboard: %s", exc
                    )
                    reply_markup = keyboard_without_premium(reply_markup)  # type: ignore[assignment]
            try:
                return await event.message.edit_text(text, reply_markup=reply_markup)
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    return event.message
                if "there is no text" not in str(exc).lower():
                    raise
                await event.message.delete()
                return await event.message.answer(text, reply_markup=reply_markup)
        return None
    if rich_message is not None:
        try:
            return await event.bot.send_rich_message(
                chat_id=event.chat.id,
                rich_message=rich_message,
            )
        except TelegramBadRequest as exc:
            logger.warning(
                "Rich RTL keyboard was rejected; using standard keyboard: %s", exc
            )
            reply_markup = keyboard_without_premium(reply_markup)  # type: ignore[assignment]
    return await event.answer(text, reply_markup=reply_markup)


def _rich_message_with_buttons(
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> InputRichMessage | None:
    """Embed premium emoji in RTL button text using Bot API 10.3 Rich Messages.

    Standard ``icon_custom_emoji_id`` is rendered on the wrong physical side by
    some Telegram clients for Persian labels. Rich buttons keep the emoji inside
    their RTL text, so its visual position is deterministic. Unsupported button
    types continue to use the ordinary inline-keyboard path.
    """

    if reply_markup is None:
        return None
    buttons = [item for row in reply_markup.inline_keyboard for item in row]
    if not any(item.icon_custom_emoji_id for item in buttons):
        return None
    if any(not item.callback_data for item in buttons):
        return None

    rows: list[str] = []
    for row in reply_markup.inline_keyboard:
        rendered: list[str] = []
        for item in row:
            label = item.text.lstrip("\u200e\u200f")
            if item.icon_custom_emoji_id:
                fallback = inline_button_fallback(item)
                alternative = _leading_button_emoji(fallback) or "✨"
                icon = (
                    f'<tg-emoji emoji-id="{html.escape(item.icon_custom_emoji_id, quote=True)}">'
                    f"{html.escape(alternative)}</tg-emoji>&nbsp;"
                )
            else:
                icon = ""
            style = (
                f' style="{html.escape(item.style, quote=True)}"' if item.style else ""
            )
            rendered.append(
                f'<tg-button type="callback_data"{style} '
                f'data="{html.escape(item.callback_data or "", quote=True)}">'
                f"{icon}{html.escape(label)}</tg-button>"
            )
        rows.append(f'<tg-button-row align="right">{"".join(rendered)}</tg-button-row>')

    return InputRichMessage(
        html=f"<p>{text}</p>{''.join(rows)}",
        is_rtl=True,
        skip_entity_detection=True,
    )


def _leading_button_emoji(text: str) -> str | None:
    token, separator, _ = text.partition(" ")
    if not separator or any(character.isalnum() for character in token):
        return None
    return token


async def replace_media_message(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    await callback.answer()
    if isinstance(callback.message, Message):
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        return await callback.message.answer(text, reply_markup=reply_markup)
    return None
