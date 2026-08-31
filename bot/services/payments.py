from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import AppSettings
from bot.core.exceptions import NotFoundError, PaymentDisabledError, ValidationError
from bot.database.enums import PaymentStatus, TransactionType
from bot.database.models import Payment
from bot.modules.payments.providers.registry import PaymentProviderRegistry
from bot.services.wallet import WalletService


class PaymentService:
    """Payment orchestration. Locked unless two environment switches are enabled."""

    def __init__(self, session: AsyncSession, settings: AppSettings) -> None:
        self.session = session
        self.settings = settings
        self.registry = PaymentProviderRegistry(settings)

    async def create_invoice(
        self,
        *,
        user_id: int,
        amount: int,
        provider_name: str,
        description: str,
        order_id: int | None = None,
    ) -> tuple[Payment, str | None]:
        if not self.settings.payments_live:
            raise PaymentDisabledError("پرداخت آنلاین فعلاً غیرفعال است.")
        if amount <= 0:
            raise ValidationError("مبلغ فاکتور باید بیشتر از صفر باشد.")
        provider = self.registry.get(provider_name)
        number = f"INV-{datetime.now(UTC):%y%m%d}-{secrets.token_hex(3).upper()}"
        payment = Payment(
            invoice_number=number,
            user_id=user_id,
            order_id=order_id,
            provider=provider_name,
            amount=amount,
            status=PaymentStatus.CREATED,
            expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        self.session.add(payment)
        await self.session.commit()
        try:
            callback = (
                f"{self.settings.payment_callback_base_url.rstrip('/')}/payments/{provider_name}"
            )
            invoice = await provider.create_invoice(
                invoice_number=number,
                amount_toman=amount,
                description=description,
                callback_url=callback,
            )
            payment.authority = invoice.authority
            payment.destination = invoice.destination
            payment.metadata_json = invoice.metadata
            payment.status = PaymentStatus.PENDING
            await self.session.commit()
            return payment, invoice.payment_url
        except Exception:
            payment.status = PaymentStatus.FAILED
            await self.session.commit()
            raise

    async def get(self, invoice_number: str) -> Payment:
        payment = await self.session.scalar(
            select(Payment).where(Payment.invoice_number == invoice_number)
        )
        if payment is None:
            raise NotFoundError("فاکتور پیدا نشد.")
        return payment

    async def verify(self, invoice_number: str) -> Payment:
        if not self.settings.payments_live:
            raise PaymentDisabledError("پرداخت آنلاین فعلاً غیرفعال است.")
        payment = await self.get(invoice_number)
        if payment.status == PaymentStatus.PAID:
            return payment
        if not payment.authority:
            raise ValidationError("شناسه درگاه برای این فاکتور ثبت نشده است.")
        provider = self.registry.get(payment.provider)
        await self.session.commit()
        verification = await provider.verify(
            authority=payment.authority,
            amount_toman=payment.amount,
            invoice_number=payment.invoice_number,
        )
        payment.metadata_json = {**payment.metadata_json, **verification.metadata}
        if not verification.paid:
            payment.status = PaymentStatus.FAILED
            await self.session.commit()
            return payment
        payment.status = PaymentStatus.PAID
        payment.paid_at = datetime.now(UTC)
        if payment.order_id is None:
            await WalletService(self.session).adjust(
                user_id=payment.user_id,
                amount=payment.amount,
                transaction_type=TransactionType.DEPOSIT,
                description=f"شارژ کیف پول با فاکتور {payment.invoice_number}",
                idempotency_key=f"payment-deposit:{payment.id}",
                reference_type="payment",
                reference_id=str(payment.id),
                commit=False,
            )
        await self.session.commit()
        return payment
