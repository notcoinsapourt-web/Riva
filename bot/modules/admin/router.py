from aiogram import Router

from bot.modules.admin import (
    admins,
    broadcast,
    catalog,
    channels,
    coupons,
    dashboard,
    deposits,
    messages,
    orders,
    settings,
    tickets,
    users,
)

router = Router(name="admin")
router.include_routers(
    dashboard.router,
    deposits.router,
    channels.router,
    admins.router,
    orders.router,
    catalog.router,
    users.router,
    coupons.router,
    broadcast.router,
    settings.router,
    tickets.router,
    messages.router,
)
