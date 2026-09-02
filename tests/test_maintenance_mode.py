from __future__ import annotations

import pytest

from bot.database.enums import UserRole
from bot.database.models import Admin, User
from bot.services.maintenance import MaintenanceModeService, maintenance_notice


@pytest.mark.asyncio
async def test_maintenance_toggle_persists(database) -> None:
    async with database.session_factory() as session:
        service = MaintenanceModeService(session)
        assert await service.is_enabled() is False
        assert await service.toggle() is True
        assert await service.is_enabled() is True
        assert await service.toggle() is False
        assert await service.is_enabled() is False


@pytest.mark.asyncio
async def test_active_admin_can_bypass_maintenance(database) -> None:
    async with database.session_factory() as session:
        user = User(
            telegram_id=123456,
            username="owner",
            first_name="Owner",
            language_code="fa",
            referral_code="OWNER123",
        )
        session.add(user)
        await session.flush()
        session.add(
            Admin(
                user_id=user.id,
                role=UserRole.OWNER,
                permissions={"*": True},
                is_active=True,
            )
        )
        await session.commit()

        service = MaintenanceModeService(session)
        assert await service.can_bypass(user.id) is True


@pytest.mark.asyncio
async def test_inactive_admin_cannot_bypass_maintenance(database) -> None:
    async with database.session_factory() as session:
        user = User(
            telegram_id=654321,
            username="old_admin",
            first_name="Old Admin",
            language_code="fa",
            referral_code="OLDADMIN1",
        )
        session.add(user)
        await session.flush()
        session.add(
            Admin(
                user_id=user.id,
                role=UserRole.ADMIN,
                permissions={},
                is_active=False,
            )
        )
        await session.commit()

        service = MaintenanceModeService(session)
        assert await service.can_bypass(user.id) is False


def test_maintenance_notice_is_bilingual() -> None:
    assert "غیرفعال" in maintenance_notice("fa")
    assert "temporarily unavailable" in maintenance_notice("en")
