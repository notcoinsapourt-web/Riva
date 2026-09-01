from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from bot.config import AppSettings
from bot.core.exceptions import InsufficientBalanceError, PaymentDisabledError, ValidationError
from bot.database.bootstrap import seed_database
from bot.database.catalog_seed import DEFAULT_CATEGORIES, DEFAULT_PRODUCTS
from bot.database.enums import (
    CouponType,
    OrderStatus,
    PaymentStatus,
    TransactionType,
    UserRole,
)
from bot.database.models import Category, Order, Payment, Product, Transaction, User, Wallet
from bot.modules.payments.providers.base import GatewayVerification
from bot.services.admin import AdminAccessService
from bot.services.coupons import CouponService
from bot.services.orders import OrderService
from bot.services.payments import PaymentService
from bot.services.settings import SettingsService
from bot.services.wallet import WalletService


async def _customer(session, telegram_id: int = 1001) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name="Test",
        referral_code=f"REF{telegram_id}",
    )
    user.wallet = Wallet(balance=0)
    session.add(user)
    await session.commit()
    return user


async def _product(session, price: int = 120_000) -> Product:
    category = Category(name="AI", emoji="🤖")
    session.add(category)
    await session.flush()
    product = Product(
        category_id=category.id,
        name="ChatGPT Plus",
        description="subscription",
        price=price,
        input_prompt="email",
    )
    session.add(product)
    await session.commit()
    return product


@pytest.mark.asyncio
async def test_wallet_is_idempotent_and_never_negative(database) -> None:
    async with database.session_factory() as session:
        user = await _customer(session)
        service = WalletService(session)
        first = await service.adjust(
            user_id=user.id,
            amount=50_000,
            transaction_type=TransactionType.ADMIN_CREDIT,
            description="credit",
            idempotency_key="same-key",
        )
        second = await service.adjust(
            user_id=user.id,
            amount=50_000,
            transaction_type=TransactionType.ADMIN_CREDIT,
            description="credit",
            idempotency_key="same-key",
        )
        assert first.id == second.id
        assert (await service.get(user.id)).balance == 50_000
        assert await session.scalar(select(func.count(Transaction.id))) == 1
        with pytest.raises(InsufficientBalanceError):
            await service.adjust(
                user_id=user.id,
                amount=-60_000,
                transaction_type=TransactionType.ADMIN_DEBIT,
                description="too much",
                idempotency_key="debit-key",
            )


@pytest.mark.asyncio
async def test_sqlite_wallet_updates_are_serialized(database) -> None:
    async with database.session_factory() as session:
        user = await _customer(session, telegram_id=1010)
        user_id = user.id

    async def credit(key: str) -> None:
        async with database.session_factory() as session:
            await WalletService(session).adjust(
                user_id=user_id,
                amount=25_000,
                transaction_type=TransactionType.ADMIN_CREDIT,
                description="parallel credit",
                idempotency_key=key,
            )

    await asyncio.gather(credit("parallel-1"), credit("parallel-2"))
    async with database.session_factory() as session:
        assert (await WalletService(session).get(user_id)).balance == 50_000


@pytest.mark.asyncio
async def test_checkout_double_click_deducts_once_and_cancel_refunds_once(database) -> None:
    async with database.session_factory() as session:
        user = await _customer(session)
        product = await _product(session)
        wallet = WalletService(session)
        await wallet.adjust(
            user_id=user.id,
            amount=200_000,
            transaction_type=TransactionType.ADMIN_CREDIT,
            description="initial",
            idempotency_key="initial-credit",
        )
        service = OrderService(session)
        first = await service.checkout(
            user=user,
            product_id=product.id,
            customer_input="customer@example.com",
            checkout_key="checkout-unique",
        )
        second = await service.checkout(
            user=user,
            product_id=product.id,
            customer_input="customer@example.com",
            checkout_key="checkout-unique",
        )
        assert first.id == second.id
        assert await session.scalar(select(func.count(Order.id))) == 1
        assert (await wallet.get(user.id)).balance == 80_000

        cancelled = await service.change_status(
            order_id=first.id,
            new_status=OrderStatus.CANCELLED,
            changed_by_user_id=user.id,
        )
        assert cancelled.status == OrderStatus.CANCELLED
        assert (await wallet.get(user.id)).balance == 200_000
        same = await service.change_status(
            order_id=first.id,
            new_status=OrderStatus.CANCELLED,
            changed_by_user_id=user.id,
        )
        assert same.id == first.id
        assert (await wallet.get(user.id)).balance == 200_000


@pytest.mark.asyncio
async def test_checkout_uses_requested_service_quantity_and_calculated_price(database) -> None:
    async with database.session_factory() as session:
        user = await _customer(session, telegram_id=1020)
        category = Category(name="Instagram", emoji="📸")
        session.add(category)
        await session.flush()
        product = Product(
            category_id=category.id,
            name="۱۰۰۰ فالوور اقتصادی اینستاگرام",
            description="فالوور اقتصادی",
            price=149_000,
            input_prompt="لینک عمومی پیج را ارسال کنید.",
            photo_file_id=(
                "https://example.test/assets/products/instagram-followers-1k-economy.jpg?v=2"
            ),
        )
        session.add(product)
        await session.commit()
        await WalletService(session).adjust(
            user_id=user.id,
            amount=500_000,
            transaction_type=TransactionType.ADMIN_CREDIT,
            description="quantity checkout credit",
            idempotency_key="quantity-credit",
        )

        order = await OrderService(session).checkout(
            user=user,
            product_id=product.id,
            customer_input="https://instagram.com/example",
            checkout_key="quantity-checkout",
            quantity=2_500,
        )

        assert order.product_name == "فالوور اقتصادی"
        assert order.quantity == 2_500
        assert order.subtotal == 372_500
        assert order.total_amount == 372_500
        assert (await WalletService(session).get(user.id)).balance == 127_500


