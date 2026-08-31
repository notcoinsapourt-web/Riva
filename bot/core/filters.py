from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.enums import UserRole
from bot.database.models import Admin, User


class IsAdmin(BaseFilter):
    async def __call__(
        self, event: Message | CallbackQuery, session: AsyncSession, **_: object
    ) -> bool:
        if event.from_user is None:
            return False
        statement = (
            select(Admin.id)
            .join(User, User.id == Admin.user_id)
            .where(
                User.telegram_id == event.from_user.id,
                User.is_blocked.is_(False),
                Admin.is_active.is_(True),
            )
        )
        return (await session.scalar(statement)) is not None


class IsOwner(BaseFilter):
    async def __call__(
        self, event: Message | CallbackQuery, session: AsyncSession, **_: object
    ) -> bool:
        if event.from_user is None:
            return False
        statement = (
            select(Admin.id)
            .join(User, User.id == Admin.user_id)
            .where(
                User.telegram_id == event.from_user.id,
                Admin.role == UserRole.OWNER,
                Admin.is_active.is_(True),
            )
        )
        return (await session.scalar(statement)) is not None


class HasAdminRole(BaseFilter):
    def __init__(self, *roles: UserRole) -> None:
        self.roles = roles

    async def __call__(
        self, event: Message | CallbackQuery, session: AsyncSession, **_: object
    ) -> bool:
        if event.from_user is None:
            return False
        statement = (
            select(Admin.id)
            .join(User, User.id == Admin.user_id)
            .where(
                User.telegram_id == event.from_user.id,
                Admin.role.in_(self.roles),
                Admin.is_active.is_(True),
            )
        )
        return (await session.scalar(statement)) is not None
