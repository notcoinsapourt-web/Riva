from __future__ import annotations

from typing import Any

import aiohttp

from bot.core.exceptions import ValidationError
from bot.modules.payments.providers.base import GatewayInvoice, GatewayVerification, PaymentProvider


class ZarinpalProvider(PaymentProvider):
    name = "zarinpal"
    request_url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
    verify_url = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
    start_url = "https://www.zarinpal.com/pg/StartPay/{authority}"

    def __init__(self, merchant_id: str) -> None:
        self.merchant_id = merchant_id

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        amount_toman: int,
        description: str,
        callback_url: str,
    ) -> GatewayInvoice:
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_toman * 10,
            "description": f"{description} ({invoice_number})",
            "callback_url": callback_url,
        }
        result = await _post_json(self.request_url, payload)
        data = result.get("data") or {}
        if data.get("code") != 100 or not data.get("authority"):
            raise ValidationError("درگاه زرین‌پال فاکتور را نپذیرفت.")
        authority = str(data["authority"])
        return GatewayInvoice(
            authority=authority,
            payment_url=self.start_url.format(authority=authority),
            metadata={"gateway_response": result},
        )

    async def verify(
        self,
        *,
        authority: str,
        amount_toman: int,
        invoice_number: str | None = None,
    ) -> GatewayVerification:
        result = await _post_json(
            self.verify_url,
            {
                "merchant_id": self.merchant_id,
                "amount": amount_toman * 10,
                "authority": authority,
            },
        )
        data = result.get("data") or {}
        return GatewayVerification(
            paid=data.get("code") in {100, 101},
            reference_id=str(data.get("ref_id")) if data.get("ref_id") else None,
            metadata={"gateway_response": result},
        )


class IDPayProvider(PaymentProvider):
    name = "idpay"
    request_url = "https://api.idpay.ir/v1.1/payment"
    verify_url = "https://api.idpay.ir/v1.1/payment/verify"

    def __init__(self, api_key: str, *, sandbox: bool = True) -> None:
        self.api_key = api_key
        self.sandbox = sandbox

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "X-SANDBOX": "1" if self.sandbox else "0",
            "Content-Type": "application/json",
        }

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        amount_toman: int,
        description: str,
        callback_url: str,
    ) -> GatewayInvoice:
        result = await _post_json(
            self.request_url,
            {
                "order_id": invoice_number,
                "amount": amount_toman * 10,
                "desc": description,
                "callback": callback_url,
            },
            headers=self.headers,
        )
        if not result.get("id") or not result.get("link"):
            raise ValidationError("درگاه IDPay فاکتور را نپذیرفت.")
        return GatewayInvoice(
            authority=str(result["id"]),
            payment_url=str(result["link"]),
            metadata={"gateway_response": result},
        )

    async def verify(
        self,
        *,
        authority: str,
        amount_toman: int,
        invoice_number: str | None = None,
    ) -> GatewayVerification:
        if not invoice_number:
            raise ValidationError("شماره فاکتور IDPay موجود نیست.")
        result = await _post_json(
            self.verify_url,
            {"id": authority, "order_id": invoice_number},
            headers=self.headers,
        )
        expected_rial = amount_toman * 10
        paid = result.get("status") == 100 and int(result.get("amount", 0)) == expected_rial
        return GatewayVerification(
            paid=paid,
            reference_id=str(result.get("track_id")) if result.get("track_id") else None,
            metadata={"gateway_response": result},
        )


async def _post_json(
    url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.post(url, json=payload, headers=headers) as response:
            try:
                result: dict[str, Any] = await response.json()
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise ValidationError("پاسخ نامعتبر از درگاه پرداخت دریافت شد.") from exc
            if response.status >= 400:
                raise ValidationError("ارتباط با درگاه پرداخت ناموفق بود.")
            return result
