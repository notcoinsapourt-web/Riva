from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)


def button(
    text: str,
    *,
    callback_data: str,
    custom_emoji_id: str | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    """Create a modern Telegram button with optional Bot API premium styling."""

    payload: dict[str, object] = {"text": text, "callback_data": callback_data}
    if custom_emoji_id:
        payload["icon_custom_emoji_id"] = custom_emoji_id
    if style:
        payload["style"] = style
    return InlineKeyboardButton(**payload)  # type: ignore[arg-type]


def keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def persistent_home_keyboard() -> ReplyKeyboardMarkup:
    """Keep a large, single-tap home button below the Telegram composer."""

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 منو")]],
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
