from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import NavCallback, OrderCallback
from bot.core.formatting import ORDER_STATUS_FA, dt, h, money
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.services.orders import OrderService
from bot.services.settings import SettingsService

router = Router(name="orders")


@router.callback_query(NavCallback.filter(F.action == "orders"))
async def list_orders(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    settings = SettingsService(session)
    await settings.require_module("orders")
    orders = await OrderService(session).user_orders(db_user.id)
    rows = [
        [
            button(
                f"{ORDER_STATUS_FA[order.status].split()[0]} {order.number}"
                f" • {money(order.total_amount)}",
                callback_data=OrderCallback(action="detail", order_id=order.id).pack(),
            )
        ]
        for order in orders
    ]
    rows.append([button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())])
    text = await settings.module_content("orders", "<b>📦 سفارش‌های من</b>")
    text += "\n\n"
    text += (
        "برای مشاهده جزئیات، یک سفارش را انتخاب کنید." if orders else "هنوز سفارشی ثبت نکرده‌اید."
    )
    await edit_or_send(callback, text, reply_markup=keyboard(*rows))


@router.callback_query(OrderCallback.filter(F.action == "detail"))
async def order_detail(
    callback: CallbackQuery,
    callback_data: OrderCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    order = await OrderService(session).get(callback_data.order_id)
    if order.user_id != db_user.id and not await SettingsService(session).module_enabled("orders"):
        await callback.answer("دسترسی غیرمجاز.", show_alert=True)
        return
    if order.user_id != db_user.id:
        # Admin order details are handled in the protected admin router.
        await callback.answer("دسترسی غیرمجاز.", show_alert=True)
        return
    history = "\n".join(
        f"• {ORDER_STATUS_FA[item.to_status]} — {dt(item.created_at)}"
        for item in order.history[-5:]
    )
    text = (
        f"<b>📦 سفارش {order.number}</b>\n\n"
        f"محصول: <b>{h(order.product_name)}</b>\n"
        f"تعداد: <b>{order.quantity:,}</b>\n"
        f"مبلغ: <b>{money(order.total_amount)}</b>\n"
        f"وضعیت: {ORDER_STATUS_FA[order.status]}\n"
        f"ثبت: {dt(order.created_at)}\n\n"
        f"<b>اطلاعات ارسال‌شده</b>\n<code>{h(order.customer_input)}</code>\n\n"
        f"<b>تاریخچه وضعیت</b>\n{history or '—'}"
    )
    await edit_or_send(
        callback,
        text,
        reply_markup=keyboard(
            [button("↩️ سفارش‌ها", callback_data=NavCallback(action="orders").pack())],
            [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
        ),
    )
