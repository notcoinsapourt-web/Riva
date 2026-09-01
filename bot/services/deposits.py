from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.enums import DepositMethod, DepositStatus, TransactionType
from bot.database.models import ManualDeposit
from bot.services.wallet import WalletService


class DepositService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        method: DepositMethod,
        amount: int,
        proof_file_id: str,
        proof_file_type: str,
        transaction_hash: str | None = None,
    ) -> ManualDeposit:
        if amount <= 0:
            raise ValidationError("مبلغ شارژ باید بیشتر از صفر باشد.")
        request = ManualDeposit(
            number=f"DP-{datetime.now(UTC):%y%m%d}-{secrets.token_hex(3).upper()}",
            user_id=user_id,
            method=method,
            amount=amount,
            proof_file_id=proof_file_id,
            proof_file_type=proof_file_type,
            transaction_hash=(transaction_hash or "").strip()[:256] or None,
        )
        self.session.add(request)
        await self.session.commit()
        return await self.get(request.id)

    async def get(self, request_id: int, *, lock: bool = False) -> ManualDeposit:
        statement = (
            select(ManualDeposit)
            .where(ManualDeposit.id == request_id)
            .options(selectinload(ManualDeposit.user))
        )
        if lock:
            statement = statement.with_for_update()
        request = await self.session.scalar(statement)
        if request is None:
            raise NotFoundError("درخواست شارژ پیدا نشد.")
        return request

    async def pending(self, limit: int = 30) -> list[ManualDeposit]:
        return list(
            (
                await self.session.scalars(
                    select(ManualDeposit)
                    .where(ManualDeposit.status == DepositStatus.PENDING)
                    .options(selectinload(ManualDeposit.user))
                    .order_by(ManualDeposit.created_at.asc())
                    .limit(limit)
                )
            ).all()
        )

    async def approve(self, request_id: int, reviewer_user_id: int) -> ManualDeposit:
        request = await self.get(request_id, lock=True)
        if request.status == DepositStatus.APPROVED:
            return request
        if request.status != DepositStatus.PENDING:
            raise ValidationError("این درخواست قبلاً بررسی شده است.")
        await WalletService(self.session).adjust(
            user_id=request.user_id,
            amount=request.amount,
            transaction_type=TransactionType.DEPOSIT,
            description=f"شارژ دستی تأییدشده {request.number}",
            idempotency_key=f"manual-deposit:{request.id}",
            reference_type="manual_deposit",
            reference_id=str(request.id),
            commit=False,
        )
        request.status = DepositStatus.APPROVED
        request.reviewed_by_user_id = reviewer_user_id
        request.reviewed_at = datetime.now(UTC)
        await self.session.commit()
        return request

    async def reject(self, request_id: int, reviewer_user_id: int) -> ManualDeposit:
        request = await self.get(request_id, lock=True)
        if request.status != DepositStatus.PENDING:
            raise ValidationError("این درخواست قبلاً بررسی شده است.")
        request.status = DepositStatus.REJECTED
        request.reviewed_by_user_id = reviewer_user_id
        request.reviewed_at = datetime.now(UTC)
        await self.session.commit()
        return request
