from __future__ import annotations

import asyncio
import secrets
from collections import defaultdict
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.enums import OrderStatus, TransactionType
from bot.database.models import (
    Coupon,
    CouponRedemption,
    Order,
    OrderStatusHistory,
    Product,
    Referral,
    User,
)
from bot.services.coupons import CouponService
from bot.services.settings import SettingsService
from bot.services.wallet import WalletService

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.APPROVED, OrderStatus.CANCELLED},
    OrderStatus.APPROVED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


class OrderService:
    _checkout_locks: ClassVar[defaultdict[tuple[int, int], asyncio.Lock]] = defaultdict(
        asyncio.Lock
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def checkout(
        self,
        *,
        user: User,
        product_id: int,
        customer_input: str,
        checkout_key: str,
        coupon_code: str | None = None,
    ) -> Order:
        lock_key = (id(asyncio.get_running_loop()), user.id)
        async with self._checkout_locks[lock_key]:
            return await self._checkout_locked(
                user=user,
                product_id=product_id,
                customer_input=customer_input,
                checkout_key=checkout_key,
                coupon_code=coupon_code,
            )

    async def _checkout_locked(
        self,
        *,
        user: User,
        product_id: int,
        customer_input: str,
        checkout_key: str,
        coupon_code: str | None,
    ) -> Order:
        existing = await self.session.scalar(
            select(Order).where(Order.checkout_key == checkout_key)
        )
        if existing is not None:
            return existing
        product = await self.session.scalar(
            select(Product).where(Product.id == product_id, Product.is_active.is_(True))
        )
        if product is None:
            raise NotFoundError("محصول پیدا نشد یا غیرفعال شده است.")
        details = customer_input.strip()
        if not details:
            raise ValidationError("اطلاعات سفارش نمی‌تواند خالی باشد.")

        subtotal = product.price
        coupon = None
        discount = 0
        try:
            if coupon_code:
                coupon, discount = await CouponService(self.session).validate(
                    coupon_code, user_id=user.id, subtotal=subtotal
                )
            total = subtotal - discount
            order = Order(
                number=_number("PS"),
                checkout_key=checkout_key[:80],
                user_id=user.id,
                product_id=product.id,
                coupon_id=coupon.id if coupon else None,
                product_name=product.name,
                unit_price=product.price,
                quantity=1,
                subtotal=subtotal,
                discount_amount=discount,
                total_amount=total,
                customer_input=details[:4000],
                status=OrderStatus.PENDING,
            )
            self.session.add(order)
            await self.session.flush()
            if total > 0:
                await WalletService(self.session).adjust(
                    user_id=user.id,
                    amount=-total,
                    transaction_type=TransactionType.PURCHASE,
                    description=f"پرداخت سفارش {order.number}",
                    idempotency_key=f"order-purchase:{order.id}",
                    reference_type="order",
                    reference_id=str(order.id),
                    commit=False,
                )
            if coupon:
                claim = await self.session.execute(
                    update(Coupon)
                    .where(
                        Coupon.id == coupon.id,
                        or_(
                            Coupon.max_uses.is_(None),
                            Coupon.used_count < Coupon.max_uses,
                        ),
                    )
                    .values(used_count=Coupon.used_count + 1)
                    .returning(Coupon.used_count)
                    .execution_options(synchronize_session=False)
                )
                if claim.scalar_one_or_none() is None:
                    raise ValidationError("ظرفیت استفاده از این کد تکمیل شده است.")
                self.session.add(
                    CouponRedemption(
                        coupon_id=coupon.id,
                        user_id=user.id,
                        order_id=order.id,
                        discount_amount=discount,
                    )
                )
            self.session.add(
                OrderStatusHistory(
                    order_id=order.id,
                    from_status=None,
                    to_status=OrderStatus.PENDING,
                    changed_by_user_id=user.id,
                    note="ثبت سفارش توسط مشتری",
                )
            )
            await self.session.commit()
            return order
        except IntegrityError:
            await self.session.rollback()
            duplicate = await self.session.scalar(
                select(Order).where(Order.checkout_key == checkout_key)
            )
            if duplicate is not None:
                return duplicate
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def get(self, order_id: int) -> Order:
        order = await self.session.scalar(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.product),
                selectinload(Order.history),
            )
            .where(Order.id == order_id)
        )
        if order is None:
            raise NotFoundError("سفارش پیدا نشد.")
        return order

    async def user_orders(self, user_id: int, limit: int = 20) -> list[Order]:
        result = await self.session.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def admin_orders(
        self, *, status: OrderStatus | None = None, limit: int = 30
    ) -> list[Order]:
        statement = (
            select(Order).options(selectinload(Order.user)).order_by(Order.created_at.desc())
        )
        if status is not None:
            statement = statement.where(Order.status == status)
        return list((await self.session.scalars(statement.limit(limit))).all())

    async def change_status(
        self,
        *,
        order_id: int,
        new_status: OrderStatus,
        changed_by_user_id: int,
        note: str | None = None,
    ) -> Order:
        order = await self.get(order_id)
        old_status = order.status
        if new_status == old_status:
            return order
        if new_status not in ALLOWED_TRANSITIONS[old_status]:
            raise ValidationError("این تغییر وضعیت مجاز نیست.")
        try:
            order.status = new_status
            if new_status == OrderStatus.CANCELLED:
                order.cancelled_at = datetime.now(UTC)
                if order.total_amount > 0:
                    await WalletService(self.session).adjust(
                        user_id=order.user_id,
                        amount=order.total_amount,
                        transaction_type=TransactionType.REFUND,
                        description=f"بازگشت وجه سفارش {order.number}",
                        idempotency_key=f"order-refund:{order.id}",
                        reference_type="order",
                        reference_id=str(order.id),
                        commit=False,
                    )
            if new_status == OrderStatus.COMPLETED:
                order.completed_at = datetime.now(UTC)
                await self._reward_referral(order)
            self.session.add(
                OrderStatusHistory(
                    order_id=order.id,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by_user_id=changed_by_user_id,
                    note=note,
                )
            )
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise

    async def _reward_referral(self, order: Order) -> None:
        referral = await self.session.scalar(
            select(Referral).where(
                Referral.referred_id == order.user_id,
                Referral.rewarded_at.is_(None),
            )
        )
        if referral is None:
            return
        reward = await SettingsService(self.session).get_int("referral_reward", 0)
        if reward <= 0:
            return
        await WalletService(self.session).adjust(
            user_id=referral.referrer_id,
            amount=reward,
            transaction_type=TransactionType.REFERRAL,
            description="پاداش دعوت دوست پس از اولین خرید موفق",
            idempotency_key=f"referral-reward:{referral.id}",
            reference_type="referral",
            reference_id=str(referral.id),
            commit=False,
        )
        referral.reward_amount = reward
        referral.rewarded_at = datetime.now(UTC)

    async def stats(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        )
        result = {status.value: count for status, count in rows.all()}
        result["revenue"] = (
            await self.session.scalar(
                select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                    Order.status == OrderStatus.COMPLETED
                )
            )
            or 0
        )
        return result


def _number(prefix: str) -> str:
    stamp = datetime.now(UTC).strftime("%y%m%d")
    return f"{prefix}-{stamp}-{secrets.token_hex(3).upper()}"
