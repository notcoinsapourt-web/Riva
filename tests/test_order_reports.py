from __future__ import annotations

from datetime import UTC, datetime

from bot.services.order_reports import (
    OrderReportPayload,
    build_cta_markup,
    build_report_text,
    format_timestamp,
    mask_identifier,
    resolve_report_product_emoji_id,
)


def test_mask_identifier_hides_middle_digits() -> None:
    assert mask_identifier(1234567890) == "12******90"
    assert mask_identifier("09123456789") == "09******89"


def test_report_text_is_product_agnostic_and_escapes_html() -> None:
    text = build_report_text(
        OrderReportPayload(
            buyer="12******90",
            product_name="Instagram <Followers>",
            quantity=2500,
            amount=173_202,
            created_at=datetime(2026, 9, 2, 8, 39, 43, tzinfo=UTC),
            product_emoji="💎",
        ),
        shop_name="Persian <Shop>",
        bot_username="ExampleBot",
        timezone_name="UTC",
        custom_emoji_id=None,
    )
    assert "#خرید_موفق" in text
    assert "Instagram &lt;Followers&gt; × 2,500" in text
    assert "173,202 تومان" in text
    assert "Persian &lt;Shop&gt;" in text
    assert "@ExampleBot" in text


def test_premium_product_icon_and_url_button_are_supported() -> None:
    text = build_report_text(
        OrderReportPayload(
            buyer="12******90",
            product_name="Telegram Premium",
            quantity=1,
            amount=10_000,
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
            product_emoji="💎",
        ),
        shop_name="Shop",
        bot_username="ExampleBot",
        timezone_name="UTC",
        custom_emoji_id="123456789",
    )
    markup = build_cta_markup("ExampleBot", "123456789")
    button = markup.inline_keyboard[0][0]

    assert '<tg-emoji emoji-id="123456789">💎</tg-emoji>' in text
    assert button.url == "https://t.me/ExampleBot"
    assert button.icon_custom_emoji_id == "123456789"
    assert "برای خرید اقدام کن" in button.text


def test_configured_report_product_emoji_overrides_product_default() -> None:
    assert (
        resolve_report_product_emoji_id(
            configured="5294476812221439592",
            product="1111111111111111111",
            contextual="2222222222222222222",
        )
        == "5294476812221439592"
    )
    assert (
        resolve_report_product_emoji_id(
            configured=None,
            product="1111111111111111111",
            contextual="2222222222222222222",
        )
        == "1111111111111111111"
    )


def test_all_report_text_icons_can_be_premium() -> None:
    text = build_report_text(
        OrderReportPayload(
            buyer="12******90",
            product_name="Telegram Premium",
            quantity=1,
            amount=10_000,
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
            product_emoji="💎",
        ),
        shop_name="Shop",
        bot_username="ExampleBot",
        timezone_name="UTC",
        custom_emoji_id="103",
        text_custom_emoji_ids={
            "shop": "101",
            "buyer": "102",
            "amount": "104",
            "time": "105",
            "bot": "106",
        },
    )
    for emoji_id in ("101", "102", "103", "104", "105", "106"):
        assert f'emoji-id="{emoji_id}"' in text


def test_test_report_has_explicit_test_marker() -> None:
    text = build_report_text(
        OrderReportPayload(
            buyer="09******123",
            product_name="Telegram Stars - Test Order",
            quantity=1,
            amount=10_000,
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
            product_emoji="⭐",
            is_test=True,
        ),
        shop_name="Shop",
        bot_username="ExampleBot",
        timezone_name="UTC",
        custom_emoji_id=None,
    )
    assert "#خرید_موفق #تست" in text


def test_format_timestamp_uses_configured_timezone() -> None:
    value = datetime(2026, 9, 2, 8, 30, tzinfo=UTC)
    assert format_timestamp(value, "Asia/Tehran") == "2026/09/02 12:00:00"
