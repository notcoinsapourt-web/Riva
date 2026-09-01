from types import SimpleNamespace

import pytest

from bot.core.exceptions import ValidationError
from bot.services.product_presentation import (
    display_name,
    order_requirements,
    parse_quantity,
    quantity_policy,
    subtotal_for,
)


def instagram_product():
    return SimpleNamespace(
        name="۱۰۰۰ فالوور اقتصادی اینستاگرام",
        description="فالوور اقتصادی برای پیج عمومی",
        price=149_000,
        photo_file_id=("https://example.test/instagram-followers-1k-economy.jpg?v=2"),
        input_prompt="لینک عمومی پیج یا پست را ارسال کنید. رمز عبور لازم نیست.",
    )


def test_scalable_product_has_short_name_and_calculated_subtotal() -> None:
    product = instagram_product()
    policy = quantity_policy(product)

    assert policy is not None
    assert policy.base_quantity == 1_000
    assert display_name(product) == "فالوور اقتصادی"
    assert subtotal_for(product, 2_500) == 372_500


def test_quantity_parser_accepts_persian_digits_and_rejects_invalid_values() -> None:
    assert parse_quantity("۲٬۵۰۰") == 2_500
    with pytest.raises(ValidationError):
        parse_quantity("دو هزار")
    with pytest.raises(ValidationError):
        subtotal_for(instagram_product(), 250)


def test_order_requirements_are_specific_and_safe() -> None:
    prompt, safety = order_requirements(instagram_product())
    assert prompt == "نام کاربری یا لینک پیج عمومی اینستاگرام را ارسال کنید."
    assert "رمز عبور" in safety
    assert "کد ورود" in safety


def test_custom_order_prompt_has_priority_over_slug_fallback() -> None:
    product = instagram_product()
    product.input_prompt = "لینک استوری فعال و زمان انتشار را ارسال کنید."

    prompt, _ = order_requirements(product)

    assert prompt == product.input_prompt
