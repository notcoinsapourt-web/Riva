from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.database.web_models import WebDeposit, WebWallet, WebWalletTransaction
from bot.modules.admin.common import protected_router

router = protected_router("web_store_deposit_fix")


@router.callback_query(AdminCallback.filter((F.section == "web") & F.action.in_({"da", "dr"})))
async def review_web_deposit_fixed(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
) -> None:
    deposit = await session.scalar(
        select(WebDeposit)
        .where(WebDeposit.id == callback_data.entity_id)
        .with_for_update()
    )
    if not deposit:
        await callback.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if deposit.status != "pending":
        await callback.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
        return

    now = datetime.now(timezone.utc)

    if callback_data.action == "da":
        wallet = await session.scalar(
            select(WebWallet)
            .where(WebWallet.user_id == deposit.user_id)
            .with_for_update()
        )
        if wallet is None:
            wallet = WebWallet(
                user_id=deposit.user_id,
                balance=0,
                created_at=now,
                updated_at=now,
            )
            session.add(wallet)
            await session.flush()

        idempotency_key = f"web-deposit:{deposit.id}"
        existing_tx = await session.scalar(
            select(WebWalletTransaction.id).where(
                WebWalletTransaction.idempotency_key == idempotency_key
            )
        )

        if existing_tx is None:
            before = int(wallet.balance)
            after = before + int(deposit.amount)
            wallet.balance = after
            wallet.updated_at = now
            session.add(
                WebWalletTransaction(
                    wallet_id=wallet.id,
                    transaction_type="deposit",
                    amount=deposit.amount,
                    balance_before=before,
                    balance_after=after,
                    description=f"تأیید شارژ {deposit.number}",
                    reference_type="web_deposit",
                    reference_id=str(deposit.id),
                    idempotency_key=idempotency_key,
                    created_at=now,
                )
            )

        deposit.status = "approved"
        result_text = "رسید تأیید شد و موجودی کیف پول کاربر افزایش یافت."
    else:
        deposit.status = "rejected"
        result_text = "درخواست شارژ رد شد."

    deposit.reviewed_by_telegram_id = callback.from_user.id
    deposit.reviewed_at = now

    # The web-store handler previously only flushed the session. The bot's
    # database middleware does not auto-commit, so the approval and wallet
    # balance were rolled back when the callback finished. Commit explicitly.
    await session.commit()

    await callback.answer(result_text, show_alert=True)

    # Refresh the same deposit card after the committed state is visible.
    from bot.modules.admin.web_store import show_deposit

    await show_deposit(callback, int(deposit.id), session)
