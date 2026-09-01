from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.formatting import h, money
from bot.core.ui import button, edit_or_send, keyboard, persistent_home_keyboard
from bot.database.models import User
from bot.services.menu import MenuService
from bot.services.settings import SettingsService
from bot.services.users import UserService

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    await state.clear()
    payload = command.args or ""
    if payload.startswith("ref_"):
        await UserService(session).apply_referral(db_user, payload.removeprefix("ref_"))
    shop_name = await SettingsService(session).get("shop_name", "Persian Shop")
    await message.answer(
        f"🌹 به منوی <b>{h(shop_name)}</b> خوش آمدید.",
        reply_markup=persistent_home_keyboard(),
    )
    await show_home(message, session=session, user=db_user)


@router.message(Command("menu"))
async def menu_command(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await show_home(message, session=session, user=db_user)


@router.message(F.text == "🏠 منو")
async def persistent_menu(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await show_home(message, session=session, user=db_user)


@router.message(Command("cancel"))
async def cancel_command(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    await state.clear()
    await message.answer("عملیات لغو شد.")
    await show_home(message, session=session, user=db_user)


@router.callback_query(NavCallback.filter(F.action == "home"))
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
    text = (
        "<b>👤 حساب کاربری</b>\n\n"
        f"نام: <b>{h(user.first_name)} {h(user.last_name or '')}</b>\n"
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
async def rules(callback: CallbackQuery, session: AsyncSession) -> None:
    await SettingsService(session).require_module("rules")
    await edit_or_send(
        callback,
        "<b>📄 راهنما و قوانین خرید</b>\n\n"
        "• قبل از خرید، توضیحات محصول را کامل بخوانید.\n"
        "• فقط لینک عمومی و اطلاعات خواسته‌شده را ارسال کنید.\n"
        "• رمز عبور، کد ورود و اطلاعات بانکی را برای ربات نفرستید.\n"
        "• قیمت نهایی پیش از پرداخت نمایش داده می‌شود.\n"
        "• وضعیت سفارش و پاسخ پشتیبانی از همین ربات اعلام می‌شود.",
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
    shop_name = await settings.get("shop_name", "Persian Shop")
    welcome = await settings.get("welcome_text", "به فروشگاه دیجیتال خوش آمدید.")
    currency = await settings.get("currency", "تومان")
    hydrated = await UserService(session).get_by_id(user.id)
    is_admin = await UserService(session).is_admin(user.id)
    text = (
        f"<b>✨ {h(shop_name)}</b>\n"
        "<i>Telegram Digital Marketplace</i>\n\n"
        f"{h(welcome)}\n\n"
        f"💰 موجودی کیف پول: <b>{money(hydrated.wallet.balance, currency)}</b>\n"
        "از منوی زیر بخش موردنظر را انتخاب کنید."
    )
    await edit_or_send(
        event,
        text,
        reply_markup=await MenuService(session).main(is_admin=is_admin),
    )
