# ruff: noqa: E501
from __future__ import annotations

import re
from contextvars import ContextVar, Token
from copy import deepcopy

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageCaption,
    EditMessageText,
    SendDocument,
    SendMessage,
    SendPhoto,
)
from aiogram.methods.base import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

SUPPORTED_LANGUAGES = {"fa", "en"}
_language: ContextVar[str] = ContextVar("user_language", default="fa")
_telegram_id: ContextVar[int | None] = ContextVar("user_telegram_id", default=None)


def normalize_language(value: str | None) -> str:
    code = (value or "fa").split("-", 1)[0].lower()
    return code if code in SUPPORTED_LANGUAGES else "fa"


def current_language() -> str:
    return normalize_language(_language.get())


def language_tokens(language: str, telegram_id: int) -> tuple[Token[str], Token[int | None]]:
    return _language.set(normalize_language(language)), _telegram_id.set(telegram_id)


def reset_language(tokens: tuple[Token[str], Token[int | None]]) -> None:
    language_token, user_token = tokens
    _language.reset(language_token)
    _telegram_id.reset(user_token)


def set_current_language(language: str) -> Token[str]:
    return _language.set(normalize_language(language))


def reset_current_language(token: Token[str]) -> None:
    _language.reset(token)


def is_english(language: str | None = None) -> bool:
    return normalize_language(language or current_language()) == "en"


def choose(fa: str, en: str, language: str | None = None) -> str:
    return en if is_english(language) else fa


CATEGORY_EN = {
    "اشتراک هوش مصنوعی": "AI Subscriptions",
    "خدمات تلگرام": "Telegram Services",
    "خدمات اینستاگرام": "Instagram Services",
    "خدمات تیک‌تاک": "TikTok Services",
    "خدمات یوتیوب": "YouTube Services",
    "سایر محصولات دیجیتال": "Other Digital Products",
    "سایر شبکه‌های اجتماعی": "Other Social Networks",
}


def category_name(value: str, language: str | None = None) -> str:
    if not is_english(language):
        return value
    return CATEGORY_EN.get(value, translate_text(value, "en"))


PRODUCT_TERMS = (
    ("فالوور", "Followers"),
    ("لایک", "Likes"),
    ("بازدید", "Views"),
    ("ویو", "Views"),
    ("کامنت", "Comments"),
    ("ممبر", "Members"),
    ("سابسکرایبر", "Subscribers"),
    ("رأی نظرسنجی", "Poll Votes"),
    ("رای نظرسنجی", "Poll Votes"),
    ("اشتراک", "Subscription"),
    ("ایرانی", "Iranian"),
    ("خارجی", "Global"),
    ("واقعی", "Real"),
    ("تضمینی", "Guaranteed"),
    ("تلگرام", "Telegram"),
    ("اینستاگرام", "Instagram"),
    ("تیک‌تاک", "TikTok"),
    ("یوتیوب", "YouTube"),
)


def product_name(value: str, language: str | None = None) -> str:
    if not is_english(language):
        return value
    translated = value
    for source, target in PRODUCT_TERMS:
        translated = translated.replace(source, target)
    return translated


