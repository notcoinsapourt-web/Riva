from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.enums import OrderStatus, UserRole
from bot.database.models import Admin, Order, Product, Ticket, User


class AdminDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def metrics(self) -> dict[str, int]:
        since = datetime.now(UTC) - timedelta(days=30)
        users = await self.session.scalar(select(func.count(User.id))) or 0
        new_users = (
            await self.session.scalar(select(func.count(User.id)).where(User.created_at >= since))
            or 0
        )
        active_products = (
            await self.session.scalar(
                select(func.count(Product.id)).where(Product.is_active.is_(True))
            )
            or 0
        )
        pending_orders = (
            await self.session.scalar(
                select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
            )
            or 0
        )
        open_tickets = (
            await self.session.scalar(
                select(func.count(Ticket.id)).where(Ticket.closed_at.is_(None))
            )
            or 0
        )
        revenue = (
            await self.session.scalar(
                select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                    Order.status == OrderStatus.COMPLETED
                )
            )
            or 0
        )
        monthly_revenue = (
            await self.session.scalar(
                select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                    Order.status == OrderStatus.COMPLETED,
                    Order.completed_at >= since,
                )
            )
            or 0
        )
        return {
            "users": users,
            "new_users": new_users,
            "active_products": active_products,
            "pending_orders": pending_orders,
            "open_tickets": open_tickets,
            "revenue": revenue,
            "monthly_revenue": monthly_revenue,
        }


class AdminAccessService:
    ALLOWED_ROLES = {UserRole.OWNER, UserRole.ADMIN, UserRole.OPERATOR, UserRole.SUPPORT}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Admin]:
        result = await self.session.scalars(
            select(Admin).options(selectinload(Admin.user)).order_by(Admin.created_at, Admin.id)
        )
        return list(result.all())

    async def get(self, admin_id: int) -> Admin:
        admin = await self.session.scalar(
            select(Admin).options(selectinload(Admin.user)).where(Admin.id == admin_id)
        )
        if admin is None:
            raise NotFoundError("مدیر پیدا نشد.")
        return admin

    async def add(self, telegram_id: int, role: UserRole) -> Admin:
        if role not in self.ALLOWED_ROLES:
            raise ValidationError("سطح دسترسی معتبر نیست.")
        user = await self.session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            raise NotFoundError("این کاربر باید ابتدا ربات را Start کند.")
        admin = await self.session.scalar(select(Admin).where(Admin.user_id == user.id))
        if admin is None:
            admin = Admin(user_id=user.id, role=role, permissions={}, is_active=True)
            self.session.add(admin)
            await self.session.flush()
        else:
            admin.role = role
            admin.is_active = True
        await self.session.commit()
        return await self.get(admin.id)

    async def set_role(self, admin_id: int, role: UserRole) -> Admin:
        if role not in self.ALLOWED_ROLES:
            raise ValidationError("سطح دسترسی معتبر نیست.")
        admin = await self.get(admin_id)
        if admin.role == UserRole.OWNER and role != UserRole.OWNER:
            await self._ensure_another_owner(admin.id)
        admin.role = role
        admin.is_active = True
        await self.session.commit()
        return admin

    async def deactivate(self, admin_id: int) -> Admin:
        admin = await self.get(admin_id)
        if admin.role == UserRole.OWNER:
            await self._ensure_another_owner(admin.id)
        admin.is_active = False
        await self.session.commit()
        return admin

    async def _ensure_another_owner(self, excluded_admin_id: int) -> None:
        other = await self.session.scalar(
            select(Admin.id).where(
                Admin.id != excluded_admin_id,
                Admin.role == UserRole.OWNER,
                Admin.is_active.is_(True),
            )
        )
        if other is None:
            raise ValidationError("آخرین مالک فروشگاه را نمی‌توان حذف یا تنزل داد.")
