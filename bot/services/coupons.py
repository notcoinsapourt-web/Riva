from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.enums import CouponType
from bot.database.models import Coupon, CouponRedemption


class CouponService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate(self, code: str, *, user_id: int, subtotal: int) -> tuple[Coupon, int]:
        coupon = await self.session.scalar(
            select(Coupon).where(func.upper(Coupon.code) == code.strip().upper())
        )
        if coupon is None or not coupon.is_active:
            raise NotFoundError("کد تخفیف معتبر نیست.")
        if coupon.expires_at and _is_past(coupon.expires_at):
            raise ValidationError("تاریخ این کد تخفیف گذشته است.")
        if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
            raise ValidationError("ظرفیت استفاده از این کد تکمیل شده است.")
        if subtotal < coupon.min_order_amount:
            raise ValidationError("مبلغ سفارش برای استفاده از این کد کافی نیست.")
        used_by_user = await self.session.scalar(
            select(func.count(CouponRedemption.id)).where(
                CouponRedemption.coupon_id == coupon.id,
                CouponRedemption.user_id == user_id,
            )
        )
        if used_by_user >= coupon.per_user_limit:
            raise ValidationError("سقف استفاده شما از این کد تکمیل شده است.")
        discount = self.calculate(coupon, subtotal)
        return coupon, discount

    @staticmethod
    def calculate(coupon: Coupon, subtotal: int) -> int:
        if coupon.coupon_type == CouponType.PERCENT:
            discount = subtotal * coupon.value // 100
        else:
            discount = coupon.value
        if coupon.max_discount is not None:
            discount = min(discount, coupon.max_discount)
        return max(0, min(discount, subtotal))

    async def create(
        self,
        *,
        code: str,
        coupon_type: CouponType,
        value: int,
        max_uses: int | None,
        expires_at: datetime | None,
    ) -> Coupon:
        normalized = code.strip().upper()
        if not normalized or value <= 0:
            raise ValidationError("کد و مقدار تخفیف باید معتبر باشند.")
        if coupon_type == CouponType.PERCENT and value > 100:
            raise ValidationError("درصد تخفیف نمی‌تواند بیشتر از ۱۰۰ باشد.")
        if await self.session.scalar(select(Coupon.id).where(Coupon.code == normalized)):
            raise ValidationError("این کد قبلاً ساخته شده است.")
        coupon = Coupon(
            code=normalized,
            coupon_type=coupon_type,
            value=value,
            max_uses=max_uses,
            expires_at=expires_at,
        )
        self.session.add(coupon)
        await self.session.commit()
        return coupon

    async def list(self) -> list[Coupon]:
        return list(
            (await self.session.scalars(select(Coupon).order_by(Coupon.created_at.desc()))).all()
        )

    async def toggle(self, coupon_id: int) -> Coupon:
        coupon = await self.session.get(Coupon, coupon_id)
        if coupon is None:
            raise NotFoundError("کد تخفیف پیدا نشد.")
        coupon.is_active = not coupon.is_active
        await self.session.commit()
        return coupon

    async def delete(self, coupon_id: int) -> None:
        coupon = await self.session.get(Coupon, coupon_id)
        if coupon is None:
            raise NotFoundError("کد تخفیف پیدا نشد.")
        redemptions = await self.session.scalar(
            select(func.count(CouponRedemption.id)).where(CouponRedemption.coupon_id == coupon_id)
        )
        if redemptions:
            coupon.is_active = False
        else:
            await self.session.delete(coupon)
        await self.session.commit()


def _is_past(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= datetime.now(UTC)
