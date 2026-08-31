from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import InsufficientBalanceError, NotFoundError, ValidationError
from bot.database.enums import TransactionType
from bot.database.models import Transaction, Wallet


class WalletService:
    # SQLite ignores SELECT ... FOR UPDATE. Per-user locks keep its single-process
    # edition safe; PostgreSQL additionally enforces the database row lock.
    _locks: ClassVar[defaultdict[tuple[int, int], asyncio.Lock]] = defaultdict(asyncio.Lock)

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, *, lock: bool = False) -> Wallet:
        statement = select(Wallet).where(Wallet.user_id == user_id)
        if lock:
            statement = statement.with_for_update()
        wallet = await self.session.scalar(statement)
        if wallet is None:
            raise NotFoundError("کیف پول پیدا نشد.")
        return wallet

    async def adjust(
        self,
        *,
        user_id: int,
        amount: int,
        transaction_type: TransactionType,
        description: str,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        commit: bool = True,
    ) -> Transaction:
        lock_key = (id(asyncio.get_running_loop()), user_id)
        async with self._locks[lock_key]:
            return await self._adjust_locked(
                user_id=user_id,
                amount=amount,
                transaction_type=transaction_type,
                description=description,
                idempotency_key=idempotency_key,
                reference_type=reference_type,
                reference_id=reference_id,
                commit=commit,
            )

    async def _adjust_locked(
        self,
        *,
        user_id: int,
        amount: int,
        transaction_type: TransactionType,
        description: str,
        idempotency_key: str,
        reference_type: str | None,
        reference_id: str | None,
        commit: bool,
    ) -> Transaction:
        idempotency_key = idempotency_key[:120]
        existing = await self.session.scalar(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        if amount == 0:
            raise ValidationError("مبلغ تراکنش نمی‌تواند صفر باشد.")
        wallet = await self.get(user_id, lock=True)
        before = wallet.balance
        after = before + amount
        if after < 0:
            raise InsufficientBalanceError("موجودی کیف پول برای این خرید کافی نیست.")
        wallet.balance = after
        transaction = Transaction(
            wallet_id=wallet.id,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=before,
            balance_after=after,
            description=description[:300],
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )
        self.session.add(transaction)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return transaction

    async def history(self, user_id: int, limit: int = 20) -> list[Transaction]:
        wallet = await self.get(user_id)
        result = await self.session.scalars(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return list(result.all())
