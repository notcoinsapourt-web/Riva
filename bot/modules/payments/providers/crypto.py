from __future__ import annotations

from bot.core.exceptions import ValidationError
from bot.modules.payments.providers.base import GatewayInvoice, GatewayVerification, PaymentProvider


class ManualUSDTProvider(PaymentProvider):
    """Manual USDT invoice provider; chain monitoring can be plugged in later."""

    def __init__(self, network: str, address: str) -> None:
        self.network = network.upper()
        self.address = address
        self.name = f"usdt_{network.lower()}"

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        amount_toman: int,
        description: str,
        callback_url: str,
    ) -> GatewayInvoice:
        if not self.address:
            raise ValidationError("آدرس کیف پول این شبکه تنظیم نشده است.")
        return GatewayInvoice(
            authority=invoice_number,
            destination=self.address,
            metadata={"network": self.network, "manual_confirmation": True},
        )

    async def verify(
        self,
        *,
        authority: str,
        amount_toman: int,
        invoice_number: str | None = None,
    ) -> GatewayVerification:
        return GatewayVerification(
            paid=False,
            metadata={"manual_confirmation": True, "network": self.network},
        )
