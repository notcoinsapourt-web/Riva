from bot.core.ui import _rich_message_with_buttons, button, keyboard


def test_premium_button_is_embedded_before_persian_label() -> None:
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

    rich = _rich_message_with_buttons("فروشگاه", markup)

    assert rich is not None
    assert rich.is_rtl is True
    assert rich.html is not None
    assert rich.html.index("<tg-emoji") < rich.html.index("خدمات تلگرام")
    assert 'style="primary"' in rich.html
    assert "✈️</tg-emoji>&nbsp;خدمات تلگرام" in rich.html


def test_regular_keyboard_stays_on_standard_path() -> None:
    markup = keyboard([button("🏠 منو", callback_data="home", style="danger")])

    assert _rich_message_with_buttons("فروشگاه", markup) is None
