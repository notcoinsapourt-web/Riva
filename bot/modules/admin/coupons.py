from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.formatting import dt, h, money
from bot.core.states import AdminCouponState
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.enums import CouponType
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.coupons import CouponService
from bot.services.logs import ActivityLogService

router = protected_router("coupons")


@router.callback_query(AdminCallback.filter((F.section == "coupons") & (F.action == "list")))
async def coupons_list(callback: CallbackQuery, session: AsyncSession) -> None:
    coupons = await CouponService(session).list()
    rows = [
        [
            button(
                f"{'🟢' if item.is_active else '⚫'} {item.code}"
                f" • {_value(item.coupon_type, item.value)}",
                callback_data=AdminCallback(
                    section="coupons", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in coupons[:30]
    ]
    rows.extend(
        [
            [
                button(
                    "➕ کد تخفیف جدید",
                    callback_data=AdminCallback(section="coupons", action="add").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        callback,
        "<b>🎟 مدیریت تخفیف‌ها</b>\n\n"
        + ("یک کد را انتخاب کنید." if coupons else "هنوز کدی ساخته نشده است."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "coupons") & (F.action == "detail")))
async def coupon_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    coupons = await CouponService(session).list()
    coupon = next((item for item in coupons if item.id == callback_data.entity_id), None)
    if coupon is None:
        await callback.answer("کد پیدا نشد.", show_alert=True)
        return
    await edit_or_send(
        callback,
        f"<b>🎟 {h(coupon.code)}</b>\n\n"
        f"مقدار: <b>{_value(coupon.coupon_type, coupon.value)}</b>\n"
        f"استفاده: {coupon.used_count}/{coupon.max_uses or '∞'}\n"
        f"انقضا: {dt(coupon.expires_at)}\n"
        f"وضعیت: {'🟢 فعال' if coupon.is_active else '⚫ غیرفعال'}",
        reply_markup=keyboard(
            [
                button(
                    "غیرفعال‌سازی" if coupon.is_active else "فعال‌سازی",
                    callback_data=AdminCallback(
                        section="coupons", action="toggle", entity_id=coupon.id
                    ).pack(),
                )
            ],
            [
                button(
                    "🗑 حذف",
                    callback_data=AdminCallback(
                        section="coupons", action="delete", entity_id=coupon.id
                    ).pack(),
                    style="danger",
                )
            ],
            [
                button(
                    "↩️ تخفیف‌ها",
                    callback_data=AdminCallback(section="coupons", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "coupons") & (F.action == "toggle")))
async def coupon_toggle(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    await CouponService(session).toggle(callback_data.entity_id)
    await coupon_detail(callback, callback_data, session)


@router.callback_query(AdminCallback.filter((F.section == "coupons") & (F.action == "delete")))
async def coupon_delete(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    await CouponService(session).delete(callback_data.entity_id)
    await ActivityLogService(session).record(
        "coupon.deleted_or_disabled",
        actor_user_id=db_user.id,
        entity_type="coupon",
        entity_id=callback_data.entity_id,
    )
    await coupons_list(callback, session)


@router.callback_query(AdminCallback.filter((F.section == "coupons") & (F.action == "add")))
async def coupon_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminCouponState.code)
    await edit_or_send(callback, "<b>➕ کد تخفیف جدید</b>\n\nکد لاتین را ارسال کنید.")


@router.message(AdminCouponState.code, F.text)
async def coupon_add_code(message: Message, state: FSMContext) -> None:
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminCouponState.coupon_type)
    await message.answer(
        "نوع تخفیف را انتخاب کنید.",
        reply_markup=keyboard(
            [
                button(
                    "درصدی",
                    callback_data=AdminCallback(section="coupons", action="type_percent").pack(),
                ),
                button(
                    "مبلغ ثابت",
                    callback_data=AdminCallback(section="coupons", action="type_fixed").pack(),
                ),
            ]
        ),
    )


@router.callback_query(
    AdminCouponState.coupon_type,
    AdminCallback.filter((F.section == "coupons") & F.action.startswith("type_")),
)
async def coupon_add_type(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    coupon_type = callback_data.action.removeprefix("type_")
    await state.update_data(coupon_type=coupon_type)
    await state.set_state(AdminCouponState.value)
    await edit_or_send(
        callback,
        "درصد را فقط با عدد ارسال کنید."
        if coupon_type == "percent"
        else "مبلغ تخفیف ثابت را به تومان ارسال کنید.",
    )


@router.message(AdminCouponState.value, F.text)
async def coupon_add_value(message: Message, state: FSMContext) -> None:
    raw = message.text.replace(",", "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("مقدار نامعتبر است؛ عدد مثبت ارسال کنید.")
        return
    data = await state.get_data()
    if data["coupon_type"] == "percent" and int(raw) > 100:
        await message.answer("درصد نمی‌تواند بیشتر از ۱۰۰ باشد.")
        return
    await state.update_data(value=int(raw))
    await state.set_state(AdminCouponState.max_uses)
    await message.answer("حداکثر تعداد استفاده را بفرستید؛ برای نامحدود عدد 0 را ارسال کنید.")


@router.message(AdminCouponState.max_uses, F.text)
async def coupon_add_limit(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("فقط عدد ارسال کنید.")
        return
    await state.update_data(max_uses=None if int(raw) == 0 else int(raw))
    await state.set_state(AdminCouponState.expires_at)
    await message.answer(
        "تاریخ انقضا را به شکل 2026-12-31 بفرستید؛ برای بدون انقضا عدد 0 را ارسال کنید."
    )


@router.message(AdminCouponState.expires_at, F.text)
async def coupon_add_expiry(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    raw = message.text.strip()
    expires_at = None
    if raw != "0":
        try:
            expires_at = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            await message.answer("فرمت تاریخ درست نیست؛ نمونه: 2026-12-31")
            return
    data = await state.get_data()
    coupon = await CouponService(session).create(
        code=str(data["code"]),
        coupon_type=CouponType(str(data["coupon_type"])),
        value=int(data["value"]),
        max_uses=data["max_uses"],
        expires_at=expires_at,
    )
    await ActivityLogService(session).record(
        "coupon.created",
        actor_user_id=db_user.id,
        entity_type="coupon",
        entity_id=coupon.id,
    )
    await state.clear()
    await message.answer(
        f"✅ کد <code>{h(coupon.code)}</code> ساخته شد.",
        reply_markup=keyboard(
            [
                button(
                    "تخفیف‌ها",
                    callback_data=AdminCallback(section="coupons", action="list").pack(),
                )
            ]
        ),
    )


def _value(coupon_type: CouponType, value: int) -> str:
    return f"{value}%" if coupon_type == CouponType.PERCENT else money(value)
