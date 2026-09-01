from datetime import UTC, datetime

from aiogram.enums import ChatType, MessageEntityType
from aiogram.types import Chat, InlineKeyboardMarkup, Message, MessageEntity

from bot.core.callbacks import AdminCallback, CatalogCallback, ModuleCallback
from bot.core.emojis import PREMIUM_EMOJIS, extract_custom_emoji_id, keyboard_without_premium
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


def test_premium_emoji_id_is_extracted_from_admin_message() -> None:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=6743306652, type=ChatType.PRIVATE),
        text="⭐",
        entities=[
            MessageEntity(
                type=MessageEntityType.CUSTOM_EMOJI,
                offset=0,
                length=1,
                custom_emoji_id="5368324170671202286",
            )
        ],
    )

    assert extract_custom_emoji_id(message) == "5368324170671202286"


def test_premium_icon_is_separate_and_has_unicode_fallback(monkeypatch) -> None:
    monkeypatch.setitem(PREMIUM_EMOJIS, "home", "5368324170671202286")
    item = button("🏠 منوی اصلی", callback_data="n:home")
    assert item.text == "\u200fمنوی اصلی"
    assert item.icon_custom_emoji_id == "5368324170671202286"

    fallback = keyboard_without_premium(InlineKeyboardMarkup(inline_keyboard=[[item]]))
    assert fallback.inline_keyboard[0][0].text == "🏠 منوی اصلی"
    assert fallback.inline_keyboard[0][0].icon_custom_emoji_id is None


def test_persistent_home_keyboard_is_full_width_and_persistent() -> None:
    markup = persistent_home_keyboard()
    assert [[item.text for item in row] for row in markup.keyboard] == [["🏠 منو"]]
    assert markup.resize_keyboard is True
    assert markup.is_persistent is True


def test_english_catalog_and_persian_fallback_are_ready() -> None:
    i18n = I18n()
    assert i18n.text("menu.catalog", "en") == "Shop"
    assert i18n.text("menu.catalog", "unknown") == "فروشگاه"