# Ordered longest-first. These phrases cover the customer-facing interface while
# owner-authored Persian content remains untouched in the database.
PHRASES_EN = tuple(
    sorted(
        {
            "برای ورود به فروشگاه ابتدا در همه کانال‌های زیر عضو شوید و سپس «بررسی عضویت» را بزنید.": "Join all channels below first, then tap “Check membership” to enter the shop.",
            "اطلاعات حساب به‌صورت خودکار با تلگرام همگام می‌شود.": "Your account details are synchronized with Telegram automatically.",
            "هر تغییر وضعیت از طریق ربات به شما اطلاع داده می‌شود.": "The bot will notify you whenever the status changes.",
            "پاسخ پشتیبانی از طریق همین ربات ارسال می‌شود.": "Support replies will be delivered through this bot.",
            "پاسخ پشتیبانی": "Support reply",
            "پیام مدیریت Persian Shop": "Message from Persian Shop Admin",
            "پاداش پس از تکمیل اولین سفارش دوست شما ثبت می‌شود.": "The reward is credited after your friend completes their first order.",
            "پرداخت سفارش‌ها به‌صورت آنی و امن از موجودی انجام می‌شود.": "Orders are paid instantly and securely from your wallet balance.",
            "قیمت نهایی قبل از پرداخت نمایش داده می‌شود": "The final price is shown before payment",
            "سرویس فقط روی لینک عمومی انجام می‌شود؛ رمز عبور، کد ورود یا اطلاعات شخصی ارسال نکنید.": "The service works only with public links. Never send passwords, login codes, or personal data.",
            "فقط ایمیل یا نام کاربری لازم را بفرستید؛ رمز عبور و کد ورود را داخل ربات ارسال نکنید. اگر فعال‌سازی نیاز به هماهنگی داشته باشد، پشتیبانی راهنمایی می‌کند.": "Send only the required email or username. Never send a password or login code; support will guide you if activation needs coordination.",
            "فعال‌سازی از طریق Gift انجام می‌شود؛ فقط نام کاربری لازم است و نباید شماره، رمز عبور یا کد ورود ارسال کنید.": "Activation is completed by Gift. Only the username is required; never send a phone number, password, or login code.",
            "جلسه خرید منقضی شده؛ دوباره محصول را انتخاب کنید.": "Your checkout session expired. Please select the product again.",
            "اطلاعات پرداخت منقضی شده است؛ دوباره شروع کنید.": "Payment details expired. Please start again.",
            "برای دریافت اطلاعات و نرخ تازه، افزایش موجودی را دوباره شروع کنید.": "Start the top-up again to receive a fresh rate and payment details.",
            "پس از پرداخت، دکمه زیر را بزنید و رسید را ارسال کنید. موجودی فقط پس از بررسی و تأیید مدیریت افزایش می‌یابد.": "After payment, tap the button below and send your receipt. Your balance is credited only after admin approval.",
            "اکنون تصویر واضح فیش کارت‌به‌کارت را به صورت عکس یا فایل ارسال کنید.": "Now send a clear card-transfer receipt as a photo or file.",
            "اکنون تصویر رسید تراکنش را به صورت عکس یا فایل ارسال کنید.": "Now send the transaction receipt as a photo or file.",
            "لطفاً تصویر فیش را به صورت عکس یا فایل ارسال کنید.": "Please send the receipt as a photo or file.",
            "موجودی قابل استفاده": "Available balance",
            "افزایش موجودی": "Top up wallet",
            "تاریخچه تراکنش‌ها": "Transaction history",
            "تراکنشی وجود ندارد.": "No transactions yet.",
            "اطلاعات پرداخت": "Payment details",
            "مبلغ شارژ درخواستی": "Requested top-up",
            "مبلغ شارژ": "Top-up amount",
            "مبلغ قابل پرداخت": "Amount to pay",
            "نرخ لحظه‌ای هر تتر": "Live price per USDT",
            "زمان محاسبه": "Quote time",
            "منبع نرخ": "Rate source",
            "به وقت تهران": "Tehran time",
            "این نرخ و مقدار USDT تا ۱۵ دقیقه معتبر است. مبلغ را دقیقاً مطابق عدد بالا ارسال کنید.": "This USDT quote is valid for 15 minutes. Send the exact amount shown above.",
            "پرداخت کردم | ارسال رسید": "I paid | Send receipt",
            "کپی شماره کارت": "Copy card number",
            "کپی آدرس کیف پول": "Copy wallet address",
            "کپی مبلغ USDT": "Copy USDT amount",
            "کپی مبلغ": "Copy amount",
            "روش پرداخت را انتخاب کنید": "Choose a payment method",
            "کارت‌به‌کارت": "Card transfer",
            "هش تراکنش": "Transaction hash",
            "هش تراکنش معتبر نیست؛ دوباره ارسال کنید.": "The transaction hash is invalid. Please send it again.",
            "مهلت پرداخت تمام شد": "Payment time expired",
            "شروع دوباره": "Start again",
            "فیش شما با شماره": "Your receipt number",
            "درخواست شارژ": "Top-up request",
            "به کیف پول شما اضافه شد.": "was added to your wallet.",
            "تأیید نشد.": "was rejected.",
            "ثبت شد. پس از بررسی مدیر نتیجه اطلاع داده می‌شود.": "was submitted. You will be notified after review.",
            "فروشگاه خدمات مجازی": "Digital Services Shop",
            "یک دسته‌بندی را انتخاب کنید": "Choose a category",
            "یک محصول را انتخاب کنید": "Choose a product",
            "هنوز محصول فعالی در این دسته ثبت نشده است.": "There are no active products in this category yet.",
            "در حال حاضر محصول فعالی ثبت نشده است.": "There are no active products right now.",
            "پس از ثبت و بررسی سفارش": "After order review",
            "دسته‌بندی": "Category",
            "اطلاعات لازم": "Required information",
            "نرخ پایه": "Base price",
            "قیمت محصول": "Product price",
            "نوع سفارش": "Order type",
            "حداقل سفارش": "Minimum order",
            "حداکثر سفارش": "Maximum order",
            "گام تعداد": "Quantity step",
            "مبلغ محاسبه‌شده": "Calculated amount",
            "تعداد انتخابی": "Selected quantity",
            "چه چیزی ارسال کنم؟": "What should I send?",
            "ثبت تعداد و ادامه": "Enter quantity and continue",
            "ادامه خرید": "Continue to checkout",
            "تأیید نهایی سفارش": "Final order confirmation",
            "قیمت قبل از تخفیف": "Price before discount",
            "مبلغ نهایی": "Final amount",
            "موجودی کیف پول": "Wallet balance",
            "اطلاعات سفارش": "Order information",
            "پرداخت از کیف پول و ثبت": "Pay from wallet and submit",
            "کد تخفیف": "Discount code",
            "کد را ارسال کنید یا آن را حذف کنید.": "Send the code or remove it.",
            "حذف کد": "Remove code",
            "سفارش با موفقیت ثبت شد": "Order submitted successfully",
            "وضعیت سفارش تغییر کرد": "Order status changed",
            "وضعیت جدید": "New status",
            "سفارش": "Order",
            "شماره سفارش": "Order number",
            "در انتظار بررسی": "Pending review",
            "تأیید شده": "Approved",
            "در حال انجام": "Processing",
            "تکمیل شده": "Completed",
            "لغو شده": "Cancelled",
            "سفارش‌های من": "My orders",
            "برای مشاهده جزئیات، یک سفارش را انتخاب کنید.": "Select an order to view its details.",
            "هنوز سفارشی ثبت نکرده‌اید.": "You have not submitted any orders yet.",
            "اطلاعات ارسال‌شده": "Submitted information",
            "تاریخچه وضعیت": "Status history",
            "دعوت دوستان": "Invite friends",
            "لینک اختصاصی شما": "Your referral link",
            "تعداد دعوت‌ها": "Invited users",
            "پاداش دریافت‌شده": "Rewards received",
            "پاداش هر دعوت موفق": "Reward per successful referral",
            "پشتیبانی": "Support",
            "تیکت موردنظر را انتخاب کنید.": "Select a support ticket.",
            "هنوز تیکتی ثبت نکرده‌اید.": "You have not submitted any tickets yet.",
            "تیکت جدید": "New ticket",
            "موضوع کوتاه تیکت را ارسال کنید.": "Send a short ticket subject.",
            "حالا متن کامل درخواست یا مشکل را ارسال کنید.": "Now send the full details of your request or problem.",
            "تیکت ثبت شد": "Ticket submitted",
            "توسط پشتیبانی بسته شد.": "was closed by support.",
            "تیکت‌ها": "Tickets",
            "پاسخ داده شده": "Answered",
            "موضوع": "Subject",
            "شما": "You",
            "حساب کاربری": "Profile",
            "شناسه تلگرام": "Telegram ID",
            "کد دعوت": "Referral code",
            "راهنما و قوانین خرید": "Purchase Guide & Rules",
            "بازگشت به منوی اصلی": "Back to main menu",
            "منوی اصلی": "Main menu",
            "دسته‌بندی‌ها": "Categories",
            "سفارش‌ها": "Orders",
            "بازگشت": "Back",
            "قبلی": "Previous",
            "بعدی": "Next",
            "لغو و بازگشت": "Cancel and go back",
            "لغو": "Cancel",
            "مشاهده سفارش": "View order",
            "بررسی عضویت": "Check membership",
            "عضویت در کانال‌ها الزامی است": "Channel membership is required",
            "عضویت در": "Join",
            "نام": "Name",
            "موجودی": "Balance",
            "ثبت": "Created",
            "وضعیت": "Status",
            "محصول": "Product",
            "تعداد": "Quantity",
            "مبلغ": "Amount",
            "قیمت": "Price",
            "شماره": "Number",
            "روش": "Method",
            "کاربر": "User",
            "شروع": "Start",
            "تخفیف": "Discount",
            "نمونه": "Example",
            "مثال": "Example",
            "ارسال رسید": "Send receipt",
            "ارز": "Asset",
            "شبکه": "Network",
            "آدرس": "Address",
            "تتر": "USDT",
            "نرخ": "Rate",
            "معادل اعلام‌شده": "Quoted amount",
            "ثابت": "Fixed",
            "برای": "for",
            "عدد": "units",
            "مضرب": "multiple of",
            "بسته": "Closed",
            "باز": "Open",
            "کیف پول": "Wallet",
            "فروشگاه": "Shop",
            "تومان": "Toman",
            "فارسی": "Persian",
            "انگلیسی": "English",
            "تغییر زبان": "Change language",
            "ارسال برای همه": "Send to everyone",
            "انصراف": "Cancel",
            "بله، حذف شود": "Yes, delete",
            "تخفیف‌ها": "Discounts",
            "تنظیمات": "Settings",
            "روش‌های شارژ": "Top-up methods",
            "فعال/غیرفعال ارز": "Enable/disable crypto",
            "فعال/غیرفعال کارت": "Enable/disable card",
            "مبلغ ثابت": "Fixed amount",
            "مدیریت کانال‌ها": "Channel management",
            "مشاهده ماژول": "View module",
            "مشاهده محصول": "View product",
            "مشاهده کاربر": "View user",
            "مشاهده": "View",
            "درخواست‌ها": "Requests",
            "دسته‌های محصولات": "Product categories",
            "ماژول‌ها": "Modules",
            "محصولات این دسته": "Products in this category",
            "مدیران": "Admins",
            "مدیریت محصولات": "Product management",
            "پاسخ به تیکت": "Reply to ticket",
            "پنل مدیریت": "Admin panel",
            "کاربران": "Users",
            "کانال‌ها": "Channels",
            "غیرفعال‌ها": "Inactive",
            "غیرفعال‌سازی": "Disable",
            "تأیید و افزایش موجودی": "Approve and credit wallet",
            "رد درخواست": "Reject request",
            "ارسال پیام": "Send message",
            "پیام به مشتری": "Message customer",
            "متن دکمه": "Button text",
            "افزودن دسته": "Add category",
            "افزودن محصول": "Add product",
            "افزودن مدیر": "Add admin",
            "افزودن کانال": "Add channel",
            "افزودن/ویرایش ارز": "Add/edit crypto",
            "افزودن/ویرایش کارت": "Add/edit card",
            "کد تخفیف جدید": "New discount code",
            "کاهش موجودی": "Debit wallet",
            "بالاتر": "Move up",
            "پایین‌تر": "Move down",
            "مدیریت تیکت‌ها": "Ticket management",
            "خروج از مدیریت": "Exit admin",
            "مدیریت": "Admin",
            "درآمد": "Revenue",
            "تنظیمات شارژ دستی": "Manual top-up settings",
            "شارژهای دستی": "Manual top-ups",
            "ورودی سفارش": "Order input",
            "توضیحات": "Description",
            "متن بخش": "Section text",
            "پیام همگانی": "Broadcast",
            "قفل عضویت": "Membership lock",
            "مدیریت سفارش‌ها": "Order management",
            "جستجوی محصول": "Search products",
            "جستجوی کاربر": "Search users",
            "بستن تیکت": "Close ticket",
            "عکس": "Photo",
            "انتقال به دسته دیگر": "Move to another category",
            "حذف دسته": "Delete category",
            "حذف محصول": "Delete product",
            "حذف کانال": "Delete channel",
            "حذف": "Delete",
            "ایموجی": "Emoji",
            "مدیران و دسترسی‌ها": "Admins & permissions",
            "فعال‌ها": "Active",
            "مدیریت ماژول‌ها": "Module management",
            "درصدی": "Percentage",
            "محصولات": "Products",
            "فعال‌سازی": "Enable",
            "غیرفعال‌کردن قفل": "Disable membership lock",
            "فعال‌کردن قفل": "Enable membership lock",
            "غیرفعال": "Inactive",
            "فعال": "Active",
            "نام فروشگاه": "Shop name",
            "متن خوش‌آمد": "Welcome text",
            "نام کاربری پشتیبانی": "Support username",
            "پاداش دعوت": "Referral reward",
            "حالت تعمیرات": "Maintenance mode",
            "کارت‌به‌کارت فعال": "Card transfer enabled",
            "شماره کارت": "Card number",
            "نام صاحب کارت": "Cardholder name",
            "متن راهنمای کارت": "Card instructions",
            "ارز دیجیتال فعال": "Crypto enabled",
            "شبکه ارز دیجیتال": "Crypto network",
            "آدرس ارز دیجیتال": "Crypto address",
            "متن راهنمای ارز دیجیتال": "Crypto instructions",
            "تنظیمات فروشگاه": "Shop settings",
            "مرکز کنترل فروشگاه دیجیتال": "Digital shop control center",
            "سفارش جدید": "New orders",
            "تیکت باز": "Open tickets",
            "محصول فعال": "Active products",
            "کل کاربران": "Total users",
            "ماه اخیر": "this month",
            "درآمد کل": "Total revenue",
            "درآمد ۳۰ روز": "30-day revenue",
            "پنل اپراتور": "Operator panel",
            "سفارش‌های در انتظار بررسی": "Orders pending review",
            "پنل پشتیبانی": "Support panel",
            "تیکت‌های نیازمند رسیدگی": "Tickets requiring attention",
            "انتخاب زبان": "Choose language",
            "زبان ربات با موفقیت تغییر کرد.": "Bot language changed successfully.",
            "زبان موردنظر را انتخاب کنید:": "Choose your preferred language:",
            "سلام {first_name} 👋": "Hello {first_name} 👋",
            "از دکمه پایین می‌توانید زبان ربات را تغییر دهید.": "Use the button below to change the bot language.",
            "روش پرداخت نامعتبر است.": "Invalid payment method.",
            "ابتدا مبلغ شارژ را وارد کنید.": "Enter the top-up amount first.",
            "واریز کارت در حال حاضر غیرفعال است.": "Card transfer is currently disabled.",
            "واریز ارز دیجیتال در حال حاضر غیرفعال است.": "Crypto transfer is currently disabled.",
            "مبلغ معتبر و بزرگ‌تر از صفر ارسال کنید؛ نمونه: <code>250000</code>": "Send a valid amount greater than zero; example: <code>250000</code>",
            "در حال حاضر روش شارژ دستی فعالی تعریف نشده است.": "No manual top-up method is currently available.",
            "ابتدا مبلغی را که می‌خواهید به کیف پول اضافه شود، به تومان و فقط به صورت عدد ارسال کنید.": "First send the amount you want to add to your wallet in Toman, using digits only.",
            "برای افزایش موجودی، مبلغ": "To top up your wallet, transfer",
            "را به شماره‌ی حساب زیر واریز کنید": "to the account below",
            "هش یا شناسه تراکنش": "Send the transaction hash or ID for",
            "روی شبکه": "on the network",
            "را ارسال کنید.": "Send it.",
            "این محصول تعداد متغیر ندارد؛ دوباره آن را انتخاب کنید.": "This product has a fixed quantity. Please select it again.",
            "تعداد دلخواه را بین": "Enter a quantity between",
            "وارد کنید.": "Enter it.",
            "عدد باید مضربی از": "The quantity must be a multiple of",
            "باشد.": ".",
            "لطفاً تعداد درست را دوباره ارسال کنید.": "Please send a valid quantity again.",
            "</b> تا <b>": "</b> to <b>",
            "عملیات لغو شد.": "Operation cancelled.",
            "دسترسی غیرمجاز.": "Access denied.",
            "خطای موقت رخ داد؛ دوباره تلاش کنید.": "A temporary error occurred. Please try again.",
            "خطای موقت رخ داد؛ لطفاً دوباره تلاش کنید.": "A temporary error occurred. Please try again.",
            "کمی آهسته‌تر لطفاً…": "Please slow down…",
            "درخواست‌ها خیلی سریع ارسال شدند؛ چند ثانیه صبر کنید.": "Too many requests. Please wait a few seconds.",
            "دسترسی شما به فروشگاه محدود شده است.": "Your access to the shop is restricted.",
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def translate_text(value: str | None, language: str | None = None) -> str | None:
    if value is None or not is_english(language):
        return value
    translated = value
    for source, target in PHRASES_EN:
        if re.fullmatch(r"[\u0600-\u06ff]+", source):
            translated = re.sub(
                rf"(?<![\u0600-\u06ff\u200c]){re.escape(source)}(?![\u0600-\u06ff\u200c])",
                target,
                translated,
            )
        else:
            translated = translated.replace(source, target)
    return translated


def _localized_markup(markup):
    if not isinstance(markup, (InlineKeyboardMarkup, ReplyKeyboardMarkup)):
        return markup
    localized = deepcopy(markup)
    rows = (
        localized.inline_keyboard
        if isinstance(localized, InlineKeyboardMarkup)
        else localized.keyboard
    )
    for row in rows:
        for item in row:
            item.text = translate_text(item.text, "en") or item.text
    if isinstance(localized, ReplyKeyboardMarkup) and localized.input_field_placeholder:
        localized.input_field_placeholder = translate_text(localized.input_field_placeholder, "en")
    return localized


class LocalizationMiddleware(BaseRequestMiddleware):
    """Translate customer-bound Bot API requests using the persisted user language."""

    async def __call__(self, make_request, bot: Bot, method: TelegramMethod):
        if current_language() != "en":
            return await make_request(bot, method)
        target = getattr(method, "chat_id", None)
        current_user = _telegram_id.get()
        if target is not None and current_user is not None and str(target) != str(current_user):
            return await make_request(bot, method)
        if isinstance(method, (SendMessage, EditMessageText)):
            method.text = translate_text(method.text, "en") or method.text
        elif isinstance(method, (SendPhoto, SendDocument, EditMessageCaption)):
            method.caption = translate_text(method.caption, "en")
        elif isinstance(method, AnswerCallbackQuery):
            method.text = translate_text(method.text, "en")
        if hasattr(method, "reply_markup") and method.reply_markup is not None:
            method.reply_markup = _localized_markup(method.reply_markup)
        return await make_request(bot, method)
