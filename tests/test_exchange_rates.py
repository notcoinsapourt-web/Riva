from decimal import Decimal

import pytest

from bot.core.exceptions import ValidationError
from bot.services.exchange_rates import (
    calculate_usdt_amount,
    parse_nobitex_rate,
    parse_wallex_rate,
)


def test_nobitex_rial_rate_is_converted_to_toman() -> None:
    payload = {"stats": {"usdt-rls": {"latest": "2088990"}}}

    assert parse_nobitex_rate(payload) == Decimal("208899")


def test_wallex_toman_rate_is_read_from_usdt_market() -> None:
    payload = {"result": {"symbols": {"USDTTMN": {"stats": {"lastPrice": "209150"}}}}}

    assert parse_wallex_rate(payload) == Decimal("209150")


def test_toman_amount_is_rounded_up_to_two_usdt_decimals() -> None:
    assert calculate_usdt_amount(2_000_000, Decimal("208899")) == Decimal("9.58")


def test_invalid_exchange_rate_is_rejected() -> None:
    with pytest.raises(ValidationError):
        calculate_usdt_amount(100_000, Decimal("0"))
