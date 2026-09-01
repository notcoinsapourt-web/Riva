from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, CopyTextButton, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import DepositCallback, NavCallback
from bot.core.exceptions import ValidationError
from bot.core.formatting import dt, h, money
from bot.core.states import WalletDepositState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import DepositMethod
from bot.database.models import User
from bot.services.deposits import DepositService
from bot.services.exchange_rates import ExchangeRateService
from bot.services.notifications import NotificationService
from bot.services.settings import SettingsService
from bot.services.users import UserService
from bot.services.wallet import WalletService

router = Router(name="wallet")


@router.callback_query(NavCallback.filter(F.action == "wallet"))
async def wallet_home(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    settings = SettingsService(session)
    await settings.require_module("wallet")
    user = await UserService(session).get_by_id(db_user.id)
    custom_text = await settings.module_content("wallet")
    await edit_or_send(
        callback,
        "<b>💰 کیف پول</b>\n\n"
        f"موجودی قابل استفاده:\n<b>{money(user.wallet.balance)}</b>\n\n"
        + (custom_text + "\n\n" if custom_text else "")
        + "پرداخت سفارش‌ها به‌صورت آنی و امن از موجودی انجام می‌شود.",
        reply_markup=keyboard(
            [
                button(
                    "➕ افزایش موجودی",
                    callback_data=NavCallback(action="topup").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "🧾 تاریخچه تراکنش‌ها", callback_data=NavCallback(action="transactions").pack()
                )
            ],
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
        ),
    )


@router.callback_query(NavCallback.filter(F.action == "topup"))
async def topup(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    settings = SettingsService(session)
    card = await settings.get_bool("wallet_card_enabled") and bool(
        await settings.get("wallet_card_number")
    )
    crypto = await settings.get_bool("wallet_crypto_enabled") and bool(
        await settings.get("wallet_crypto_address")
    )
    if card or crypto:
        await state.set_state(WalletDepositState.amount)
    await edit_or_send(
        callback,
        "<b>➕ افزایش موجودی</b>\n\n"
        + (
            "ابتدا مبلغی را که می‌خواهید به کیف پول اضافه شود، به تومان و فقط به "
            "صورت عدد ارسال کنید.\n\nمثال: <code>250000</code>"
            if card or crypto
            else "در حال حاضر روش شارژ دستی فعالی تعریف نشده است."
        ),
        reply_markup=keyboard(
            [button("↩️ کیف پول", callback_data=NavCallback(action="wallet").pack())]
        ),
    )


@router.callback_query(DepositCallback.filter(F.action == "start"))
async def deposit_start(
    callback: CallbackQuery,
    callback_data: DepositCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        method = DepositMethod(callback_data.method)
    except ValueError as exc:
        raise ValidationError("روش پرداخت نامعتبر است.") from exc
    settings = SettingsService(session)
    data = await state.get_data()
    amount = int(data.get("amount", 0))
    if amount <= 0:
        await callback.answer("ابتدا مبلغ شارژ را وارد کنید.", show_alert=True)
        await topup(callback, session, state)
        return
    if method == DepositMethod.CARD:
        card_number = await settings.get("wallet_card_number")
        if not await settings.get_bool("wallet_card_enabled") or not card_number:
            raise ValidationError("واریز کارت در حال حاضر غیرفعال است.")
        destination = (
            f"برای افزایش موجودی، مبلغ <b>{money(amount)}</b> را به شماره کارت زیر "
            "واریز کنید 👇\n\n"
            "<code>━━━━━━━━━━━━━━━━</code>\n"
            f"<code>{h(card_number)}</code>\n"
            f"<b>{h(await settings.get('wallet_card_holder', '—'))}</b>\n"
            "<code>━━━━━━━━━━━━━━━━</code>\n\n"
            f"{await settings.get('wallet_card_text')}"
        )
        destination_value = card_number
        copy_label = "📋 کپی شماره کارت"
        copy_amount_value = str(amount)
        copy_amount_label = "📋 کپی مبلغ"
        quote_expires_at = datetime.now(UTC).timestamp() + 3600
        state_values: dict[str, object] = {}
    else:
        crypto_address = await settings.get("wallet_crypto_address")
        if not await settings.get_bool("wallet_crypto_enabled") or not crypto_address:
            raise ValidationError("واریز ارز دیجیتال در حال حاضر غیرفعال است.")
        quote = await ExchangeRateService().usdt_toman(amount)
        network = await settings.get("wallet_crypto_network", "BEP20")
        local_time = quote.fetched_at.astimezone(ZoneInfo("Asia/Tehran")).strftime("%H:%M:%S")
        destination = (
            f"مبلغ شارژ درخواستی: <b>{money(amount)}</b>\n\n"
            f"مبلغ قابل پرداخت: <b>{quote.usdt_text} USDT</b>\n"
            f"نرخ لحظه‌ای هر تتر: <b>{money(int(quote.rate_toman))}</b>\n"
            f"زمان محاسبه: <b>{local_time}</b> به وقت تهران\n"
            f"منبع نرخ: <b>{h(quote.source)}</b>\n\n"
            "ارز: <b>USDT</b>\n"
            f"شبکه: <b>{h(network)}</b>\n"
            f"آدرس: <code>{h(crypto_address)}</code>\n\n"
            f"{await settings.get('wallet_crypto_text')}\n\n"
            "⏱ این نرخ و مقدار USDT تا ۱۵ دقیقه معتبر است. مبلغ را دقیقاً مطابق "
            "عدد بالا ارسال کنید."
        )
        destination_value = crypto_address
        copy_label = "📋 کپی آدرس کیف پول"
        copy_amount_value = quote.usdt_text
        copy_amount_label = "📋 کپی مبلغ USDT"
        quote_expires_at = datetime.now(UTC).timestamp() + 900
        state_values = {
            "crypto_amount": quote.usdt_text,
            "crypto_rate_toman": str(quote.rate_toman),
            "crypto_rate_source": quote.source,
            "crypto_network": network,
        }
    await state.update_data(
        deposit_method=method.value,
        quote_expires_at=quote_expires_at,
        **state_values,
    )
    await state.set_state(WalletDepositState.confirming)
    await edit_or_send(
        callback,
        f"<b>💳 اطلاعات پرداخت</b>\n\n{destination}\n\n"
        "پس از پرداخت، دکمه زیر را بزنید و رسید را ارسال کنید. موجودی فقط پس از "
        "بررسی و تأیید مدیریت افزایش می‌یابد.",
        reply_markup=keyboard(
            [
                InlineKeyboardButton(
                    text=copy_amount_label,
                    copy_text=CopyTextButton(text=copy_amount_value),
                ),
                InlineKeyboardButton(
                    text=copy_label,
                    copy_text=CopyTextButton(text=destination_value),
                ),
            ],
            [
                button(
                    "✅ پرداخت کردم | ارسال رسید",
                    callback_data=DepositCallback(action="paid", method=method.value).pack(),
                    style="success",
                )
            ],
            [
                button(
                    "لغو و بازگشت",
                    callback_data=NavCallback(action="topup").pack(),
                    style="danger",
                )
            ],
        ),
    )


@router.message(WalletDepositState.amount, F.text)
async def deposit_amount(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = message.text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace(",", "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("مبلغ معتبر و بزرگ‌تر از صفر ارسال کنید؛ نمونه: <code>250000</code>")
        return
    amount = int(raw)
    await state.update_data(amount=amount)
    settings = SettingsService(session)
    rows = []
    if await settings.get_bool("wallet_card_enabled") and await settings.get("wallet_card_number"):
        rows.append(
            [
                button(
                    "💳 کارت‌به‌کارت",
                    callback_data=DepositCallback(action="start", method="card").pack(),
                    style="success",
                )
            ]
        )
    if await settings.get_bool("wallet_crypto_enabled") and await settings.get(
        "wallet_crypto_address"
    ):
        network = await settings.get("wallet_crypto_network", "BEP20")
        rows.append(
            [
                button(
                    f"₮ تتر USDT ({network})",
                    callback_data=DepositCallback(action="start", method="crypto").pack(),
                    style="success",
                )
            ]
        )
    rows.append([button("لغو", callback_data=NavCallback(action="wallet").pack(), style="danger")])
    await message.answer(
        f"<b>مبلغ شارژ: {money(amount)}</b>\n\nروش پرداخت را انتخاب کنید:",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(DepositCallback.filter(F.action == "paid"))
async def deposit_paid(
    callback: CallbackQuery,
    callback_data: DepositCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    if int(data.get("amount", 0)) <= 0 or data.get("deposit_method") != callback_data.method:
        await callback.answer("اطلاعات پرداخت منقضی شده است؛ دوباره شروع کنید.", show_alert=True)
        return
    if datetime.now(UTC).timestamp() > float(data.get("quote_expires_at", 0)):
        await state.clear()
        await edit_or_send(
            callback,
            "<b>⏱ مهلت پرداخت تمام شد</b>\n\n"
            "برای دریافت اطلاعات و نرخ تازه، افزایش موجودی را دوباره شروع کنید.",
            reply_markup=keyboard(
                [
                    button(
                        "➕ شروع دوباره",
                        callback_data=NavCallback(action="topup").pack(),
                        style="success",
                    )
                ]
            ),
        )
        return
    if callback_data.method == DepositMethod.CRYPTO.value:
        await state.set_state(WalletDepositState.transaction_hash)
        await edit_or_send(
            callback,
            "<b>🔗 هش تراکنش</b>\n\n"
            f"هش یا شناسه تراکنش <b>{h(data.get('crypto_amount'))} USDT</b> روی شبکه "
            f"<b>{h(data.get('crypto_network', 'BEP20'))}</b> را ارسال کنید.",
            reply_markup=keyboard(
                [button("لغو", callback_data=NavCallback(action="wallet").pack(), style="danger")]
            ),
        )
    else:
        await state.set_state(WalletDepositState.proof)
        await edit_or_send(
            callback,
            "<b>🧾 ارسال رسید</b>\n\n"
            "اکنون تصویر واضح فیش کارت‌به‌کارت را به صورت عکس یا فایل ارسال کنید.",
            reply_markup=keyboard(
                [button("لغو", callback_data=NavCallback(action="wallet").pack(), style="danger")]
            ),
        )


@router.message(WalletDepositState.transaction_hash, F.text)
async def deposit_hash(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if len(value) < 6:
        await message.answer("هش تراکنش معتبر نیست؛ دوباره ارسال کنید.")
        return
    await state.update_data(transaction_hash=value[:256])
    await state.set_state(WalletDepositState.proof)
    await message.answer("اکنون تصویر رسید تراکنش را به صورت عکس یا فایل ارسال کنید.")


@router.message(WalletDepositState.proof, F.photo | F.document)
async def deposit_proof(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
    bot: Bot,
) -> None:
    data = await state.get_data()
    if message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, file_type = message.document.file_id, "document"
    else:
        return
    request = await DepositService(session).create(
        user_id=db_user.id,
        method=DepositMethod(data["deposit_method"]),
        amount=int(data["amount"]),
        proof_file_id=file_id,
        proof_file_type=file_type,
        transaction_hash=data.get("transaction_hash"),
    )
    await state.clear()
    await NotificationService(session, bot).notify_admins(
        f"<b>💳 درخواست شارژ جدید</b>\n\n"
        f"شماره: <code>{request.number}</code>\n"
        f"مبلغ: <b>{money(request.amount)}</b>\n"
        f"کاربر: <code>{db_user.telegram_id}</code>"
        + (
            f"\nمعادل اعلام‌شده: <b>{h(data.get('crypto_amount'))} USDT</b>"
            f"\nنرخ: <b>{h(data.get('crypto_rate_toman'))} تومان</b>"
            if data.get("deposit_method") == DepositMethod.CRYPTO.value
            else ""
        )
        + "\n\n"
        "از پنل مدیریت ← شارژهای دستی بررسی کنید."
    )
    await message.answer(
        f"✅ فیش شما با شماره <code>{request.number}</code> ثبت شد. "
        "پس از بررسی مدیر نتیجه اطلاع داده می‌شود.",
        reply_markup=keyboard(
            [button("💰 کیف پول", callback_data=NavCallback(action="wallet").pack())]
        ),
    )


@router.message(WalletDepositState.proof)
async def invalid_proof(message: Message) -> None:
    await message.answer("لطفاً تصویر فیش را به صورت عکس یا فایل ارسال کنید.")


@router.callback_query(NavCallback.filter(F.action == "transactions"))
async def transactions(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    items = await WalletService(session).history(db_user.id)
    lines = []
    for item in items:
        sign = "+" if item.amount > 0 else "−"
        lines.append(
            f"<b>{sign} {money(abs(item.amount))}</b>\n"
            f"{h(item.description)} • {dt(item.created_at)}"
        )
    await edit_or_send(
        callback,
        "<b>🧾 تاریخچه تراکنش‌ها</b>\n\n" + ("\n\n".join(lines) if lines else "تراکنشی وجود ندارد."),
        reply_markup=keyboard(
            [button("↩️ کیف پول", callback_data=NavCallback(action="wallet").pack())]
        ),
    )
