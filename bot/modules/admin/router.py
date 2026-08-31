from aiogram import Router

from bot.modules.admin import (
    admins,
    broadcast,
    catalog,
    coupons,
    dashboard,
    messages,
    orders,
    settings,
    tickets,
    users,
)

router = Router(name="admin")
router.include_routers(
    dashboard.router,
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
