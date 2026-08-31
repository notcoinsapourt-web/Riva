from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.ui import button
from bot.services.settings import SettingsService

MODULE_ACTIONS = {
    "catalog": "catalog",
    "orders": "orders",
    "wallet": "wallet",
    "referral": "referral",
    "tickets": "tickets",
}


class MenuService:
    def __init__(self, session: AsyncSession) -> None:
        self.settings = SettingsService(session)

    async def main(self, *, is_admin: bool = False) -> InlineKeyboardMarkup:
        modules = await self.settings.enabled_modules(menu_only=True)
        items: list[InlineKeyboardButton] = []
        for module in modules:
            action = MODULE_ACTIONS.get(module.name)
            if action is None:
                continue
            label = (
                module.menu_text or module.display_name
                if module.custom_emoji_id
                else " ".join(part for part in (module.emoji, module.menu_text) if part)
            )
            items.append(
                button(
                    label,
                    callback_data=NavCallback(action=action).pack(),
                    custom_emoji_id=module.custom_emoji_id,
                    style="primary" if module.name == "catalog" else None,
                )
            )
        rows = [items[index : index + 2] for index in range(0, len(items), 2)]
        rows.append(
            [
                button(
                    "👤 حساب کاربری",
                    callback_data=NavCallback(action="profile").pack(),
                )
            ]
        )
        if is_admin:
            rows.append(
                [
                    button(
                        "👑 مدیریت",
                        callback_data=NavCallback(action="admin").pack(),
                        style="success",
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)
