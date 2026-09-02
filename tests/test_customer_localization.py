from __future__ import annotations

from bot.core.customer_localization import (
    WELCOME_EN,
    contains_persian,
    english_rules_from_persian,
    strict_button_english,
)
from bot.core.ui import persistent_language_keyboard


def test_english_language_keyboard_is_persistent() -> None:
    markup = persistent_language_keyboard("en")
    assert markup.is_persistent is True
    assert markup.resize_keyboard is True
    assert markup.keyboard[0][0].text == "🌐 Change language"


def test_mixed_product_button_is_cleaned_to_english() -> None:
    label = strict_button_english("👥 Followers اقتصادی")
    assert "Economy" in label
    assert not contains_persian(label)


def test_faq_is_translated_without_persian_fragments() -> None:
    source = (
        "<b>❓ سوالات متداول</b>\n\n"
        "• قبل از خرید، توضیحات محصول را کامل بخوانید.\n"
        "• فقط لینک عمومی و اطلاعات خواسته‌شده را ارسال کنید.\n"
        "• رمز عبور، کد ورود و اطلاعات بانکی را برای ربات نفرستید.\n"
        "• قیمت نهایی پیش از پرداخت نمایش داده می‌شود.\n"
        "• وضعیت سفارش و پاسخ پشتیبانی از همین ربات اعلام می‌شود."
    )
    translated = english_rules_from_persian(source)
    assert "Frequently Asked Questions" in translated
    assert not contains_persian(translated)


def test_corrected_english_welcome_is_not_stale_or_mixed() -> None:
    assert "Arvan Coin" in WELCOME_EN
    assert "premium accounts" in WELCOME_EN
    assert "Choose the service you need" in WELCOME_EN
    assert not contains_persian(WELCOME_EN)
