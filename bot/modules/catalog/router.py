from __future__ import annotations

import secrets

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import CatalogCallback, NavCallback
from bot.core.formatting import compact_text, h, money
from bot.core.states import CheckoutState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.services.catalog import CatalogService
from bot.services.coupons import CouponService
from bot.services.notifications import NotificationService
from bot.services.orders import OrderService
from bot.services.settings import SettingsService
from bot.services.users import UserService

router = Router(name="catalog")
PAGE_SIZE = 8


@router.callback_query(NavCallback.filter(F.action == "catalog"))
async def show_catalog(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await SettingsService(session).require_module("catalog")
    categories = await CatalogService(session).categories()
    rows = [
        [
            button(
                category.name if category.custom_emoji_id else f"{category.emoji} {category.name}",
                callback_data=CatalogCallback(action="category", entity_id=category.id).pack(),
                custom_emoji_id=category.custom_emoji_id,
            )
        ]
        for category in categories
    ]
    rows.append([button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())])
    text = (
        "<b>🛍 فروشگاه Persian Shop</b>\n\nسرویس موردنظر را از دسته‌بندی‌های زیر انتخاب کنید."
        if categories
        else "<b>🛍 فروشگاه</b>\n\nدر حال حاضر محصول فعالی ثبت نشده است."
    )
    await edit_or_send(callback, text, reply_markup=keyboard(*rows))


@router.callback_query(CatalogCallback.filter(F.action == "category"))
async def show_category(
    callback: CallbackQuery,
    callback_data: CatalogCallback,
    session: AsyncSession,
) -> None:
    await SettingsService(session).require_module("catalog")
    service = CatalogService(session)
    category = await service.category(callback_data.entity_id)
    products = await service.products(category.id)
    page = max(0, callback_data.page)
    start = page * PAGE_SIZE
    visible = products[start : start + PAGE_SIZE]
    rows = [
        [
            button(
                (
                    compact_text(product.name, 26)
                    if product.custom_emoji_id
                    else f"{product.emoji} {compact_text(product.name, 26)}"
                )
                + f" • {money(product.price)}",
                callback_data=CatalogCallback(action="product", entity_id=product.id).pack(),
                custom_emoji_id=product.custom_emoji_id,
            )
        ]
        for product in visible
    ]
    paging = []
    if page > 0:
        paging.append(
            button(
                "◀️ قبلی",
                callback_data=CatalogCallback(
                    action="category", entity_id=category.id, page=page - 1
                ).pack(),
            )
        )
    if start + PAGE_SIZE < len(products):
        paging.append(
            button(
                "بعدی ▶️",
                callback_data=CatalogCallback(
                    action="category", entity_id=category.id, page=page + 1
                ).pack(),
            )
        )
    if paging:
        rows.append(paging)
    rows.extend(
        [
            [button("🗂 دسته‌بندی‌ها", callback_data=NavCallback(action="catalog").pack())],
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
        ]
    )
    text = f"<b>{h(category.emoji)} {h(category.name)}</b>\n\n{h(category.description or '')}"
    if not products:
        text += "\n\nهنوز محصول فعالی در این دسته ثبت نشده است."
    await edit_or_send(callback, text, reply_markup=keyboard(*rows))


@router.callback_query(CatalogCallback.filter(F.action == "product"))
async def show_product(
    callback: CallbackQuery,
    callback_data: CatalogCallback,
    session: AsyncSession,
) -> None:
    product = await CatalogService(session).product(callback_data.entity_id)
    text = (
        f"<b>{h(product.emoji)} {h(product.name)}</b>\n\n"
        f"{h(product.description)}\n\n"
        f"💳 قیمت: <b>{money(product.price)}</b>\n"
        "⚡ تحویل و پیگیری از داخل همین ربات"
    )
    markup = keyboard(
        [
            button(
                "خرید این محصول",
                callback_data=CatalogCallback(action="buy", entity_id=product.id).pack(),
                style="success",
            )
        ],
        [
            button(
                "↩️ بازگشت",
                callback_data=CatalogCallback(
                    action="category", entity_id=product.category_id
                ).pack(),
            )
        ],
    )
    if product.photo_file_id and isinstance(callback.message, Message):
        await callback.answer()
        await callback.message.delete()
        await callback.message.answer_photo(
            product.photo_file_id, caption=text, reply_markup=markup
        )
    else:
        await edit_or_send(callback, text, reply_markup=markup)


