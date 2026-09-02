from bot.core.ui import button, keyboard


def test_premium_button_stays_on_standard_telegram_markup() -> None:
    markup = keyboard(
        [
            button(
                "✈️ خدمات تلگرام",
                callback_data="catalog:telegram",
                custom_emoji_id="5368324170671202286",
                style="primary",
            )
        ]
    )

    item = markup.inline_keyboard[0][0]
    assert item.icon_custom_emoji_id == "5368324170671202286"
    assert item.style == "primary"
    assert "خدمات تلگرام" in item.text


def test_premium_product_icon_does_not_hide_admin_status() -> None:
    markup = keyboard(
        [
            button(
                "🧠 🟢 ChatGPT Plus | 1,300,000 تومان",
                callback_data="a:products:detail:1:0",
                custom_emoji_id="5368324170671202286",
            )
        ]
    )

    item = markup.inline_keyboard[0][0]

    assert item.icon_custom_emoji_id == "5368324170671202286"
    assert "🟢" in item.text
