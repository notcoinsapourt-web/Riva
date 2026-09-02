from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback
from bot.core.i18n import I18n
from bot.core.language import is_english
from bot.core.ui import button
from bot.services.settings import SettingsService

MODULE_ACTIONS = {
    "catalog": "catalog",
    "orders": "orders",
    "wallet": "wallet",
    "referral": "referral",
    "tickets": "tickets",
    "profile": "profile",
    "rules": "rules",
}

MODULE_I18N_KEYS = {
    "catalog": "menu.catalog",
    "orders": "menu.orders",
    "wallet": "menu.wallet",
    "referral": "menu.referral",
    "tickets": "menu.tickets",
    "profile": "menu.profile",
    "rules": "menu.rules",
}


class MenuService:
    def __init__(self, session: AsyncSession) -> None:
        self.settings = SettingsService(session)

    async def main(self, *, is_admin: bool = False, language: str = "fa") -> InlineKeyboardMarkup:
        modules = await self.settings.enabled_modules(menu_only=True)
        i18n = I18n()
        items: dict[str, InlineKeyboardButton] = {}
        for module in modules:
            action = MODULE_ACTIONS.get(module.name)
            if action is None:
                continue
            configured_label = module.menu_text or module.display_name
            translated_label = i18n.text(MODULE_I18N_KEYS.get(module.name, ""), language)
            menu_label = translated_label if is_english(language) else configured_label
            label = " ".join(part for part in (module.emoji, menu_label) if part)
            if module.name == "catalog":
                label = (
                    f"💎 Digital Services | {menu_label}"
                    if is_english(language)
                    else f"💎 خدمات مجازی | {configured_label}"
                )
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

        account_pair = [items.pop(name) for name in ("profile", "rules") if name in items]
        if account_pair:
            rows.append(account_pair)

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