@router.callback_query(CatalogCallback.filter(F.action == "buy"))
async def begin_checkout(
    callback: CallbackQuery,
    callback_data: CatalogCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await SettingsService(session).require_module("catalog")
    product = await CatalogService(session).product(callback_data.entity_id)
    await state.set_state(CheckoutState.waiting_for_details)
    await state.set_data(
        {
            "product_id": product.id,
            "checkout_key": secrets.token_urlsafe(18),
            "coupon_code": None,
        }
    )
    await edit_or_send(
        callback,
        f"<b>📝 اطلاعات سفارش</b>\n\n{h(product.input_prompt)}",
        reply_markup=keyboard(
            [button("لغو", callback_data=NavCallback(action="catalog").pack(), style="danger")]
        ),
    )


@router.message(CheckoutState.waiting_for_details, F.text)
async def receive_details(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    await state.update_data(customer_input=message.text.strip())
    await state.set_state(CheckoutState.confirming)
    await _show_confirmation(message, session, db_user, state, data["product_id"])


@router.callback_query(CatalogCallback.filter(F.action == "coupon"))
async def ask_coupon(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CheckoutState.waiting_for_coupon)
    await edit_or_send(
        callback,
        "<b>🎟 کد تخفیف</b>\n\nکد را ارسال کنید یا آن را حذف کنید.",
        reply_markup=keyboard(
            [
                button(
                    "حذف کد",
                    callback_data=CatalogCallback(action="remove_coupon").pack(),
                    style="danger",
                )
            ]
        ),
    )


@router.message(CheckoutState.waiting_for_coupon, F.text)
async def receive_coupon(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    product = await CatalogService(session).product(data["product_id"])
    await CouponService(session).validate(message.text, user_id=db_user.id, subtotal=product.price)
    await state.update_data(coupon_code=message.text.strip().upper())
    await state.set_state(CheckoutState.confirming)
    await _show_confirmation(message, session, db_user, state, product.id)


@router.callback_query(CatalogCallback.filter(F.action == "remove_coupon"))
async def remove_coupon(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    await state.update_data(coupon_code=None)
    await state.set_state(CheckoutState.confirming)
    await _show_confirmation(callback, session, db_user, state, data["product_id"])


@router.callback_query(CatalogCallback.filter(F.action == "confirm"))
async def confirm_checkout(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    required = {"product_id", "customer_input", "checkout_key"}
    if not required.issubset(data):
        await state.clear()
        await callback.answer("جلسه خرید منقضی شده؛ دوباره محصول را انتخاب کنید.", show_alert=True)
        return
    order = await OrderService(session).checkout(
        user=db_user,
        product_id=int(data["product_id"]),
        customer_input=str(data["customer_input"]),
        checkout_key=str(data["checkout_key"]),
        coupon_code=data.get("coupon_code"),
    )
    await state.clear()
    await edit_or_send(
        callback,
        "<b>✅ سفارش با موفقیت ثبت شد</b>\n\n"
        f"شماره سفارش: <code>{order.number}</code>\n"
        f"مبلغ: <b>{money(order.total_amount)}</b>\n"
        "وضعیت: 🕐 در انتظار بررسی\n\n"
        "هر تغییر وضعیت از طریق ربات به شما اطلاع داده می‌شود.",
        reply_markup=keyboard(
            [
                button(
                    "مشاهده سفارش",
                    callback_data=NavCallback(action="orders").pack(),
                    style="primary",
                )
            ],
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
        ),
    )
    await NotificationService(session, bot).notify_admins(
        "<b>📦 سفارش جدید</b>\n\n"
        f"شماره: <code>{order.number}</code>\n"
        f"محصول: {h(order.product_name)}\n"
        f"مبلغ: {money(order.total_amount)}\n"
        f"کاربر: <code>{db_user.telegram_id}</code>"
    )


async def _show_confirmation(
    event: Message | CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    product_id: int,
) -> None:
    data = await state.get_data()
    product = await CatalogService(session).product(product_id)
    hydrated = await UserService(session).get_by_id(user.id)
    discount = 0
    if data.get("coupon_code"):
        _, discount = await CouponService(session).validate(
            str(data["coupon_code"]), user_id=user.id, subtotal=product.price
        )
    total = product.price - discount
    text = (
        "<b>🧾 تأیید نهایی سفارش</b>\n\n"
        f"محصول: <b>{h(product.name)}</b>\n"
        f"قیمت: {money(product.price)}\n"
        f"تخفیف: {money(discount)}\n"
        f"مبلغ نهایی: <b>{money(total)}</b>\n"
        f"موجودی کیف پول: {money(hydrated.wallet.balance)}\n\n"
        f"اطلاعات سفارش:\n<code>{h(data.get('customer_input', ''))}</code>"
    )
    await edit_or_send(
        event,
        text,
        reply_markup=keyboard(
            [
                button(
                    "پرداخت از کیف پول و ثبت",
                    callback_data=CatalogCallback(action="confirm").pack(),
                    style="success",
                )
            ],
            [button("🎟 کد تخفیف", callback_data=CatalogCallback(action="coupon").pack())],
            [button("لغو", callback_data=NavCallback(action="catalog").pack(), style="danger")],
        ),
    )
