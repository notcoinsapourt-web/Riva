from __future__ import annotations

import secrets

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import CatalogCallback, NavCallback
from bot.core.exceptions import ValidationError
from bot.core.formatting import compact_text, h, money
from bot.core.states import CheckoutState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.services.catalog import CatalogService
from bot.services.coupons import CouponService
from bot.services.notifications import NotificationService
from bot.services.orders import OrderService
from bot.services.product_presentation import (
    display_name,
    order_requirements,
    parse_quantity,
    quantity_policy,
    subtotal_for,
)
from bot.services.settings import SettingsService
from bot.services.users import UserService

router = Router(name="catalog")
PAGE_SIZE = 10

CATEGORY_ORDER = (
    "اشتراک هوش مصنوعی",
    "خدمات تلگرام",
    "خدمات اینستاگرام",
    "خدمات تیک‌تاک",
    "خدمات یوتیوب",
    "سایر محصولات دیجیتال",
    "سایر شبکه‌های اجتماعی",
)


@router.callback_query(NavCallback.filter(F.action == "catalog"))
async def show_catalog(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await SettingsService(session).require_module("catalog")
    categories = await CatalogService(session).categories()
    category_rank = {name: index for index, name in enumerate(CATEGORY_ORDER)}
    categories.sort(key=lambda item: (category_rank.get(item.name, len(category_rank)), item.id))

    def category_button(category, *, featured: bool = False):
        return button(
            f"{category.emoji} {category.name}",
            callback_data=CatalogCallback(action="category", entity_id=category.id).pack(),
            custom_emoji_id=category.custom_emoji_id,
            style="danger" if featured else "primary",
        )

    rows = []
    remaining = list(categories)
    if remaining and remaining[0].name == "اشتراک هوش مصنوعی":
        rows.append([category_button(remaining.pop(0), featured=True)])
    rows.extend(
        [category_button(category) for category in remaining[index : index + 2]]
        for index in range(0, len(remaining), 2)
    )
    rows.append(
        [
            button(
                "🏠 بازگشت به منوی اصلی",
                callback_data=NavCallback(action="home").pack(),
                style="danger",
            )
        ]
    )
    custom_text = await SettingsService(session).module_content("catalog")
    text = (
        (custom_text or "<b>🛍 فروشگاه خدمات مجازی</b>\n\nیک دسته‌بندی را انتخاب کنید 👇")
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
    product_buttons = [
        button(
            f"{product.emoji} {compact_text(display_name(product), 22)}",
            callback_data=CatalogCallback(action="product", entity_id=product.id).pack(),
            custom_emoji_id=product.custom_emoji_id,
            style="primary",
        )
        for product in visible
    ]
    rows = [product_buttons[index : index + 2] for index in range(0, len(product_buttons), 2)]
    paging = []
    if page > 0:
        paging.append(
            button(
                "◀️ قبلی",
                callback_data=CatalogCallback(
                    action="category", entity_id=category.id, page=page - 1
                ).pack(),
                style="primary",
            )
        )
    if start + PAGE_SIZE < len(products):
        paging.append(
            button(
                "بعدی ▶️",
                callback_data=CatalogCallback(
                    action="category", entity_id=category.id, page=page + 1
                ).pack(),
                style="primary",
            )
        )
    if paging:
        rows.append(paging)
    rows.append(
        [
            button(
                "↩️ دسته‌بندی‌ها", callback_data=NavCallback(action="catalog").pack(), style="primary"
            ),
            button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack(), style="danger"),
        ]
    )
    text = (
        f"<b>{h(category.emoji)} {h(category.name)}</b>\n\n"
        f"{h(category.description or '')}\n\n"
        "یک محصول را انتخاب کنید 👇"
    )
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
    policy = quantity_policy(product)
    product_name = display_name(product)
    requirement, safety = order_requirements(product)
    pricing = (
        f"💳 نرخ پایه: <b>{money(product.price)}</b> برای "
        f"<b>{policy.base_quantity:,}</b> عدد\n"
        f"🔢 حداقل سفارش: <b>{policy.minimum:,}</b>\n"
        f"📦 حداکثر سفارش: <b>{policy.maximum:,}</b>\n"
        f"➕ گام تعداد: مضرب <b>{policy.step:,}</b>"
        if policy
        else f"💳 قیمت محصول: <b>{money(product.price)}</b>\n📦 نوع سفارش: <b>ثابت</b>"
    )
    text = (
        f"<b>{h(product.emoji)} {h(product_name)}</b>\n\n"
        f"{h(product.description)}\n\n"
        "⚡ شروع: <b>پس از ثبت و بررسی سفارش</b>\n"
        f"🎯 دسته‌بندی: <b>{h(product.category.name)}</b>\n"
        "✅ قیمت نهایی قبل از پرداخت نمایش داده می‌شود\n"
        f"📝 اطلاعات لازم: {h(requirement)}\n"
        f"🔐 {h(safety)}\n\n"
        f"{pricing}"
    )
    markup = keyboard(
        [
            button(
                "🔢 ثبت تعداد و ادامه" if policy else "🛒 ادامه خرید",
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
                style="primary",
            )
        ],
        [
            button(
                "🏠 منوی اصلی",
                callback_data=NavCallback(action="home").pack(),
                style="danger",
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
    policy = quantity_policy(product)
    await state.set_data(
        {
            "product_id": product.id,
            "checkout_key": secrets.token_urlsafe(18),
            "coupon_code": None,
            "quantity": 1,
        }
    )
    if policy:
        await state.set_state(CheckoutState.waiting_for_quantity)
        await edit_or_send(
            callback,
            f"<b>🔢 تعداد {h(display_name(product))}</b>\n\n"
            f"تعداد دلخواه را بین <b>{policy.minimum:,}</b> تا "
            f"<b>{policy.maximum:,}</b> وارد کنید.\n"
            f"عدد باید مضربی از <b>{policy.step:,}</b> باشد.\n\n"
            f"💳 نرخ پایه: {money(product.price)} برای {policy.base_quantity:,} عدد\n\n"
            "نمونه: <code>2500</code>",
            reply_markup=keyboard(
                [
                    button(
                        "لغو و بازگشت",
                        callback_data=CatalogCallback(
                            action="product", entity_id=product.id
                        ).pack(),
                        style="danger",
                    )
                ]
            ),
        )
        return
    await _ask_order_details(callback, product, state, quantity=1)


@router.message(CheckoutState.waiting_for_quantity, F.text)
async def receive_quantity(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    product = await CatalogService(session).product(int(data["product_id"]))
    policy = quantity_policy(product)
    if policy is None:
        await state.clear()
        await message.answer("این محصول تعداد متغیر ندارد؛ دوباره آن را انتخاب کنید.")
        return
    try:
        quantity = policy.validate(parse_quantity(message.text))
    except ValidationError as exc:
        await message.answer(f"⚠️ {h(str(exc))}\n\nلطفاً تعداد درست را دوباره ارسال کنید.")
        return
    await state.update_data(quantity=quantity)
    await _ask_order_details(message, product, state, quantity=quantity)


async def _ask_order_details(
    event: Message | CallbackQuery,
    product,
    state: FSMContext,
    *,
    quantity: int,
) -> None:
    prompt, safety = order_requirements(product)
    await state.set_state(CheckoutState.waiting_for_details)
    await edit_or_send(
        event,
        f"<b>📝 اطلاعات لازم برای {h(display_name(product))}</b>\n\n"
        f"🔢 تعداد انتخابی: <b>{quantity:,}</b>\n"
        f"💳 مبلغ محاسبه‌شده: <b>{money(subtotal_for(product, quantity))}</b>\n\n"
        f"<b>چه چیزی ارسال کنم؟</b>\n{h(prompt)}\n\n"
        f"🔐 {h(safety)}",
        reply_markup=keyboard(
            [
                button(
                    "لغو و بازگشت",
                    callback_data=CatalogCallback(action="product", entity_id=product.id).pack(),
                    style="danger",
                )
            ]
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
    subtotal = subtotal_for(product, int(data.get("quantity", 1)))
    await CouponService(session).validate(message.text, user_id=db_user.id, subtotal=subtotal)
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
        quantity=int(data.get("quantity", 1)),
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
        f"تعداد: {order.quantity:,}\n"
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
    quantity = int(data.get("quantity", 1))
    subtotal = subtotal_for(product, quantity)
    discount = 0
    if data.get("coupon_code"):
        _, discount = await CouponService(session).validate(
            str(data["coupon_code"]), user_id=user.id, subtotal=subtotal
        )
    total = subtotal - discount
    text = (
        "<b>🧾 تأیید نهایی سفارش</b>\n\n"
        f"محصول: <b>{h(display_name(product))}</b>\n"
        f"تعداد: <b>{quantity:,}</b>\n"
        f"قیمت قبل از تخفیف: {money(subtotal)}\n"
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
