from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.formatting import dt, h, money
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.services.settings import SettingsService
from bot.services.users import UserService
from bot.services.wallet import WalletService

router = Router(name="wallet")


@router.callback_query(NavCallback.filter(F.action == "wallet"))
async def wallet_home(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await SettingsService(session).require_module("wallet")
    user = await UserService(session).get_by_id(db_user.id)
    await edit_or_send(
        callback,
        "<b>💰 کیف پول</b>\n\n"
        f"موجودی قابل استفاده:\n<b>{money(user.wallet.balance)}</b>\n\n"
        "پرداخت سفارش‌ها به‌صورت آنی و امن از موجودی انجام می‌شود.",
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
async def topup(callback: CallbackQuery, session: AsyncSession) -> None:
    support = await SettingsService(session).get("support_username", "")
    support_text = f"\n\nپشتیبانی: @{h(support.lstrip('@'))}" if support else ""
    await edit_or_send(
        callback,
        "<b>➕ افزایش موجودی</b>\n\n"
        "درگاه‌های بانکی و USDT در کد پروژه آماده‌اند، اما طبق تنظیم فعلی غیرفعال هستند. "
        "برای شارژ دستی با پشتیبانی تماس بگیرید."
        f"{support_text}",
        reply_markup=keyboard(
            [button("↩️ کیف پول", callback_data=NavCallback(action="wallet").pack())]
        ),
    )


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
