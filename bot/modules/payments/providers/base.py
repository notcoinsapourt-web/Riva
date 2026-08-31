from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GatewayInvoice:
    authority: str
    payment_url: str | None = None
    destination: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GatewayVerification:
    paid: bool
    reference_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_invoice(
        self,
        *,
        invoice_number: str,
        amount_toman: int,
        description: str,
        callback_url: str,
    ) -> GatewayInvoice: ...

    @abstractmethod
    async def verify(
        self,
        *,
        authority: str,
        amount_toman: int,
        invoice_number: str | None = None,
    ) -> GatewayVerification: ...
