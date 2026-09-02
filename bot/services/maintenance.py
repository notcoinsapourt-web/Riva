from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Admin
from bot.services.settings import SettingsService

MAINTENANCE_SETTING = "maintenance_mode"


def maintenance_notice(language_code: str | None) -> str:
    if (language_code or "").lower().startswith("en"):
        return (
            "⛔ The bot is temporarily unavailable for users.\n"
            "Please try again later."
        )
    return (
        "⛔ ربات موقتاً برای کاربران غیرفعال شده است.\n"
        "لطفاً کمی بعد دوباره تلاش کنید."
    )


class MaintenanceModeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)

    async def is_enabled(self) -> bool:
        return await self.settings.get_bool(MAINTENANCE_SETTING, False)

    async def set_enabled(self, enabled: bool) -> bool:
        await self.settings.set(
            MAINTENANCE_SETTING,
            enabled,
            value_type="bool",
            description="خاموش کردن سراسری ربات برای کاربران عادی",
        )
        return enabled

    async def toggle(self) -> bool:
        return await self.set_enabled(not await self.is_enabled())

    async def can_bypass(self, user_id: int) -> bool:
        admin_id = await self.session.scalar(
            select(Admin.id).where(
                Admin.user_id == user_id,
                Admin.is_active.is_(True),
            )
        )
        return admin_id is not None
