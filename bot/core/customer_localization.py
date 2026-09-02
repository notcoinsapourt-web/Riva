from __future__ import annotations

import re
from copy import deepcopy

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods.base import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from bot.core.language import _telegram_id, current_language, translate_text

PERSIAN_RE = re.compile(r"[\u0600-\u06ff]")
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# These are only a final cleanup for button labels. The regular localization
# dictionary remains the primary translator. This list covers the product/menu
# fragments that previously produced mixed labels such as “Followers اقتصادی”.
BUTTON_FRAGMENT_EN: tuple[tuple[str, str], ...] = tuple(
    sorted(
        {
            "پکیج شروع کانال": "Channel Starter Pack",
            "پکیج شروع پیج": "Account Starter Pack",
            "پکیج شروع": "Starter Pack",
            "پکیج وایرال": "Viral Pack",
            "ری‌اکشن مثبت": "Positive Reactions",
            "رأی نظرسنجی": "Poll Votes",
            "رای نظرسنجی": "Poll Votes",
            "زمان تماشا": "Watch Time",
            "پست آینده": "Future Posts",
            "ذخیره پست": "Saves",
            "ذخیره ویدیو": "Saves",
            "کیفیت بالا": "Premium",
            "اشتراک‌گذاری": "Shares",
            "سوالات متداول": "FAQ",
            "سؤالات متداول": "FAQ",
            "هوش مصنوعی": "AI",
            "دوازده‌ماهه": "12 Months",
            "شش‌ماهه": "6 Months",
            "سه‌ماهه": "3 Months",
            "یک‌ماهه": "1 Month",
            "اختصاصی": "Personal",
            "اشتراکی": "Shared",
            "اقتصادی": "Economy",
            "ایرانی": "Iranian",
            "فالوور": "Followers",
            "سابسکرایب": "Subscribers",
            "سابسکرایبر": "Subscribers",
            "بازدید": "Views",
            "ویو": "Views",
            "لایک": "Likes",
            "کامنت": "Comments",
            "دلخواه": "Custom",
            "ممبر": "Members",
            "ری‌اکشن": "Reactions",
            "نظرسنجی": "Poll",
            "ریلز": "Reels",
            "استوری": "Story",
            "ذخیره": "Saves",
            "پست": "Post",
            "ویدیو": "Video",
            "کانال": "Channel",
            "پیج": "Account",
            "تلگرام": "Telegram",
            "اینستاگرام": "Instagram",
            "تیک‌تاک": "TikTok",
            "یوتیوب": "YouTube",
            "تردز": "Threads",
            "دیسکورد": "Discord",
            "توییچ": "Twitch",
            "لینکدین": "LinkedIn",
            "اکانت": "Account",
            "پرمیوم": "Premium",
            "پریمیوم": "Premium",
            "اشتراک": "Subscription",
            "سالانه": "Annual",
            "ماهه": "Month",
            "موزیک": "Music",
            "فیلم": "Streaming",
            "خدمات": "Services",
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

WELCOME_EN = (
    "Hello {first_name} 👋\n"
    "Welcome to Arvan Coin.\n"
    "Here you can quickly and securely get subscriptions for popular services, "
    "premium accounts, and AI tools.\n\n"
    "⚡️ Fast delivery after your order is placed\n"
    "🛡 Support and guarantee\n"
    "💎 Tested and reliable accounts\n"
    "🎵 Music, streaming, and AI subscriptions\n"
    "💰 Competitive prices\n\n"
    "Choose the service you need from the product menu and place your order 🚀"
)

RULES_EN = (
    "<b>📄 Purchase Guide & Rules</b>\n\n"
    "• Read the full product description before placing an order.\n"
    "• Send only the public link or information requested for that product.\n"
    "• Never send passwords, login codes, or banking information to the bot.\n"
    "• The final price is shown before payment.\n"
    "• Order updates and support replies are delivered through this bot."
)

FAQ_EN = (
    "<b>❓ Frequently Asked Questions</b>\n\n"
    "• Read each product’s details and required information before ordering.\n"
    "• Send only the requested public link or account information.\n"
    "• Never send passwords, login codes, or banking information.\n"
    "• The final amount is shown before payment.\n"
    "• Order updates and support replies are sent through this bot."
)

FAQ_PHRASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        {
            "سوالات متداول": "Frequently Asked Questions",
            "سؤالات متداول": "Frequently Asked Questions",
            "قبل از خرید، توضیحات محصول را کامل بخوانید.": (
                "Read the full product description before placing an order."
            ),
            "فقط لینک عمومی و اطلاعات خواسته‌شده را ارسال کنید.": (
                "Send only the requested public link or information."
            ),
            "رمز عبور، کد ورود و اطلاعات بانکی را برای ربات نفرستید.": (
                "Never send passwords, login codes, or banking information to the bot."
            ),
            "قیمت نهایی پیش از پرداخت نمایش داده می‌شود.": (
                "The final price is shown before payment."
            ),
            "وضعیت سفارش و پاسخ پشتیبانی از همین ربات اعلام می‌شود.": (
                "Order updates and support replies are delivered through this bot."
            ),
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def contains_persian(value: str | None) -> bool:
    return bool(value and PERSIAN_RE.search(value))


def strict_button_english(value: str) -> str:
    translated = (translate_text(value, "en") or value).translate(PERSIAN_DIGITS)
    for source, target in BUTTON_FRAGMENT_EN:
        translated = translated.replace(source, target)
    # Existing customer buttons are fully covered by the main dictionary plus
    # the fragments above. If a newly edited product label adds an unknown
    # Persian adjective, avoid a half-Persian/half-English button by dropping
    # only the unknown Persian token while preserving the translated label.
    translated = re.sub(r"[\u0600-\u06ff\u200c]+", "", translated)
    translated = re.sub(r"\s{2,}", " ", translated).strip()
    return translated or "Select"


def english_rules_from_persian(source: str) -> str:
    translated = translate_text(source, "en") or source
    for persian, english in FAQ_PHRASES:
        translated = translated.replace(persian, english)
    if not contains_persian(translated):
        return translated
    if "سوالات متداول" in source or "سؤالات متداول" in source:
        return FAQ_EN
    return RULES_EN


class EnglishButtonCleanupMiddleware(BaseRequestMiddleware):
    """Guarantee English customer buttons never contain Persian fragments."""

    async def __call__(
        self,
        make_request,
        bot: Bot,
        method: TelegramMethod,
    ):
        if current_language() != "en":
            return await make_request(bot, method)
        target = getattr(method, "chat_id", None)
        current_user = _telegram_id.get()
        if target is not None and current_user is not None and str(target) != str(current_user):
            return await make_request(bot, method)
        markup = getattr(method, "reply_markup", None)
        if isinstance(markup, (InlineKeyboardMarkup, ReplyKeyboardMarkup)):
            localized = deepcopy(markup)
            rows = (
                localized.inline_keyboard
                if isinstance(localized, InlineKeyboardMarkup)
                else localized.keyboard
            )
            for row in rows:
                for item in row:
                    item.text = strict_button_english(item.text)
            if isinstance(localized, ReplyKeyboardMarkup) and localized.input_field_placeholder:
                localized.input_field_placeholder = strict_button_english(
                    localized.input_field_placeholder
                )
            method.reply_markup = localized
        return await make_request(bot, method)
