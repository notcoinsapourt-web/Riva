from __future__ import annotations

import secrets
from datetime import UTC, datetime

from aiogram.types import User as TelegramUser
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.core.language import normalize_language
from bot.database.models import Admin, Referral, User, Wallet


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_user(self, telegram_user: TelegramUser) -> User:
        statement = (
            select(User)
            .options(selectinload(User.wallet), selectinload(User.admin))
            .where(User.telegram_id == telegram_user.id)
        )
        user = await self.session.scalar(statement)
        if user is None:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name or "کاربر",
                last_name=telegram_user.last_name,
                # The shop must always open in Persian on a user's very first start.
                # Telegram's client language must not silently opt a new user into English.
                language_code="fa",
                referral_code=await self._new_referral_code(),
                last_seen_at=datetime.now(UTC),
            )
            user.wallet = Wallet(balance=0)
            self.session.add(user)
        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name or user.first_name
            user.last_name = telegram_user.last_name
            user.last_seen_at = datetime.now(UTC)
            if user.wallet is None:
                user.wallet = Wallet(balance=0)
        await self.session.commit()
        return user

    async def apply_referral(self, user: User, referral_code: str | None) -> bool:
        code = (referral_code or "").strip().upper()
        if not code or user.referred_by_id is not None:
            return False
        referrer = await self.session.scalar(
            select(User).where(func.upper(User.referral_code) == code)
        )
        if referrer is None or referrer.id == user.id:
            return False
        existing = await self.session.scalar(
            select(Referral.id).where(Referral.referred_id == user.id)
        )
        if existing is not None:
            return False
        user.referred_by_id = referrer.id
        self.session.add(Referral(referrer_id=referrer.id, referred_id=user.id))
        await self.session.commit()
        return True

    async def get_by_telegram_id(self, telegram_id: int) -> User:
        user = await self.session.scalar(
            select(User)
            .options(selectinload(User.wallet), selectinload(User.admin))
            .where(User.telegram_id == telegram_id)
        )
        if user is None:
            raise NotFoundError("کاربر پیدا نشد.")
        return user

    async def get_by_id(self, user_id: int) -> User:
        user = await self.session.scalar(
            select(User)
            .options(selectinload(User.wallet), selectinload(User.admin))
            .where(User.id == user_id)
        )
        if user is None:
            raise NotFoundError("کاربر پیدا نشد.")
        return user

    async def search(self, query: str, limit: int = 20) -> list[User]:
        query = query.strip()
        clauses = [User.username.ilike(f"%{query}%"), User.first_name.ilike(f"%{query}%")]
        if query.isdigit():
            clauses.extend([User.telegram_id == int(query), User.id == int(query)])
        result = await self.session.scalars(
            select(User)
            .options(selectinload(User.wallet))
            .where(or_(*clauses))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def set_blocked(self, user_id: int, blocked: bool) -> User:
        user = await self.get_by_id(user_id)
        if user.admin and blocked:
            raise ValidationError("حساب مدیر را نمی‌توان مسدود کرد.")
        user.is_blocked = blocked
        await self.session.commit()
        return user

    async def set_language(self, user_id: int, language: str) -> User:
        user = await self.get_by_id(user_id)
        user.language_code = normalize_language(language)
        await self.session.commit()
        return user

    async def active_telegram_ids(self) -> list[int]:
        result = await self.session.scalars(
            select(User.telegram_id).where(User.is_active.is_(True), User.is_blocked.is_(False))
        )
        return list(result.all())

    async def is_admin(self, user_id: int) -> bool:
        return (
            await self.session.scalar(
                select(Admin.id).where(Admin.user_id == user_id, Admin.is_active.is_(True))
            )
        ) is not None

    async def _new_referral_code(self) -> str:
        while True:
            code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:9].upper()
            if not await self.session.scalar(select(User.id).where(User.referral_code == code)):
                return code