@pytest.mark.asyncio
async def test_coupon_capacity_cannot_be_exceeded(database) -> None:
    async with database.session_factory() as session:
        first = await _customer(session, telegram_id=2011)
        second = await _customer(session, telegram_id=2012)
        second_id = second.id
        product = await _product(session, price=40_000)
        coupon = await CouponService(session).create(
            code="ONLYONE",
            coupon_type=CouponType.PERCENT,
            value=50,
            max_uses=1,
            expires_at=None,
        )
        wallet = WalletService(session)
        for user in (first, second):
            await wallet.adjust(
                user_id=user.id,
                amount=100_000,
                transaction_type=TransactionType.ADMIN_CREDIT,
                description="credit",
                idempotency_key=f"coupon-credit-{user.id}",
            )
        orders = OrderService(session)
        await orders.checkout(
            user=first,
            product_id=product.id,
            customer_input="first",
            checkout_key="coupon-checkout-1",
            coupon_code=coupon.code,
        )
        with pytest.raises(ValidationError):
            await orders.checkout(
                user=second,
                product_id=product.id,
                customer_input="second",
                checkout_key="coupon-checkout-2",
                coupon_code=coupon.code,
            )
        assert (await wallet.get(second_id)).balance == 100_000


@pytest.mark.asyncio
async def test_core_module_cannot_be_disabled(database) -> None:
    settings = AppSettings(bot_token="123456:TEST", admin_ids=())
    await seed_database(database.session_factory, settings)
    async with database.session_factory() as session:
        service = SettingsService(session)
        with pytest.raises(ValidationError):
            await service.toggle_module("catalog")
        wallet = await service.toggle_module("wallet")
        assert wallet.is_enabled is False


@pytest.mark.asyncio
async def test_profile_and_rules_are_editable_modules(database) -> None:
    settings = AppSettings(bot_token="123456:TEST", admin_ids=())
    await seed_database(database.session_factory, settings)
    async with database.session_factory() as session:
        service = SettingsService(session)
        modules = {item.name: item for item in await service.modules()}
        assert modules["profile"].menu_text == "حساب کاربری"
        assert modules["profile"].emoji == "👤"
        assert modules["rules"].menu_text == "راهنما و قوانین"
        assert modules["rules"].emoji == "📄"

        profile = await service.toggle_module("profile")
        rules = await service.toggle_module("rules")
        assert profile.is_enabled is False
        assert rules.is_enabled is False


@pytest.mark.asyncio
async def test_catalog_seed_is_complete_and_idempotent(database) -> None:
    settings = AppSettings(bot_token="123456:TEST", admin_ids=())
    await seed_database(database.session_factory, settings)
    await seed_database(database.session_factory, settings)

    async with database.session_factory() as session:
        category_count = await session.scalar(select(func.count(Category.id)))
        product_count = await session.scalar(select(func.count(Product.id)))
        products_with_photos = await session.scalar(
            select(func.count(Product.id)).where(Product.photo_file_id.is_not(None))
        )

        assert category_count == len(DEFAULT_CATEGORIES)
        assert product_count == len(DEFAULT_PRODUCTS)
        assert products_with_photos == len(DEFAULT_PRODUCTS)


@pytest.mark.asyncio
async def test_payments_are_double_locked(database) -> None:
    settings = AppSettings(
        bot_token="123456:TEST",
        payments_enabled=True,
        payment_integration_confirmed=False,
    )
    async with database.session_factory() as session:
        user = await _customer(session)
        with pytest.raises(PaymentDisabledError):
            await PaymentService(session, settings).create_invoice(
                user_id=user.id,
                amount=100_000,
                provider_name="zarinpal",
                description="test",
            )


@pytest.mark.asyncio
async def test_payment_verification_credits_wallet_once(database) -> None:
    class FakeProvider:
        name = "fake"

        async def verify(self, **_):
            return GatewayVerification(paid=True, reference_id="TRACK-1")

    settings = AppSettings(
        bot_token="123456:TEST",
        payments_enabled=True,
        payment_integration_confirmed=True,
    )
    async with database.session_factory() as session:
        user = await _customer(session, telegram_id=3010)
        payment = Payment(
            invoice_number="INV-TEST-1",
            user_id=user.id,
            provider="fake",
            amount=75_000,
            authority="AUTH-1",
            status=PaymentStatus.PENDING,
        )
        session.add(payment)
        await session.commit()
        service = PaymentService(session, settings)
        service.registry._providers["fake"] = FakeProvider()  # type: ignore[assignment]
        first = await service.verify(payment.invoice_number)
        second = await service.verify(payment.invoice_number)
        assert first.status == PaymentStatus.PAID
        assert second.id == first.id
        assert (await WalletService(session).get(user.id)).balance == 75_000
        count = await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.idempotency_key == f"payment-deposit:{payment.id}"
            )
        )
        assert count == 1


@pytest.mark.asyncio
async def test_last_owner_cannot_be_removed(database) -> None:
    settings = AppSettings(bot_token="123456:TEST", admin_ids=(7001,))
    await seed_database(database.session_factory, settings)
    async with database.session_factory() as session:
        service = AdminAccessService(session)
        first_owner = (await service.list())[0]
        with pytest.raises(ValidationError):
            await service.deactivate(first_owner.id)

        second = await _customer(session, telegram_id=7002)
        await service.add(second.telegram_id, UserRole.OWNER)
        first = await service.deactivate(first_owner.id)
        assert first.is_active is False
