from __future__ import annotations

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.emojis import (
    extract_custom_emoji_id,
    valid_custom_emoji_id,
    validate_custom_emoji,
    verify_custom_emoji_button_access,
)
from bot.modules.admin.common import protected_router
from bot.services.order_reports import OrderReportService
from bot.services.settings import SettingsService

router = protected_router("settings")

SLOTS: dict[str, tuple[str, str]] = {
    "shop": ("🛍 گزارش خرید", "order_report_emoji_shop"),
    "buyer": ("🐸 خریدار", "order_report_emoji_buyer"),
    "product": ("💎 سفارش", "order_report_emoji_product"),
    "amount": ("💸 مبلغ", "order_report_emoji_amount"),
    "time": ("📺 زمان", "order_report_emoji_time"),
    "bot": ("🤖 ربات", "order_report_emoji_bot"),
    "button": ("دکمه «برای خرید اقدام کن»", "order_report_emoji_button"),
}


@router.message(Command("reportemoji"))
async def report_emoji_command(message: Message, bot: Bot, session: AsyncSession) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) == 1 or parts[1].lower() in {"show", "help"}:
        await _show_help(message, session)
        return

    action = parts[1].lower()
    if action == "test":
        delivery = await OrderReportService(session, bot).send_test()
        await message.answer(
            "✅ تست گزارش ارسال شد.\n"
            f"Message ID: <code>{delivery.message_id}</code>\n"
            f"Premium Emoji: <b>{'فعال' if delivery.premium_emoji_used else 'Fallback معمولی'}</b>"
        )
        return

    slot = SLOTS.get(action)
    if slot is None:
        await message.answer("نام بخش معتبر نیست. /reportemoji را بدون پارامتر بفرستید.")
        return

    if len(parts) >= 3 and parts[2].strip() == "0":
        await SettingsService(session).set(slot[1], "")
        await message.answer(f"✅ ایموجی Premium بخش «{slot[0]}» حذف شد.")
        return

    raw_value = parts[2].strip() if len(parts) >= 3 else ""
    emoji_id = extract_custom_emoji_id(message) or valid_custom_emoji_id(raw_value)
    if emoji_id is None or not await validate_custom_emoji(bot, emoji_id):
        await message.answer(
            "یک ایموجی Premium متحرک را در همان پیام بفرستید یا Custom Emoji ID عددی معتبر وارد کنید.\n\n"
            "مثال: <code>/reportemoji amount</code> سپس همان‌جا ایموجی Premium را قرار دهید."
        )
        return

    if action == "button" and not await verify_custom_emoji_button_access(
        bot, message.chat.id, emoji_id
    ):
        await message.answer(
            "⚠️ تلگرام این Custom Emoji را برای دکمه‌های ربات قبول نکرد. "
            "برای متن می‌توانید از آن استفاده کنید، اما برای دکمه یک Emoji مجاز دیگر بفرستید."
        )
        return

    await SettingsService(session).set(slot[1], emoji_id)
    await message.answer(
        f"✅ ایموجی Premium بخش «{slot[0]}» ذخیره شد.\n"
        f"ID: <code>{emoji_id}</code>\n\n"
        "برای دیدن نتیجه: <code>/reportemoji test</code>"
    )


async def _show_help(message: Message, session: AsyncSession) -> None:
    settings = SettingsService(session)
    lines = [
        "<b>💠 تنظیم Premium Emoji گزارش کانال</b>",
        "",
        "برای هر خط گزارش می‌توانید ایموجی Premium جدا تعیین کنید:",
    ]
    for key, (label, setting_key) in SLOTS.items():
        value = await settings.get(setting_key, "")
        lines.append(
            f"• <code>{key}</code> — {label}: "
            f"<code>{value}</code>" if value else f"• <code>{key}</code> — {label}: تنظیم نشده"
        )
    lines.extend(
        [
            "",
            "روش تنظیم:",
            "<code>/reportemoji shop</code> + ایموجی Premium",
            "<code>/reportemoji buyer</code> + ایموجی Premium",
            "<code>/reportemoji product</code> + ایموجی Premium",
            "<code>/reportemoji amount</code> + ایموجی Premium",
            "<code>/reportemoji time</code> + ایموجی Premium",
            "<code>/reportemoji bot</code> + ایموجی Premium",
            "<code>/reportemoji button</code> + ایموجی Premium",
            "",
            "حذف یک مورد: <code>/reportemoji amount 0</code>",
            "پیش‌نمایش کانال: <code>/reportemoji test</code>",
        ]
    )
    await message.answer("\n".join(lines))
