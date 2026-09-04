from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup

from bot.core.callbacks import AdminCallback, NavCallback
from bot.core.filters import HasAdminRole, IsAdmin, IsOwner
from bot.core.ui import button, keyboard
from bot.database.enums import UserRole

ROLE_MATRIX = {
    "orders": (UserRole.OWNER, UserRole.ADMIN, UserRole.OPERATOR),
    "web_store": (UserRole.OWNER, UserRole.ADMIN, UserRole.OPERATOR),
    "catalog": (UserRole.OWNER, UserRole.ADMIN),
    "users": (UserRole.OWNER, UserRole.ADMIN),
    "coupons": (UserRole.OWNER, UserRole.ADMIN),
    "broadcast": (UserRole.OWNER, UserRole.ADMIN),
    "settings": (UserRole.OWNER, UserRole.ADMIN),
    "tickets": (UserRole.OWNER, UserRole.ADMIN, UserRole.SUPPORT),
}


def protected_router(name: str) -> Router:
    router = Router(name=f"admin_{name}")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    if roles := ROLE_MATRIX.get(name):
        router.message.filter(HasAdminRole(*roles))
        router.callback_query.filter(HasAdminRole(*roles))
    return router


def owner_router(name: str) -> Router:
    router = Router(name=f"owner_{name}")
    router.message.filter(IsOwner())
    router.callback_query.filter(IsOwner())
    return router


def back_to_admin() -> InlineKeyboardMarkup:
    return keyboard(
        [
            button(
                "↩️ پنل مدیریت",
                callback_data=AdminCallback(section="dashboard", action="show").pack(),
            )
        ],
        [button("🏠 منوی اصلی", callback_data=NavCallback(action="home").pack())],
    )
