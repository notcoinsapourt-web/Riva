from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import ModuleDisabledError, NotFoundError, ValidationError
from bot.database.models import Module, Setting


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str, default: str = "") -> str:
        value = await self.session.scalar(select(Setting.value).where(Setting.key == key))
        return default if value is None else value

    async def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(await self.get(key, str(default)))
        except ValueError:
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        value = (await self.get(key, str(default))).strip().lower()
        return value in {"1", "true", "yes", "on"}

    async def module_content(self, name: str, default: str = "") -> str:
        return await self.get(f"module_content_{name}", default)

    async def set(
        self,
        key: str,
        value: object,
        *,
        value_type: str = "str",
        description: str | None = None,
        is_public: bool = False,
    ) -> Setting:
        setting = await self.session.scalar(select(Setting).where(Setting.key == key))
        serialized = str(value).lower() if isinstance(value, bool) else str(value)
        if setting is None:
            setting = Setting(
                key=key,
                value=serialized,
                value_type=value_type,
                description=description,
                is_public=is_public,
            )
            self.session.add(setting)
        else:
            setting.value = serialized
            setting.value_type = value_type
            if description is not None:
                setting.description = description
        await self.session.commit()
        return setting

    async def list_settings(self) -> list[Setting]:
        return list((await self.session.scalars(select(Setting).order_by(Setting.key))).all())

    async def modules(self, *, menu_only: bool = False) -> list[Module]:
        statement = select(Module).order_by(Module.sort_order, Module.id)
        if menu_only:
            statement = statement.where(Module.menu_text.is_not(None))
        return list((await self.session.scalars(statement)).all())

    async def enabled_modules(self, *, menu_only: bool = False) -> list[Module]:
        statement = (
            select(Module).where(Module.is_enabled.is_(True)).order_by(Module.sort_order, Module.id)
        )
        if menu_only:
            statement = statement.where(Module.menu_text.is_not(None))
        return list((await self.session.scalars(statement)).all())

    async def module_enabled(self, name: str) -> bool:
        return bool(await self.session.scalar(select(Module.is_enabled).where(Module.name == name)))

    async def require_module(self, name: str) -> None:
        if not await self.module_enabled(name):
            raise ModuleDisabledError("این بخش در حال حاضر غیرفعال است.")

    async def toggle_module(self, name: str) -> Module:
        module = await self._module(name)
        if module.is_core and module.is_enabled:
            raise ValidationError("ماژول‌های اصلی قابل غیرفعال‌سازی نیستند.")
        module.is_enabled = not module.is_enabled
        await self.session.commit()
        return module

    async def move_module(self, name: str, direction: int) -> Module:
        module = await self._module(name)
        modules = await self.modules(menu_only=True)
        index = next((i for i, item in enumerate(modules) if item.name == name), -1)
        target_index = index + direction
        if index < 0 or target_index < 0 or target_index >= len(modules):
            return module
        other = modules[target_index]
        module.sort_order, other.sort_order = other.sort_order, module.sort_order
        await self.session.commit()
        return module

    async def update_module_ui(
        self,
        name: str,
        *,
        menu_text: str | None = None,
        emoji: str | None = None,
        custom_emoji_id: str | None = None,
    ) -> Module:
        module = await self._module(name)
        if menu_text is not None:
            module.menu_text = menu_text.strip()[:80]
        if emoji is not None:
            module.emoji = emoji.strip()[:32] or None
        if custom_emoji_id is not None:
            module.custom_emoji_id = custom_emoji_id.strip()[:64] or None
        await self.session.commit()
        return module

    async def _module(self, name: str) -> Module:
        module = await self.session.scalar(select(Module).where(Module.name == name))
        if module is None:
            raise NotFoundError("ماژول پیدا نشد.")
        return module
