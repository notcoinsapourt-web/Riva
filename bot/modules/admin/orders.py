from __future__ import annotations

from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import ORDER_STATUS_FA, dt, h, money
from bot.core.states import AdminMessageState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import OrderStatus
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.orders import ALLOWED_TRANSITIONS, OrderService

router = protected_router("orders")


@router.callback_query(AdminCallback.filter((F.section == "orders") & (F.action == "list")))
async def list_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    orders = await OrderService(session).admin_orders()
    rows = [
        [
            button(
                f"{ORDER_STATUS_FA[item.status].split()[0]} {item.number}"
                f" • {money(item.total_amount)}",
                callback_data=AdminCallback(
                    section="orders", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in orders
    ]
    rows.append(
        [
            button(
                "↩️ پنل مدیریت",
                callback_data=AdminCallback(section="dashboard", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>📦 مدیریت سفارش‌ها</b>\n\n"
        + ("آخرین سفارش‌ها:" if orders else "هنوز سفارشی ثبت نشده است."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "orders") & (F.action == "detail")))
async def order_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    order = await OrderService(session).get(callback_data.entity_id)
    transitions = ALLOWED_TRANSITIONS[order.status]
    rows = []
    transition_labels = {
        OrderStatus.APPROVED: "✅ تأیید",
        OrderStatus.PROCESSING: "⚙️ شروع انجام",
        OrderStatus.COMPLETED: "🎉 تکمیل",
        OrderStatus.CANCELLED: "❌ لغو و بازپرداخت",
    }
    for status in transitions:
        rows.append(
            [
                button(
                    transition_labels[status],
                    callback_data=AdminCallback(
                        section="orders", action=f"status_{status.value}", entity_id=order.id
                    ).pack(),
                    style="danger" if status == OrderStatus.CANCELLED else "success",
                )
            ]
        )
    rows.extend(
        [
            [
                button(
                    "✉️ پیام به مشتری",
                    callback_data=AdminCallback(
                        section="orders", action="message", entity_id=order.id
                    ).pack(),
                )
            ],
            [
                button(
                    "↩️ سفارش‌ها",
                    callback_data=AdminCallback(section="orders", action="list").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        callback,
        f"<b>📦 سفارش {order.number}</b>\n\n"
        f"وضعیت: {ORDER_STATUS_FA[order.status]}\n"
        f"محصول: <b>{h(order.product_name)}</b>\n"
        f"مبلغ: <b>{money(order.total_amount)}</b>\n"
        f"کاربر: {h(order.user.first_name)} • <code>{order.user.telegram_id}</code>\n"
        f"زمان ثبت: {dt(order.created_at)}\n\n"
        f"<b>اطلاعات سفارش</b>\n<code>{h(order.customer_input)}</code>",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "orders") & F.action.startswith("status_"))
)
async def change_status(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
) -> None:
    status = OrderStatus(callback_data.action.removeprefix("status_"))
    order = await OrderService(session).change_status(
        order_id=callback_data.entity_id,
        new_status=status,
        changed_by_user_id=db_user.id,
    )
    await ActivityLogService(session).record(
        "order.status_changed",
        actor_user_id=db_user.id,
        entity_type="order",
        entity_id=order.id,
        details={"status": status.value},
    )
    try:
        await bot.send_message(
            order.user.telegram_id,
            f"<b>📦 وضعیت سفارش تغییر کرد</b>\n\n"
            f"سفارش: <code>{order.number}</code>\n"
            f"وضعیت جدید: {ORDER_STATUS_FA[order.status]}",
        )
    except TelegramAPIError:
        pass
    await order_detail(
        callback,
        AdminCallback(section="orders", action="detail", entity_id=order.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "orders") & (F.action == "message")))
async def ask_customer_message(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    order = await OrderService(session).get(callback_data.entity_id)
    await state.set_state(AdminMessageState.text)
    await state.set_data(
        {
            "purpose": "direct_message",
            "target_telegram_id": order.user.telegram_id,
            "return_section": "orders",
            "return_entity_id": order.id,
        }
    )
    await edit_or_send(
        callback,
        f"<b>✉️ پیام به مشتری سفارش {order.number}</b>\n\nمتن پیام را ارسال کنید.",
        reply_markup=keyboard(
            [
                button(
                    "لغو",
                    callback_data=AdminCallback(
                        section="orders", action="detail", entity_id=order.id
                    ).pack(),
                    style="danger",
                )
            ]
        ),
    )
