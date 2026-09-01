from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import DepositCallback, NavCallback
from bot.core.exceptions import ValidationError
from bot.core.formatting import dt, h, money
from bot.core.states import WalletDepositState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import DepositMethod
from bot.database.models import User
from bot.services.deposits import DepositService
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
    rows = []
    if card:
        rows.append(
            [
                button(
                    "💳 واریز کارت به کارت",
                    callback_data=DepositCallback(action="start", method="card").pack(),
                    style="success",
                )
            ]
        )
    if crypto:
        rows.append(
            [
                button(
                    "₿ واریز ارز دیجیتال",
                    callback_data=DepositCallback(action="start", method="crypto").pack(),
                    style="success",
                )
            ]
        )
    rows.append([button("↩️ کیف پول", callback_data=NavCallback(action="wallet").pack())])
    await edit_or_send(
        callback,
        "<b>➕ افزایش موجودی</b>\n\n"
        + (
            "روش واریز را انتخاب کنید. پس از بررسی مدیر، مبلغ به کیف پول افزوده می‌شود."
            if card or crypto
            else "در حال حاضر روش شارژ دستی فعالی تعریف نشده است."
        ),
        reply_markup=keyboard(*rows),
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
    if method == DepositMethod.CARD:
        if not await settings.get_bool("wallet_card_enabled"):
            raise ValidationError("واریز کارت در حال حاضر غیرفعال است.")
        destination = (
            f"شماره کارت: <code>{h(await settings.get('wallet_card_number'))}</code>\n"
            f"به نام: <b>{h(await settings.get('wallet_card_holder', '—'))}</b>\n\n"
            f"{await settings.get('wallet_card_text')}"
        )
    else:
        if not await settings.get_bool("wallet_crypto_enabled"):
            raise ValidationError("واریز ارز دیجیتال در حال حاضر غیرفعال است.")
        destination = (
            f"شبکه: <b>{h(await settings.get('wallet_crypto_network', 'TRC20'))}</b>\n"
            f"آدرس: <code>{h(await settings.get('wallet_crypto_address'))}</code>\n\n"
            f"{await settings.get('wallet_crypto_text')}"
        )
    await state.set_state(WalletDepositState.amount)
    await state.set_data({"deposit_method": method.value})
    await edit_or_send(
        callback,
        f"<b>افزایش موجودی</b>\n\n{destination}\n\n"
        "پس از واریز، مبلغ پرداختی را به تومان و فقط به صورت عدد ارسال کنید.",
        reply_markup=keyboard(
            [button("لغو", callback_data=NavCallback(action="topup").pack(), style="danger")]
        ),
    )


@router.message(WalletDepositState.amount, F.text)
async def deposit_amount(message: Message, state: FSMContext) -> None:
    raw = message.text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace(",", "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("مبلغ معتبر و بزرگ‌تر از صفر ارسال کنید؛ نمونه: <code>250000</code>")
        return
    data = await state.get_data()
    await state.update_data(amount=int(raw))
    if data["deposit_method"] == DepositMethod.CRYPTO.value:
        await state.set_state(WalletDepositState.transaction_hash)
        await message.answer("هش یا شناسه تراکنش ارز دیجیتال را ارسال کنید.")
    else:
        await state.set_state(WalletDepositState.proof)
        await message.answer("اکنون تصویر فیش واریز را به صورت عکس یا فایل ارسال کنید.")


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
        f"کاربر: <code>{db_user.telegram_id}</code>\n\n"
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
