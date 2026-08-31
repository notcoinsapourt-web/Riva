from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.models import Category, Product


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def categories(self, *, active_only: bool = True) -> list[Category]:
        statement = select(Category).order_by(Category.sort_order, Category.id)
        if active_only:
            statement = statement.where(Category.is_active.is_(True))
        return list((await self.session.scalars(statement)).all())

    async def category(self, category_id: int, *, active_only: bool = True) -> Category:
        statement = select(Category).where(Category.id == category_id)
        if active_only:
            statement = statement.where(Category.is_active.is_(True))
        category = await self.session.scalar(statement)
        if category is None:
            raise NotFoundError("دسته‌بندی پیدا نشد.")
        return category

    async def products(
        self, category_id: int | None = None, *, active_only: bool = True
    ) -> list[Product]:
        statement = (
            select(Product)
            .options(selectinload(Product.category))
            .order_by(Product.sort_order, Product.id)
        )
        if category_id is not None:
            statement = statement.where(Product.category_id == category_id)
        if active_only:
            statement = statement.where(Product.is_active.is_(True))
        return list((await self.session.scalars(statement)).all())

    async def product(self, product_id: int, *, active_only: bool = True) -> Product:
        statement = (
            select(Product).options(selectinload(Product.category)).where(Product.id == product_id)
        )
        if active_only:
            statement = statement.where(Product.is_active.is_(True))
        product = await self.session.scalar(statement)
        if product is None:
            raise NotFoundError("محصول پیدا نشد یا غیرفعال شده است.")
        return product

    async def create_category(self, name: str, description: str = "", emoji: str = "🗂") -> Category:
        if not name.strip():
            raise ValidationError("نام دسته‌بندی الزامی است.")
        max_order = await self.session.scalar(select(func.max(Category.sort_order))) or 0
        category = Category(
            name=name.strip()[:128],
            description=description.strip()[:2000],
            emoji=emoji.strip()[:32] or "🗂",
            sort_order=max_order + 10,
        )
        self.session.add(category)
        await self.session.commit()
        return category

    async def update_category(self, category_id: int, **values: object) -> Category:
        category = await self.category(category_id, active_only=False)
        allowed = {"name", "description", "emoji", "custom_emoji_id", "photo_file_id", "is_active"}
        for key, value in values.items():
            if key in allowed:
                setattr(category, key, value)
        await self.session.commit()
        return category

    async def delete_category(self, category_id: int) -> None:
        category = await self.category(category_id, active_only=False)
        count = await self.session.scalar(
            select(func.count(Product.id)).where(Product.category_id == category_id)
        )
        if count:
            raise ValidationError("ابتدا محصولات این دسته را حذف یا منتقل کنید.")
        await self.session.delete(category)
        await self.session.commit()

    async def create_product(
        self,
        *,
        category_id: int,
        name: str,
        description: str,
        price: int,
        input_prompt: str,
        emoji: str = "💎",
        photo_file_id: str | None = None,
    ) -> Product:
        await self.category(category_id, active_only=False)
        if price < 0:
            raise ValidationError("قیمت نمی‌تواند منفی باشد.")
        if not name.strip():
            raise ValidationError("نام محصول الزامی است.")
        max_order = (
            await self.session.scalar(
                select(func.max(Product.sort_order)).where(Product.category_id == category_id)
            )
            or 0
        )
        product = Product(
            category_id=category_id,
            name=name.strip()[:180],
            description=description.strip()[:4000],
            price=price,
            input_prompt=input_prompt.strip()[:240]
            or "اطلاعات لازم برای انجام سفارش را وارد کنید.",
            emoji=emoji.strip()[:32] or "💎",
            photo_file_id=photo_file_id,
            sort_order=max_order + 10,
        )
        self.session.add(product)
        await self.session.commit()
        return product

    async def update_product(self, product_id: int, **values: object) -> Product:
        product = await self.product(product_id, active_only=False)
        allowed = {
            "category_id",
            "name",
            "description",
            "price",
            "photo_file_id",
            "emoji",
            "custom_emoji_id",
            "input_prompt",
            "is_active",
        }
        for key, value in values.items():
            if key not in allowed:
                continue
            if key == "price" and int(value) < 0:  # type: ignore[arg-type]
                raise ValidationError("قیمت نمی‌تواند منفی باشد.")
            setattr(product, key, value)
        await self.session.commit()
        return product

    async def delete_product(self, product_id: int) -> None:
        product = await self.product(product_id, active_only=False)
        await self.session.delete(product)
        await self.session.commit()
