from bot.core.callbacks import AdminCallback, CatalogCallback, ModuleCallback
from bot.core.i18n import I18n
from bot.core.ui import button, persistent_home_keyboard


def test_callback_payloads_fit_telegram_limit() -> None:
    payloads = [
        AdminCallback(section="products", action="edit_description", entity_id=999999).pack(),
        CatalogCallback(action="category", entity_id=999999, page=100).pack(),
        ModuleCallback(action="edit_custom", name="notifications").pack(),
    ]
    assert all(len(item.encode()) <= 64 for item in payloads)


def test_premium_button_fields_are_supported() -> None:
    item = button(
        "فروشگاه",
        callback_data="n:catalog",
        custom_emoji_id="5368324170671202286",
        style="primary",
    )
    assert item.icon_custom_emoji_id == "5368324170671202286"
    assert item.style == "primary"


def test_invalid_custom_emoji_is_ignored() -> None:
    item = button("فروشگاه", callback_data="n:catalog", custom_emoji_id="none")
    assert item.icon_custom_emoji_id is None


def test_persistent_home_keyboard_is_full_width_and_persistent() -> None:
    markup = persistent_home_keyboard()
    assert [[item.text for item in row] for row in markup.keyboard] == [["🏠 منو"]]
    assert markup.resize_keyboard is True
    assert markup.is_persistent is True


def test_english_catalog_and_persian_fallback_are_ready() -> None:
    i18n = I18n()
    assert i18n.text("menu.catalog", "en") == "Shop"
    assert i18n.text("menu.catalog", "unknown") == "فروشگاه"
