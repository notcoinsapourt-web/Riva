from unittest.mock import AsyncMock

import pytest

from bot.config import AppSettings
from bot.database.bootstrap import seed_database
from bot.modules.admin import settings as settings_module


@pytest.mark.asyncio
async def test_settings_button_renders_settings_page(database, monkeypatch) -> None:
    await seed_database(
        database.session_factory,
        AppSettings(bot_token="123456:TEST", admin_ids=()),
    )
    render = AsyncMock()
    monkeypatch.setattr(settings_module, "edit_or_send", render)
    async with database.session_factory() as session:
        await settings_module.settings_list(object(), session)
    render.assert_awaited_once()
    assert "تنظیمات فروشگاه" in render.await_args.args[1]


@pytest.mark.asyncio
async def test_wallet_settings_has_guided_add_buttons(database, monkeypatch) -> None:
    await seed_database(
        database.session_factory,
        AppSettings(bot_token="123456:TEST", admin_ids=()),
    )
    render = AsyncMock()
    monkeypatch.setattr(settings_module, "edit_or_send", render)
    async with database.session_factory() as session:
        await settings_module.wallet_settings(object(), session)
    markup = render.await_args.kwargs["reply_markup"]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "➕ افزودن/ویرایش کارت" in labels
    assert "➕ افزودن/ویرایش ارز" in labels
