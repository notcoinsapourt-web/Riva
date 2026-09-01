from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal, InvalidOperation

import aiohttp

from bot.core.exceptions import ValidationError

NOBITEX_MARKET_URL = "https://api.nobitex.ir/market/stats"
WALLEX_MARKETS_URL = "https://api.wallex.ir/v1/markets"


@dataclass(frozen=True, slots=True)
class UsdtQuote:
    toman_amount: int
    rate_toman: Decimal
    usdt_amount: Decimal
    source: str
    fetched_at: datetime

    @property
    def usdt_text(self) -> str:
        return format(self.usdt_amount, "f")


def calculate_usdt_amount(toman_amount: int, rate_toman: Decimal) -> Decimal:
    if toman_amount <= 0 or rate_toman <= 0:
        raise ValidationError("مبلغ یا نرخ تبدیل معتبر نیست.")
    return (Decimal(toman_amount) / rate_toman).quantize(Decimal("0.01"), rounding=ROUND_UP)


def parse_nobitex_rate(payload: object) -> Decimal:
    try:
        market = payload["stats"]["usdt-rls"]  # type: ignore[index]
        raw = market.get("latest") or market.get("bestSell")
        rial_rate = Decimal(str(raw))
        rate = rial_rate / Decimal(10)
    except (AttributeError, KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("Invalid Nobitex response") from exc
    if rate <= 0:
        raise ValueError("Invalid Nobitex rate")
    return rate


def parse_wallex_rate(payload: object) -> Decimal:
    try:
        result = payload["result"]  # type: ignore[index]
        symbols = result.get("symbols") or result.get("markets")
        market = symbols.get("USDTTMN") or symbols.get("USDTIRT")
        stats = market.get("stats", market)
        raw = stats.get("lastPrice") or stats.get("last_price") or stats.get("bidPrice")
        rate = Decimal(str(raw))
    except (AttributeError, KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("Invalid Wallex response") from exc
    if rate <= 0:
        raise ValueError("Invalid Wallex rate")
    return rate


class ExchangeRateService:
    async def usdt_toman(self, toman_amount: int) -> UsdtQuote:
        timeout = aiohttp.ClientTimeout(total=8, connect=4)
        headers = {"Accept": "application/json", "User-Agent": "PersianShopBot/1.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as client:
            providers = (
                (
                    "نوبیتکس",
                    NOBITEX_MARKET_URL,
                    {"srcCurrency": "usdt", "dstCurrency": "rls"},
                    parse_nobitex_rate,
                ),
                ("والکس", WALLEX_MARKETS_URL, None, parse_wallex_rate),
            )
            for source, url, params, parser in providers:
                try:
                    async with client.get(url, params=params) as response:
                        response.raise_for_status()
                        rate = parser(await response.json())
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    continue
                return UsdtQuote(
                    toman_amount=toman_amount,
                    rate_toman=rate,
                    usdt_amount=calculate_usdt_amount(toman_amount, rate),
                    source=source,
                    fetched_at=datetime.now(UTC),
                )
        raise ValidationError(
            "دریافت نرخ لحظه‌ای تتر ممکن نشد. برای جلوگیری از محاسبه اشتباه، "
            "پرداخت ارزی ثبت نشد؛ چند دقیقه دیگر دوباره تلاش کنید."
        )
