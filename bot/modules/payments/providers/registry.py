from __future__ import annotations

from bot.config import AppSettings
from bot.core.exceptions import NotFoundError, PaymentDisabledError
from bot.modules.payments.providers.base import PaymentProvider
from bot.modules.payments.providers.crypto import ManualUSDTProvider
from bot.modules.payments.providers.iranian import IDPayProvider, ZarinpalProvider


class PaymentProviderRegistry:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._providers: dict[str, PaymentProvider] = {}
        if settings.zarinpal_merchant_id:
            self._providers["zarinpal"] = ZarinpalProvider(
                settings.zarinpal_merchant_id.get_secret_value()
            )
        if settings.idpay_api_key:
            self._providers["idpay"] = IDPayProvider(
                settings.idpay_api_key.get_secret_value(), sandbox=settings.idpay_sandbox
            )
        if settings.usdt_trc20_address:
            self._providers["usdt_trc20"] = ManualUSDTProvider("TRC20", settings.usdt_trc20_address)
        if settings.usdt_bep20_address:
            self._providers["usdt_bep20"] = ManualUSDTProvider("BEP20", settings.usdt_bep20_address)

    def get(self, name: str) -> PaymentProvider:
        if not self.settings.payments_live:
            raise PaymentDisabledError("پرداخت آنلاین فعلاً غیرفعال است.")
        provider = self._providers.get(name)
        if provider is None:
            raise NotFoundError("درگاه انتخاب‌شده تنظیم نشده است.")
        return provider

    @property
    def available(self) -> tuple[str, ...]:
        if not self.settings.payments_live:
            return ()
        return tuple(self._providers)
