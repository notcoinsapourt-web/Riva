from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

from bot.core.emojis import remember_button_fallback, reply_button, resolve_button_emoji


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


def persistent_language_keyboard(language: str = "fa") -> ReplyKeyboardMarkup:
    """Keep language switching available below the Telegram composer."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                reply_button(
                    "🌐 Change language" if language == "en" else "🌐 تغییر زبان",
                    emoji_key="language",
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=(
            "Choose an option" if language == "en" else "یک گزینه را انتخاب کنید"
        ),
    )


def persistent_home_keyboard() -> ReplyKeyboardMarkup:
    """Backward-compatible alias for older imports and cached clients."""

    return persistent_language_keyboard()


async def edit_or_send(
    event: CallbackQuery | Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
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
    return await event.answer(text, reply_markup=reply_markup)


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
