from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message, ReactionTypeEmoji
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.customer_localization import WELCOME_EN, english_rules_from_persian
from bot.core.formatting import h, money
from bot.core.language import (
    is_english,
    reset_current_language,
    set_current_language,
)
from bot.core.ui import button, edit_or_send, keyboard, persistent_language_keyboard
from bot.database.models import User
from bot.services.channels import ChannelService
from bot.services.menu import MenuService
from bot.services.settings import SettingsService
from bot.services.users import UserService

router = Router(name="start")


async def _apply_language_keyboard(message: Message, language: str) -> None:
    # Reply keyboards are tied to the message that carries them. Deleting the
    # invisible carrier makes Telegram hide the keyboard on some clients.
    await message.answer(
        "\u2063",
        reply_markup=persistent_language_keyboard(language),
    )


@router.message(CommandStart())
async def start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    await state.clear()
    try:
        await message.react([ReactionTypeEmoji(emoji="⚡")], is_big=True)
    except TelegramAPIError:
        pass
    payload = command.args or ""
    if payload.startswith("ref_"):
        await UserService(session).apply_referral(db_user, payload.removeprefix("ref_"))
    await _apply_language_keyboard(message, db_user.language_code)
    await show_home(message, session=session, user=db_user)


@router.message(Command("menu"))
async def menu_command(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await show_home(message, session=session, user=db_user)


@router.message(F.text.in_({"🌐 تغییر زبان", "🌐 Change language", "🏠 منو"}))
async def language_menu(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await message.answer(
        "<b>🌐 انتخاب زبان</b>\n\nزبان موردنظر را انتخاب کنید:",
        reply_markup=keyboard(
            [
                button(
                    "🇮🇷 فارسی",
                    callback_data=NavCallback(action="lang_fa").pack(),
                    style="primary",
                ),
                button(
                    "🇬🇧 English",
                    callback_data=NavCallback(action="lang_en").pack(),
                    style="primary",
                ),
            ]
        ),
    )


@router.callback_query(NavCallback.filter(F.action.in_({"lang_fa", "lang_en"})))
async def change_language(
    callback: CallbackQuery,
    callback_data: NavCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    language = callback_data.action.removeprefix("lang_")
    user = await UserService(session).set_language(db_user.id, language)
    await state.clear()
    token = set_current_language(language)
    try:
        if isinstance(callback.message, Message):
            await _apply_language_keyboard(callback.message, language)
        await show_home(callback, session=session, user=user)
    finally:
        reset_current_language(token)


@router.message(Command("cancel"))
async def cancel_command(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await message.answer("عملیات لغو شد.")
    await show_home(message, session=session, user=db_user)


@router.callback_query(NavCallback.filter(F.action == "home"))
@router.callback_query(NavCallback.filter(F.action == "verify_join"))
async def home_callback(
    callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await show_home(callback, session=session, user=db_user)


@router.callback_query(NavCallback.filter(F.action == "profile"))
async def profile(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await SettingsService(session).require_module("profile")
    user = await UserService(session).get_by_id(db_user.id)
    currency = await SettingsService(session).get("currency", "تومان")
    custom_intro = (
        ""
        if is_english(db_user.language_code)
        else await SettingsService(session).module_content("profile")
    )
    text = (
        "<b>👤 حساب کاربری</b>\n\n"
        + (custom_intro + "\n\n" if custom_intro else "")
        + f"نام: <b>{h(user.first_name)} {h(user.last_name or '')}</b>\n"
        f"شناسه تلگرام: <code>{user.telegram_id}</code>\n"
        f"موجودی: <b>{money(user.wallet.balance, currency)}</b>\n"
        f"کد دعوت: <code>{user.referral_code}</code>\n\n"
        "اطلاعات حساب به‌صورت خودکار با تلگرام همگام می‌شود."
    )
    await edit_or_send(
        callback,
        text,
        reply_markup=keyboard(
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())]
        ),
    )


@router.callback_query(NavCallback.filter(F.action == "rules"))
async def rules(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    settings = SettingsService(session)
    await settings.require_module("rules")
    default_text = (
        "<b>📄 راهنما و قوانین خرید</b>\n\n"
        "• قبل از خرید، توضیحات محصول را کامل بخوانید.\n"
        "• فقط لینک عمومی و اطلاعات خواسته‌شده را ارسال کنید.\n"
        "• رمز عبور، کد ورود و اطلاعات بانکی را برای ربات نفرستید.\n"
        "• قیمت نهایی پیش از پرداخت نمایش داده می‌شود.\n"
        "• وضعیت سفارش و پاسخ پشتیبانی از همین ربات اعلام می‌شود."
    )
    persian_rules = await settings.module_content("rules", default_text)
    rules_text = (
        english_rules_from_persian(persian_rules)
        if is_english(db_user.language_code)
        else persian_rules
    )
    await edit_or_send(
        callback,
        rules_text,
        reply_markup=keyboard(
            [
                button(
                    "🏠 بازگشت به منوی اصلی",
                    callback_data=NavCallback(action="home").pack(),
                    style="danger",
                )
            ]
        ),
    )


async def show_home(event: Message | CallbackQuery, *, session: AsyncSession, user: User) -> None:
    settings = SettingsService(session)
    currency = await settings.get("currency", "تومان")
    hydrated = await UserService(session).get_by_id(user.id)
    is_admin = await UserService(session).is_admin(user.id)
    if not is_admin:
        missing = await ChannelService(session).missing_for(event.bot, user.telegram_id)
        if missing:
            rows = [
                [InlineKeyboardButton(text=f"📣 عضویت در {channel.title}", url=channel.invite_link)]
                for channel in missing
            ]
            rows.append(
                [
                    button(
                        "✅ بررسی عضویت",
                        callback_data=NavCallback(action="verify_join").pack(),
                        style="success",
                    )
                ]
            )
            await edit_or_send(
                event,
                "<b>🔒 عضویت در کانال‌ها الزامی است</b>\n\n"
                "برای ورود به فروشگاه ابتدا در همه کانال‌های زیر عضو شوید و سپس "
                "«بررسی عضویت» را بزنید.",
                reply_markup=keyboard(*rows),
            )
            return
    welcome = (
        WELCOME_EN
        if is_english(hydrated.language_code)
        else await settings.get("welcome_text", "سلام {first_name} 👋")
    )
    text = (
        welcome.replace("{first_name}", h(hydrated.first_name))
        .replace("{balance}", money(hydrated.wallet.balance, currency))
        .replace("{currency}", h(currency))
    )
    await edit_or_send(
        event,
        text,
        reply_markup=await MenuService(session).main(
            is_admin=is_admin, language=hydrated.language_code
        ),
    )
