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
        items: dict[str, InlineKeyboardButton] = {}
        for module in modules:
            action = MODULE_ACTIONS.get(module.name)
            if action is None:
                continue
            label = (
                module.menu_text or module.display_name
                if module.custom_emoji_id
                else " ".join(part for part in (module.emoji, module.menu_text) if part)
            )
            if module.name == "catalog" and not module.custom_emoji_id:
                label = f"💎 خدمات مجازی | {module.menu_text or module.display_name}"
            items[module.name] = button(
                label,
                callback_data=NavCallback(action=action).pack(),
                custom_emoji_id=module.custom_emoji_id,
                style=(
                    "danger"
                    if module.name == "catalog"
                    else "success"
                    if module.name in {"wallet", "tickets"}
                    else "primary"
                ),
            )

        rows: list[list[InlineKeyboardButton]] = []
        catalog = items.pop("catalog", None)
        if catalog:
            rows.append([catalog])

        first_pair = [items.pop(name) for name in ("orders", "referral") if name in items]
        if first_pair:
            rows.append(first_pair)

        rows.append(
            [
                button(
                    "👤 حساب کاربری",
                    callback_data=NavCallback(action="profile").pack(),
                    style="primary",
                ),
                button(
                    "📄 راهنما و قوانین",
                    callback_data=NavCallback(action="rules").pack(),
                    style="primary",
                ),
            ]
        )

        bottom_pair: list[InlineKeyboardButton] = []
        for name in ("wallet", "tickets"):
            item = items.pop(name, None)
            if item:
                bottom_pair.append(item)
        if bottom_pair:
            rows.append(bottom_pair)

        remaining = list(items.values())
        rows.extend(remaining[index : index + 2] for index in range(0, len(remaining), 2))
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
